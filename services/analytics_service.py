import csv
import io
import re
from datetime import date, datetime, timedelta
import sqlite3

from database import get_connection
from services.permissions import enforce_elderly_access, can_access_elderly_record


# =============================================================================
# CONSTANTS & SAFETY NOTICE
# =============================================================================

ANALYTICS_SAFETY_NOTICE = (
    "Notice: Dearly analytics and reports are designed strictly for personal tracking, "
    "care coordination, and family reassurance. They are non-diagnostic, do not predict "
    "health outcomes, and never replace professional medical judgment from a qualified doctor."
)


# =============================================================================
# DATE RANGE RESOLUTION
# =============================================================================

def resolve_date_range(
    period: str = None,
    start_date: str = None,
    end_date: str = None,
) -> tuple[str, str]:
    """
    Resolves standard periods ('last_7_days', 'last_30_days', 'last_90_days')
    or explicit (start_date, end_date) into standardized (start_date_str, end_date_str).
    If start_date and end_date are provided, uses them directly.
    """
    today = date.today()

    if start_date and end_date:
        try:
            d_start = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
            d_end = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
            if d_start <= d_end:
                return (d_start.isoformat(), d_end.isoformat())
            else:
                return (d_end.isoformat(), d_start.isoformat())
        except (ValueError, TypeError):
            pass

    if period == "last_7_days":
        s = (today - timedelta(days=6)).isoformat()
        e = today.isoformat()
        return (s, e)
    elif period == "last_90_days":
        s = (today - timedelta(days=89)).isoformat()
        e = today.isoformat()
        return (s, e)
    else:
        # Default last 30 days
        s = (today - timedelta(days=29)).isoformat()
        e = today.isoformat()
        return (s, e)


# =============================================================================
# OVERVIEW METRICS
# =============================================================================

def get_analytics_overview(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    user: dict = None,
) -> dict:
    """
    Calculates executive KPI overview metrics from actual stored records across all modules:
    - Medication adherence percentage
    - Total scheduled doses due
    - Doses marked as taken
    - Skipped doses
    - Overdue doses
    - Upcoming appointments
    - Completed appointments
    - Number of recorded health readings
    - Recent care activities count
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)

    # 1. Medication adherence metrics
    med_metrics = get_medication_adherence_analytics(
        elderly_user_id=elderly_user_id,
        start_date=s_date,
        end_date=e_date,
        user=user,
    )

    # 2. Appointment metrics
    appt_metrics = get_appointment_analytics(
        elderly_user_id=elderly_user_id,
        start_date=s_date,
        end_date=e_date,
        user=user,
    )

    # 3. Health readings count
    with get_connection() as conn:
        health_row = conn.execute(
            """SELECT COUNT(*) as count FROM health_readings
               WHERE elderly_user_id = ? AND recorded_on BETWEEN ? AND ?""",
            (elderly_user_id, s_date, e_date),
        ).fetchone()
        health_count = health_row["count"] if health_row else 0

        # 4. Care activities count
        act_row = conn.execute(
            """SELECT COUNT(*) as count FROM activity_logs
               WHERE elderly_user_id = ? AND date(created_at) BETWEEN date(?) AND date(?)""",
            (elderly_user_id, s_date, e_date),
        ).fetchone()
        activity_count = act_row["count"] if act_row else 0

    has_data = (
        med_metrics["has_data"]
        or appt_metrics["total_appointments"] > 0
        or health_count > 0
        or activity_count > 0
    )

    return {
        "start_date": s_date,
        "end_date": e_date,
        "has_data": has_data,
        "adherence_percentage": med_metrics["adherence_percentage"],
        "total_due_doses": med_metrics["total_due"],
        "taken_doses": med_metrics["total_taken"],
        "skipped_doses": med_metrics["total_skipped"],
        "overdue_doses": med_metrics["total_overdue"],
        "upcoming_appointments": appt_metrics["upcoming_count"],
        "completed_appointments": appt_metrics["completed_count"],
        "health_readings_count": health_count,
        "recent_activities_count": activity_count,
        "safety_notice": ANALYTICS_SAFETY_NOTICE,
    }


# =============================================================================
# MEDICATION ADHERENCE ANALYTICS
# =============================================================================

def get_medication_adherence_analytics(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    medication_id: int = None,
    user: dict = None,
) -> dict:
    """
    Computes rigorous medication adherence analytics:
    Adherence (%) = (Taken doses / Total doses due) * 100

    Rules enforced:
    - Strictly excludes future scheduled doses (date > today, or date == today and time > now).
    - Prevents double-counting by deduplicating logs by (medication_id, scheduled_date, scheduled_time).
    - Respects existing dose statuses: taken, skipped, missed, pending.
    - Does NOT treat pending future doses as missed.
    - Safely handles zero-dose periods (returns has_data=False, adherence_percentage=None).
    - Computes medication-wise breakdown, daily adherence trend, and weekly adherence trend.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)
    today_str = date.today().isoformat()
    now_time_str = datetime.now().strftime("%H:%M")

    with get_connection() as conn:
        # Fetch valid medications for this senior
        med_query = "SELECT id, medicine_name, dosage, frequency, stock_quantity, active FROM medications WHERE elderly_user_id = ?"
        med_params = [elderly_user_id]
        if medication_id:
            med_query += " AND id = ?"
            med_params.append(medication_id)

        med_rows = conn.execute(med_query, med_params).fetchall()
        med_dict = {m["id"]: dict(m) for m in med_rows}

        if not med_dict:
            return {
                "has_data": False,
                "adherence_percentage": None,
                "total_due": 0,
                "total_taken": 0,
                "total_skipped": 0,
                "total_overdue": 0,
                "total_missed": 0,
                "future_excluded": 0,
                "medication_breakdown": [],
                "daily_trend": [],
                "weekly_trend": [],
                "start_date": s_date,
                "end_date": e_date,
                "explanation": (
                    "Adherence (%) = (Taken Doses / Total Due Doses) x 100. "
                    "Future scheduled doses are strictly excluded from the calculation. "
                    "Skipped and missed doses count towards total due doses."
                ),
            }

        # Query dose logs in the date window (using MAX(id) to deduplicate if duplicates exist)
        log_query = """
            SELECT ml.medication_id, ml.scheduled_date, ml.scheduled_time, ml.status,
                   m.medicine_name, m.dosage
            FROM medication_logs ml
            JOIN medications m ON ml.medication_id = m.id
            WHERE m.elderly_user_id = ?
              AND ml.scheduled_date BETWEEN ? AND ?
        """
        log_params = [elderly_user_id, s_date, e_date]
        if medication_id:
            log_query += " AND m.id = ?"
            log_params.append(medication_id)

        log_query += " ORDER BY ml.scheduled_date ASC, ml.scheduled_time ASC"
        raw_logs = conn.execute(log_query, log_params).fetchall()

    # Deduplicate in-memory by (medication_id, scheduled_date, scheduled_time)
    seen_doses = set()
    deduped_logs = []
    for r in raw_logs:
        key = (r["medication_id"], r["scheduled_date"], r["scheduled_time"])
        if key not in seen_doses:
            seen_doses.add(key)
            deduped_logs.append(r)

    total_taken = 0
    total_skipped = 0
    total_missed = 0
    total_overdue = 0
    total_due = 0
    future_excluded = 0

    # Per-medication tracking
    per_med = {}
    for m_id, m_info in med_dict.items():
        per_med[m_id] = {
            "medication_id": m_id,
            "medicine_name": m_info["medicine_name"],
            "dosage": m_info["dosage"],
            "active": m_info["active"],
            "total_due": 0,
            "taken": 0,
            "skipped": 0,
            "missed": 0,
            "overdue": 0,
            "adherence_percentage": None,
        }

    # Daily aggregation tracking
    daily_buckets = {}
    # Populate all calendar days in range up to min(e_date, today_str)
    cur_d = datetime.strptime(s_date, "%Y-%m-%d").date()
    max_d = datetime.strptime(e_date, "%Y-%m-%d").date()
    while cur_d <= max_d:
        d_str = cur_d.isoformat()
        daily_buckets[d_str] = {
            "date": d_str,
            "day_name": cur_d.strftime("%a"),
            "total_due": 0,
            "taken": 0,
            "skipped": 0,
            "missed": 0,
            "overdue": 0,
            "adherence_percentage": None,
        }
        cur_d += timedelta(days=1)

    for log in deduped_logs:
        m_id = log["medication_id"]
        log_d = log["scheduled_date"]
        log_t = log["scheduled_time"]
        status = log["status"]

        # 1. Strictly exclude future doses
        is_future = False
        if log_d > today_str:
            is_future = True
        elif log_d == today_str and log_t > now_time_str:
            is_future = True

        if is_future:
            future_excluded += 1
            continue

        # 2. Count towards due and statuses
        total_due += 1
        if m_id in per_med:
            per_med[m_id]["total_due"] += 1

        if log_d in daily_buckets:
            daily_buckets[log_d]["total_due"] += 1

        if status == "taken":
            total_taken += 1
            if m_id in per_med:
                per_med[m_id]["taken"] += 1
            if log_d in daily_buckets:
                daily_buckets[log_d]["taken"] += 1
        elif status == "skipped":
            total_skipped += 1
            if m_id in per_med:
                per_med[m_id]["skipped"] += 1
            if log_d in daily_buckets:
                daily_buckets[log_d]["skipped"] += 1
        elif status == "missed":
            total_missed += 1
            if m_id in per_med:
                per_med[m_id]["missed"] += 1
            if log_d in daily_buckets:
                daily_buckets[log_d]["missed"] += 1
        elif status == "pending":
            # Past scheduled time but still pending is considered overdue
            total_overdue += 1
            if m_id in per_med:
                per_med[m_id]["overdue"] += 1
            if log_d in daily_buckets:
                daily_buckets[log_d]["overdue"] += 1

    # Overall adherence percentage
    if total_due > 0:
        adherence_pct = round((total_taken / total_due) * 100.0, 1)
        has_data = True
    else:
        adherence_pct = None
        has_data = False

    # Calculate per-medication percentages
    medication_breakdown = []
    for m_id, p in per_med.items():
        if p["total_due"] > 0:
            p["adherence_percentage"] = round((p["taken"] / p["total_due"]) * 100.0, 1)
        else:
            p["adherence_percentage"] = None
        medication_breakdown.append(p)

    medication_breakdown.sort(key=lambda x: (x["medicine_name"].lower()))

    # Calculate daily adherence percentages
    daily_trend = []
    for d_str in sorted(daily_buckets.keys()):
        b = daily_buckets[d_str]
        if b["total_due"] > 0:
            b["adherence_percentage"] = round((b["taken"] / b["total_due"]) * 100.0, 1)
        else:
            b["adherence_percentage"] = None
        daily_trend.append(b)

    # Group into weekly trend
    weekly_trend = []
    if daily_trend:
        # Group into 7-day chunks starting from s_date
        chunk_size = 7
        for i in range(0, len(daily_trend), chunk_size):
            chunk = daily_trend[i : i + chunk_size]
            w_start = chunk[0]["date"]
            w_end = chunk[-1]["date"]
            w_due = sum(c["total_due"] for c in chunk)
            w_taken = sum(c["taken"] for c in chunk)
            w_pct = round((w_taken / w_due) * 100.0, 1) if w_due > 0 else None
            weekly_trend.append({
                "week_label": f"{w_start[5:]} to {w_end[5:]}",
                "start_date": w_start,
                "end_date": w_end,
                "total_due": w_due,
                "taken": w_taken,
                "adherence_percentage": w_pct,
            })

    return {
        "has_data": has_data,
        "adherence_percentage": adherence_pct,
        "total_due": total_due,
        "total_taken": total_taken,
        "total_skipped": total_skipped,
        "total_overdue": total_overdue,
        "total_missed": total_missed,
        "future_excluded": future_excluded,
        "medication_breakdown": medication_breakdown,
        "daily_trend": daily_trend,
        "weekly_trend": weekly_trend,
        "start_date": s_date,
        "end_date": e_date,
        "explanation": (
            "Adherence (%) = (Taken Doses / Total Due Doses) x 100. "
            "Doses scheduled in the future are strictly excluded. "
            "Skipped, missed, and overdue past doses count towards total due doses."
        ),
    }


# =============================================================================
# HEALTH TREND ANALYTICS
# =============================================================================

def get_health_trend_analytics(
    elderly_user_id: int,
    measurement_type: str = None,
    unit: str = None,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    user: dict = None,
) -> dict:
    """
    Retrieves and organizes health records for trend analysis:
    - Supports Blood Pressure, Blood Sugar, Weight, Heart Rate, Oxygen Saturation (SpO2), Body Temperature.
    - Strictly uses actual stored readings; zero invented data points.
    - Separates distinct units: INCOMPATIBLE UNITS ARE NOT COMBINED.
    - Displays helpful empty states when data is missing or insufficient (< 2 points).
    - Enforces non-diagnostic clinical safety disclaimer.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)

    with get_connection() as conn:
        # Check all available measurement types logged for this senior
        type_rows = conn.execute(
            """SELECT DISTINCT reading_type FROM health_readings
               WHERE elderly_user_id = ?
               ORDER BY reading_type ASC""",
            (elderly_user_id,),
        ).fetchall()
        available_types = [r["reading_type"] for r in type_rows]

        if not available_types:
            return {
                "has_data": False,
                "has_sufficient_data": False,
                "available_types": [],
                "available_units": [],
                "selected_type": None,
                "selected_unit": None,
                "readings": [],
                "count": 0,
                "summary": {},
                "safety_disclaimer": ANALYTICS_SAFETY_NOTICE,
            }

        # Select type (default to Blood Pressure or first available)
        selected_type = measurement_type
        if not selected_type or selected_type not in available_types:
            if "Blood Pressure" in available_types:
                selected_type = "Blood Pressure"
            else:
                selected_type = available_types[0]

        # Check available units for the selected type
        unit_rows = conn.execute(
            """SELECT DISTINCT unit FROM health_readings
               WHERE elderly_user_id = ? AND reading_type = ? AND unit != ''
               ORDER BY unit ASC""",
            (elderly_user_id, selected_type),
        ).fetchall()
        available_units = [r["unit"] for r in unit_rows if r["unit"]]

        # Select unit
        selected_unit = unit
        if not selected_unit or selected_unit not in available_units:
            selected_unit = available_units[0] if available_units else ""

        # Query readings matching type, unit, and date range
        query = """
            SELECT hr.id, hr.elderly_user_id, hr.reading_type, hr.reading_value,
                   hr.numeric_value, hr.unit, hr.context, hr.recorded_on, hr.recorded_time,
                   hr.systolic, hr.diastolic, hr.notes, hr.is_corrected,
                   u.name as recorded_by_name
            FROM health_readings hr
            LEFT JOIN users u ON hr.recorded_by = u.id
            WHERE hr.elderly_user_id = ?
              AND hr.reading_type = ?
              AND hr.recorded_on BETWEEN ? AND ?
        """
        params = [elderly_user_id, selected_type, s_date, e_date]

        # Enforce unit separation to avoid combining incompatible units
        if selected_unit:
            query += " AND (hr.unit = ? OR hr.unit = '')"
            params.append(selected_unit)

        query += " ORDER BY hr.recorded_on ASC, hr.recorded_time ASC, hr.id ASC"
        rows = conn.execute(query, params).fetchall()
        readings = [dict(r) for r in rows]

    count = len(readings)
    has_data = count > 0
    has_sufficient_data = count >= 2

    # Compute summary statistics without fabricating data
    summary = {}
    if has_data:
        if selected_type == "Blood Pressure":
            sys_vals = [r["systolic"] for r in readings if r["systolic"] is not None]
            dia_vals = [r["diastolic"] for r in readings if r["diastolic"] is not None]
            if sys_vals and dia_vals:
                summary = {
                    "systolic_min": min(sys_vals),
                    "systolic_max": max(sys_vals),
                    "systolic_avg": round(sum(sys_vals) / len(sys_vals), 1),
                    "diastolic_min": min(dia_vals),
                    "diastolic_max": max(dia_vals),
                    "diastolic_avg": round(sum(dia_vals) / len(dia_vals), 1),
                    "unit": "mmHg",
                }
        else:
            nums = [r["numeric_value"] for r in readings if r["numeric_value"] is not None]
            if nums:
                summary = {
                    "min_value": min(nums),
                    "max_value": max(nums),
                    "avg_value": round(sum(nums) / len(nums), 1),
                    "unit": selected_unit,
                }

    return {
        "has_data": has_data,
        "has_sufficient_data": has_sufficient_data,
        "available_types": available_types,
        "available_units": available_units,
        "selected_type": selected_type,
        "selected_unit": selected_unit,
        "readings": readings,
        "count": count,
        "summary": summary,
        "start_date": s_date,
        "end_date": e_date,
        "safety_disclaimer": ANALYTICS_SAFETY_NOTICE,
    }


# =============================================================================
# APPOINTMENT ANALYTICS
# =============================================================================

def get_appointment_analytics(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    status_filter: str = "all",
    user: dict = None,
) -> dict:
    """
    Calculates appointment analytics:
    - Total appointments, upcoming, completed, cancelled, missed.
    - Cancelled appointments are NEVER counted as completed.
    - Monthly appointment history and type distribution.
    - Date range and status filtering.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)

    with get_connection() as conn:
        base_query = """
            SELECT a.*, u.name as doctor_name_display
            FROM appointments a
            LEFT JOIN users u ON a.created_by = u.id
            WHERE a.elderly_user_id = ?
              AND a.appointment_date BETWEEN ? AND ?
        """
        params = [elderly_user_id, s_date, e_date]

        if status_filter and status_filter.lower() != "all":
            base_query += " AND a.status = ?"
            params.append(status_filter.lower())

        base_query += " ORDER BY a.appointment_date ASC, a.appointment_time ASC"
        rows = conn.execute(base_query, params).fetchall()
        appointments = [dict(r) for r in rows]

        # Calculate counts across the date window (regardless of current status filter)
        count_rows = conn.execute(
            """SELECT status, COUNT(*) as count
               FROM appointments
               WHERE elderly_user_id = ? AND appointment_date BETWEEN ? AND ?
               GROUP BY status""",
            (elderly_user_id, s_date, e_date),
        ).fetchall()

        counts = {
            "total": 0,
            "upcoming": 0,
            "completed": 0,
            "cancelled": 0,
            "missed": 0,
        }
        for cr in count_rows:
            st = cr["status"]
            cnt = cr["count"]
            counts["total"] += cnt
            if st in counts:
                counts[st] = cnt

        # Monthly history distribution
        month_rows = conn.execute(
            """SELECT substr(appointment_date, 1, 7) as month_key,
                      COUNT(*) as total,
                      SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                      SUM(CASE WHEN status = 'upcoming' THEN 1 ELSE 0 END) as upcoming,
                      SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                      SUM(CASE WHEN status = 'missed' THEN 1 ELSE 0 END) as missed
               FROM appointments
               WHERE elderly_user_id = ? AND appointment_date BETWEEN ? AND ?
               GROUP BY month_key
               ORDER BY month_key ASC""",
            (elderly_user_id, s_date, e_date),
        ).fetchall()
        monthly_distribution = [dict(mr) for mr in month_rows]

        # Appointment type distribution
        type_rows = conn.execute(
            """SELECT appointment_type, COUNT(*) as count
               FROM appointments
               WHERE elderly_user_id = ? AND appointment_date BETWEEN ? AND ?
               GROUP BY appointment_type
               ORDER BY count DESC""",
            (elderly_user_id, s_date, e_date),
        ).fetchall()
        total_types = sum(tr["count"] for tr in type_rows)
        type_distribution = [
            {
                "appointment_type": tr["appointment_type"],
                "count": tr["count"],
                "percentage": round((tr["count"] / total_types) * 100.0, 1) if total_types > 0 else 0.0,
            }
            for tr in type_rows
        ]

    return {
        "has_data": counts["total"] > 0,
        "total_appointments": counts["total"],
        "upcoming_count": counts["upcoming"],
        "completed_count": counts["completed"],
        "cancelled_count": counts["cancelled"],
        "missed_count": counts["missed"],
        "monthly_distribution": monthly_distribution,
        "type_distribution": type_distribution,
        "appointments": appointments,
        "start_date": s_date,
        "end_date": e_date,
    }


# =============================================================================
# CARE ACTIVITY ANALYTICS
# =============================================================================

def get_care_activity_analytics(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    category_filter: str = "all",
    limit: int = 100,
    user: dict = None,
) -> dict:
    """
    Retrieves care activity breakdown and chronological audit trail:
    - Categories: Medication activity, Reminders/Escalations, Care Circle, Notes, Emergency SOS.
    - Filters by event category, date range, and elderly profile.
    - Privacy enforcement: For family viewers, notes marked caregivers_only are sanitized.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)
    is_family = user and user.get("role") == "family"

    query = """
        SELECT al.id, al.elderly_user_id, al.action, al.details, al.created_at,
               u.name as actor_name, u.role as actor_role
        FROM activity_logs al
        LEFT JOIN users u ON al.actor_user_id = u.id
        WHERE al.elderly_user_id = ?
          AND date(al.created_at) BETWEEN date(?) AND date(?)
    """
    params = [elderly_user_id, s_date, e_date]

    # Category filter
    if category_filter and category_filter.lower() != "all":
        cat = category_filter.lower()
        if cat in ("medication", "dose"):
            query += " AND (al.action LIKE '%Medication%' OR al.action LIKE '%Dose%')"
        elif cat in ("reminder", "alert", "escalation"):
            query += " AND (al.action LIKE '%Reminder%' OR al.action LIKE '%Escalation%' OR al.action LIKE '%Overdue%')"
        elif cat in ("circle", "caregiver", "invitation"):
            query += " AND (al.action LIKE '%Circle%' OR al.action LIKE '%Caregiver%' OR al.action LIKE '%Invitation%')"
        elif cat in ("notes", "care_notes"):
            query += " AND al.action LIKE '%Note%'"
        elif cat in ("emergency", "sos"):
            query += " AND (al.action LIKE '%Emergency%' OR al.action LIKE '%SOS%')"
        else:
            query += " AND LOWER(al.action) = LOWER(?)"
            params.append(category_filter)

    query += " ORDER BY al.created_at DESC, al.id DESC LIMIT ?"
    params.append(int(limit))

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

        # Category distribution counts across window
        cat_rows = conn.execute(
            """SELECT action, COUNT(*) as count FROM activity_logs
               WHERE elderly_user_id = ? AND date(created_at) BETWEEN date(?) AND date(?)
               GROUP BY action""",
            (elderly_user_id, s_date, e_date),
        ).fetchall()

    activities = []
    for r in rows:
        act = dict(r)
        # Privacy enforcement for family viewers
        if is_family and "caregivers_only" in act.get("details", "").lower():
            act["details"] = "Private care note recorded by caregiver (caregivers-only)."
        activities.append(act)

    # Classify actions into high-level categories
    category_counts = {
        "Medication & Doses": 0,
        "Reminders & Alerts": 0,
        "Care Circle": 0,
        "Care Notes": 0,
        "Emergency SOS": 0,
        "Other Care Activities": 0,
    }
    for cr in cat_rows:
        act_name = cr["action"]
        c_cnt = cr["count"]
        if "Medication" in act_name or "Dose" in act_name:
            category_counts["Medication & Doses"] += c_cnt
        elif "Reminder" in act_name or "Escalation" in act_name or "Overdue" in act_name:
            category_counts["Reminders & Alerts"] += c_cnt
        elif "Circle" in act_name or "Caregiver" in act_name or "Invitation" in act_name:
            category_counts["Care Circle"] += c_cnt
        elif "Note" in act_name:
            category_counts["Care Notes"] += c_cnt
        elif "Emergency" in act_name or "SOS" in act_name:
            category_counts["Emergency SOS"] += c_cnt
        else:
            category_counts["Other Care Activities"] += c_cnt

    return {
        "has_data": len(activities) > 0,
        "total_activities": len(activities),
        "activities": activities,
        "category_counts": category_counts,
        "start_date": s_date,
        "end_date": e_date,
    }


# =============================================================================
# CSV REPORT EXPORT
# =============================================================================

def sanitize_csv_cell(val) -> str:
    """
    Sanitizes values against CSV Formula Injection (OWASP CWE-1236).
    Prepends a single quote if string begins with =, +, -, @, tab, or carriage return.
    """
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def generate_analytics_csv_report(
    elderly_user_id: int,
    start_date: str = None,
    end_date: str = None,
    period: str = "last_30_days",
    user: dict = None,
) -> str:
    """
    Generates a structured, RFC-4180 compliant CSV analytics report:
    - Contains: Metadata, Executive Summary, Medication Adherence, Appointments, Health Readings, Activity Logs.
    - Sanitizes cell data against CSV formula injection (OWASP CWE-1236).
    - Omits sensitive authentication credentials (passwords, salts, tokens).
    - Encoded in UTF-8; handles empty datasets gracefully with informative headers.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    s_date, e_date = resolve_date_range(period, start_date, end_date)

    with get_connection() as conn:
        elderly_row = conn.execute(
            "SELECT name, email, phone FROM users WHERE id = ?",
            (elderly_user_id,),
        ).fetchone()
        elderly_name = elderly_row["name"] if elderly_row else f"Patient #{elderly_user_id}"

    # Fetch module analytics
    overview = get_analytics_overview(elderly_user_id, s_date, e_date, user=user)
    meds_data = get_medication_adherence_analytics(elderly_user_id, s_date, e_date, user=user)
    appts_data = get_appointment_analytics(elderly_user_id, s_date, e_date, user=user)
    health_data = get_health_trend_analytics(elderly_user_id, start_date=s_date, end_date=e_date, user=user)
    act_data = get_care_activity_analytics(elderly_user_id, s_date, e_date, user=user)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    def write_safe_row(cells):
        writer.writerow([sanitize_csv_cell(c) for c in cells])

    # 1. Report Metadata
    write_safe_row(["DEARLY - HEALTHCARE ANALYTICS & CARE SUMMARY REPORT"])
    write_safe_row(["Patient Name", elderly_name])
    write_safe_row(["Patient ID", elderly_user_id])
    write_safe_row(["Report Period Start", s_date])
    write_safe_row(["Report Period End", e_date])
    write_safe_row(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    if user:
        write_safe_row(["Generated By", f"{user.get('name', 'User')} ({user.get('role', 'authorized')})"])
    write_safe_row(["Safety Notice", ANALYTICS_SAFETY_NOTICE])
    write_safe_row([])

    # 2. Executive KPI Overview
    write_safe_row(["--- SECTION 1: EXECUTIVE CARE SUMMARY ---"])
    write_safe_row(["Metric", "Value", "Notes"])
    adh_str = f"{overview['adherence_percentage']}%" if overview["adherence_percentage"] is not None else "N/A (No due doses)"
    write_safe_row(["Overall Medication Adherence", adh_str, "Calculated as (Taken / Total Due) * 100"])
    write_safe_row(["Total Doses Due", overview["total_due_doses"], "Future scheduled doses excluded"])
    write_safe_row(["Total Doses Taken", overview["taken_doses"], "Confirmed taken"])
    write_safe_row(["Total Doses Skipped", overview["skipped_doses"], "Marked skipped"])
    write_safe_row(["Total Doses Overdue", overview["overdue_doses"], "Past scheduled time"])
    write_safe_row(["Upcoming Appointments", overview["upcoming_appointments"], "Scheduled future visits"])
    write_safe_row(["Completed Appointments", overview["completed_appointments"], "Visits marked completed"])
    write_safe_row(["Recorded Health Readings", overview["health_readings_count"], "Vitals logged in period"])
    write_safe_row(["Total Care Activities", overview["recent_activities_count"], "Care log audit count"])
    write_safe_row([])

    # 3. Medication Breakdown
    write_safe_row(["--- SECTION 2: MEDICATION-WISE ADHERENCE BREAKDOWN ---"])
    if meds_data["has_data"] and meds_data["medication_breakdown"]:
        write_safe_row(["Medicine Name", "Dosage", "Total Due", "Taken", "Skipped", "Overdue", "Adherence (%)", "Status"])
        for m in meds_data["medication_breakdown"]:
            m_adh = f"{m['adherence_percentage']}%" if m["adherence_percentage"] is not None else "N/A"
            m_st = "Active" if m.get("active", 1) else "Inactive"
            write_safe_row([
                m["medicine_name"],
                m["dosage"],
                m["total_due"],
                m["taken"],
                m["skipped"],
                m["overdue"],
                m_adh,
                m_st,
            ])
    else:
        write_safe_row(["No medication records available for this period."])
    write_safe_row([])

    # 4. Appointments Summary
    write_safe_row(["--- SECTION 3: DOCTOR APPOINTMENTS ---"])
    if appts_data["appointments"]:
        write_safe_row(["Date", "Time", "Doctor Name", "Specialization", "Hospital / Clinic", "Type", "Status", "Notes"])
        for a in appts_data["appointments"]:
            write_safe_row([
                a.get("appointment_date", ""),
                a.get("appointment_time", ""),
                a.get("doctor_name", ""),
                a.get("specialization", ""),
                a.get("hospital", ""),
                a.get("appointment_type", ""),
                a.get("status", ""),
                a.get("notes", ""),
            ])
    else:
        write_safe_row(["No appointment records available for this period."])
    write_safe_row([])

    # 5. Health Readings Summary
    write_safe_row(["--- SECTION 4: HEALTH VITALS & MEASUREMENTS ---"])
    if health_data["readings"]:
        write_safe_row(["Date", "Time", "Measurement Type", "Reading Value", "Unit", "Context", "Recorded By", "Corrected"])
        for hr in health_data["readings"]:
            write_safe_row([
                hr.get("recorded_on", ""),
                hr.get("recorded_time", ""),
                hr.get("reading_type", ""),
                hr.get("reading_value", ""),
                hr.get("unit", ""),
                hr.get("context", ""),
                hr.get("recorded_by_name", "Caregiver"),
                "Yes" if hr.get("is_corrected") else "No",
            ])
    else:
        write_safe_row(["No health reading records available for this period."])
    write_safe_row([])

    # 6. Care Activity Log
    write_safe_row(["--- SECTION 5: CARE ACTIVITY AUDIT TRAIL ---"])
    if act_data["activities"]:
        write_safe_row(["Timestamp", "Action Category", "Details", "Actor Name", "Actor Role"])
        for act in act_data["activities"]:
            write_safe_row([
                act.get("created_at", ""),
                act.get("action", ""),
                act.get("details", ""),
                act.get("actor_name", "System"),
                act.get("actor_role", ""),
            ])
    else:
        write_safe_row(["No care activities recorded for this period."])

    return output.getvalue()
