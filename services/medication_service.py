import re
import sqlite3
from datetime import datetime, date, timedelta
from database import get_connection
from services.activity_service import log_activity
from services.permissions import enforce_elderly_access, can_manage_elderly_care, can_access_elderly_record

TIME_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_medication_input(
    medicine_name: str,
    dosage: str,
    medication_type: str,
    frequency: str,
    schedule_time: str,
    start_date: str,
    end_date: str = None,
) -> tuple[bool, str]:
    """
    Validates required fields and dates for medication CRUD.
    Returns (is_valid, error_message).
    """
    if not medicine_name or len(medicine_name.strip()) < 2:
        return False, "Medication name must be at least 2 characters."

    if not dosage or not dosage.strip():
        return False, "Dosage is required (e.g. '1 tablet' or '5 ml')."

    if not medication_type or not medication_type.strip():
        return False, "Medication type is required (e.g. Tablet, Capsule, Syrup)."

    if not frequency or not frequency.strip():
        return False, "Dosing frequency is required."

    if not schedule_time or not TIME_REGEX.match(schedule_time.strip()):
        return False, "Scheduled time must be in 24-hour HH:MM format (e.g. 08:30 or 20:00)."

    if not start_date or not DATE_REGEX.match(start_date.strip()):
        return False, "Start date must be in YYYY-MM-DD format."

    try:
        s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        return False, "Start date is not a valid calendar date."

    if end_date and end_date.strip():
        if not DATE_REGEX.match(end_date.strip()):
            return False, "End date must be in YYYY-MM-DD format if provided."
        try:
            e_date = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
            if e_date < s_date:
                return False, "End date cannot be earlier than start date."
        except ValueError:
            return False, "End date is not a valid calendar date."

    return True, ""


def add_medication(
    elderly_user_id: int,
    medicine_name: str,
    dosage: str,
    schedule_time: str,
    medication_type: str = "Tablet",
    frequency: str = "Daily",
    start_date: str = None,
    end_date: str = None,
    meal_timing: str = "After Meal",
    instructions: str = "",
    purpose: str = "",
    prescribing_doctor: str = "",
    notes: str = "",
    stock_quantity: int = 30,
    created_by: int = None,
    user: dict = None,
) -> int:
    """
    Creates a new medication record after verifying backend write permissions and input constraints.
    """
    # Enforce backend write access if actor user is provided
    if user:
        actor = user
    elif created_by:
        with get_connection() as conn:
            u_row = conn.execute("SELECT id, role, name FROM users WHERE id = ?", (created_by,)).fetchone()
            actor = dict(u_row) if u_row else {"id": created_by, "role": "caregiver"}
    else:
        actor = None
    if actor:
        enforce_elderly_access(actor, elderly_user_id, write_access=True)

    if not start_date:
        start_date = date.today().isoformat()

    is_valid, err = validate_medication_input(
        medicine_name=medicine_name,
        dosage=dosage,
        medication_type=medication_type,
        frequency=frequency,
        schedule_time=schedule_time,
        start_date=start_date,
        end_date=end_date,
    )
    if not is_valid:
        raise ValueError(err)

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO medications
               (elderly_user_id, medicine_name, dosage, medication_type, schedule_time,
                frequency, meal_timing, instructions, purpose, start_date, end_date,
                prescribing_doctor, notes, stock_quantity, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                elderly_user_id,
                medicine_name.strip(),
                dosage.strip(),
                medication_type.strip(),
                schedule_time.strip(),
                frequency.strip(),
                meal_timing.strip() if meal_timing else "After Meal",
                instructions.strip() if instructions else "",
                purpose.strip() if purpose else "",
                start_date.strip(),
                end_date.strip() if end_date and end_date.strip() else None,
                prescribing_doctor.strip() if prescribing_doctor else "",
                notes.strip() if notes else "",
                max(0, int(stock_quantity)),
            ),
        )
        med_id = cursor.lastrowid

    actor_id = actor["id"] if actor else created_by
    if actor_id:
        log_activity(
            elderly_user_id,
            actor_id,
            "Added Medication",
            f"Added {medicine_name.strip()} {dosage.strip()} ({medication_type.strip()}, {schedule_time.strip()})",
        )
    return med_id


def update_medication(
    medication_id: int,
    elderly_user_id: int,
    medicine_name: str,
    dosage: str,
    schedule_time: str,
    medication_type: str = "Tablet",
    frequency: str = "Daily",
    start_date: str = None,
    end_date: str = None,
    meal_timing: str = "After Meal",
    instructions: str = "",
    purpose: str = "",
    prescribing_doctor: str = "",
    notes: str = "",
    stock_quantity: int = 30,
    updated_by: int = None,
    user: dict = None,
) -> bool:
    """
    Updates an existing medication record with permission checks and validation.
    """
    if user:
        actor = user
    elif updated_by:
        with get_connection() as conn:
            u_row = conn.execute("SELECT id, role, name FROM users WHERE id = ?", (updated_by,)).fetchone()
            actor = dict(u_row) if u_row else {"id": updated_by, "role": "caregiver"}
    else:
        actor = None
    if actor:
        enforce_elderly_access(actor, elderly_user_id, write_access=True)

    if not start_date:
        start_date = date.today().isoformat()

    is_valid, err = validate_medication_input(
        medicine_name=medicine_name,
        dosage=dosage,
        medication_type=medication_type,
        frequency=frequency,
        schedule_time=schedule_time,
        start_date=start_date,
        end_date=end_date,
    )
    if not is_valid:
        raise ValueError(err)

    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE medications
               SET medicine_name = ?, dosage = ?, medication_type = ?, schedule_time = ?,
                   frequency = ?, meal_timing = ?, instructions = ?, purpose = ?,
                   start_date = ?, end_date = ?, prescribing_doctor = ?, notes = ?,
                   stock_quantity = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (
                medicine_name.strip(),
                dosage.strip(),
                medication_type.strip(),
                schedule_time.strip(),
                frequency.strip(),
                meal_timing.strip() if meal_timing else "After Meal",
                instructions.strip() if instructions else "",
                purpose.strip() if purpose else "",
                start_date.strip(),
                end_date.strip() if end_date and end_date.strip() else None,
                prescribing_doctor.strip() if prescribing_doctor else "",
                notes.strip() if notes else "",
                max(0, int(stock_quantity)),
                medication_id,
                elderly_user_id,
            ),
        )
        if cursor.rowcount == 0:
            return False

    actor_id = actor["id"] if actor else updated_by
    if actor_id:
        log_activity(
            elderly_user_id,
            actor_id,
            "Updated Medication",
            f"Updated details for {medicine_name.strip()} {dosage.strip()}",
        )
    return True


def deactivate_medication(
    medication_id: int,
    elderly_user_id: int,
    deactivated_by: int = None,
    user: dict = None,
) -> bool:
    """
    Deactivates a medication without deleting its historical logs.
    """
    actor = user or ({"id": deactivated_by, "role": "caregiver"} if deactivated_by else None)
    if actor:
        enforce_elderly_access(actor, elderly_user_id, write_access=True)

    with get_connection() as conn:
        med = conn.execute(
            "SELECT medicine_name FROM medications WHERE id = ? AND elderly_user_id = ?",
            (medication_id, elderly_user_id),
        ).fetchone()
        if not med:
            return False

        name = med["medicine_name"]
        conn.execute(
            "UPDATE medications SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND elderly_user_id = ?",
            (medication_id, elderly_user_id),
        )

    actor_id = actor["id"] if actor else deactivated_by
    if actor_id:
        log_activity(
            elderly_user_id,
            actor_id,
            "Discontinued Medication",
            f"Medication {name} was deactivated. Past dose history is preserved.",
        )
    return True


def activate_medication(
    medication_id: int,
    elderly_user_id: int,
    activated_by: int = None,
    user: dict = None,
) -> bool:
    """Reactivates an inactive medication."""
    actor = user or ({"id": activated_by, "role": "caregiver"} if activated_by else None)
    if actor:
        enforce_elderly_access(actor, elderly_user_id, write_access=True)

    with get_connection() as conn:
        med = conn.execute(
            "SELECT medicine_name FROM medications WHERE id = ? AND elderly_user_id = ?",
            (medication_id, elderly_user_id),
        ).fetchone()
        if not med:
            return False

        name = med["medicine_name"]
        conn.execute(
            "UPDATE medications SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND elderly_user_id = ?",
            (medication_id, elderly_user_id),
        )

    actor_id = actor["id"] if actor else activated_by
    if actor_id:
        log_activity(
            elderly_user_id,
            actor_id,
            "Reactivated Medication",
            f"Medication {name} reactivated into active schedule.",
        )
    return True


def delete_medication(
    medication_id: int,
    elderly_user_id: int,
    deleted_by: int = None,
    confirmed: bool = False,
    user: dict = None,
) -> bool:
    """
    Deletes a medication record only if confirmed and authorized.
    To preserve medication history, if dose logs exist, recommends deactivation.
    """
    if not confirmed:
        raise ValueError("Deletion requires explicit user confirmation.")

    actor = user or ({"id": deleted_by, "role": "caregiver"} if deleted_by else None)
    if actor:
        enforce_elderly_access(actor, elderly_user_id, write_access=True)

    with get_connection() as conn:
        med = conn.execute(
            "SELECT medicine_name FROM medications WHERE id = ? AND elderly_user_id = ?",
            (medication_id, elderly_user_id),
        ).fetchone()
        if not med:
            return False

        name = med["medicine_name"]

        # Check if medication has recorded logs
        log_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM medication_logs WHERE medication_id = ?",
            (medication_id,),
        ).fetchone()["cnt"]

        if log_count > 0:
            # Preserves medication history when discontinued instead of deleting logs
            conn.execute(
                "UPDATE medications SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND elderly_user_id = ?",
                (medication_id, elderly_user_id),
            )
            action_desc = f"Medication {name} has {log_count} historical dose records; archived as inactive to preserve clinical audit trail."
        else:
            conn.execute(
                "DELETE FROM medications WHERE id = ? AND elderly_user_id = ?",
                (medication_id, elderly_user_id),
            )
            action_desc = f"Removed medication {name} (no prior logs)."

    actor_id = actor["id"] if actor else deleted_by
    if actor_id:
        log_activity(
            elderly_user_id,
            actor_id,
            "Deleted/Archived Medication",
            action_desc,
        )
    return True


def get_medications(
    elderly_user_id: int,
    status_filter: str = "all",
    active_only: bool = False,
    user: dict = None,
) -> list[dict]:
    """
    Returns filtered medications for an elderly individual:
    status_filter: 'all' | 'active' | 'inactive'
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    with get_connection() as conn:
        query = """SELECT id, elderly_user_id, medicine_name, dosage, medication_type,
                          schedule_time, frequency, meal_timing, instructions, start_date,
                          end_date, active, purpose, prescribing_doctor, notes, stock_quantity,
                          created_at, updated_at
                   FROM medications WHERE elderly_user_id = ?"""
        params = [elderly_user_id]

        if active_only or status_filter == "active":
            query += " AND active = 1"
        elif status_filter == "inactive":
            query += " AND active = 0"

        query += " ORDER BY schedule_time ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_medication_by_id(medication_id: int, elderly_user_id: int = None) -> dict | None:
    """Fetches details of a single medication."""
    with get_connection() as conn:
        query = """SELECT id, elderly_user_id, medicine_name, dosage, medication_type,
                          schedule_time, frequency, meal_timing, instructions, start_date,
                          end_date, active, purpose, prescribing_doctor, notes, stock_quantity,
                          created_at, updated_at
                   FROM medications WHERE id = ?"""
        params = [medication_id]
        if elderly_user_id:
            query += " AND elderly_user_id = ?"
            params.append(elderly_user_id)
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def get_time_period(time_str: str) -> str:
    """
    Maps 24h time HH:MM to day period:
    Morning: 05:00 - 11:59
    Afternoon: 12:00 - 16:59
    Evening: 17:00 - 20:59
    Night: 21:00 - 04:59
    """
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M").time()
        hour = t.hour
        if 5 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 21:
            return "Evening"
        else:
            return "Night"
    except Exception:
        return "Morning"


def get_today_schedule(elderly_user_id: int, target_date: str = None, user: dict = None) -> list[dict]:
    """
    Returns flat list of scheduled medications for a target date with dose status.
    Excludes medications outside active date window (start_date/end_date).
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    if not target_date:
        target_date = date.today().isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT m.id as medication_id, m.medicine_name, m.dosage, m.medication_type,
                      m.schedule_time, m.frequency, m.meal_timing, m.instructions, m.purpose,
                      m.prescribing_doctor, m.notes as med_notes, m.stock_quantity,
                      m.start_date, m.end_date, m.active,
                      COALESCE(ml.status, 'pending') as status,
                      ml.id as log_id, ml.notes as log_notes, ml.actual_action_time, ml.recorded_at,
                      u.name as recorded_by_name
               FROM medications m
               LEFT JOIN medication_logs ml ON m.id = ml.medication_id AND ml.scheduled_date = ?
               LEFT JOIN users u ON ml.recorded_by = u.id
               WHERE m.elderly_user_id = ? AND m.active = 1
                 AND (m.start_date IS NULL OR m.start_date <= ?)
                 AND (m.end_date IS NULL OR m.end_date = '' OR m.end_date >= ?)
               ORDER BY m.schedule_time ASC""",
            (target_date, elderly_user_id, target_date, target_date),
        ).fetchall()

    schedule = []
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")
    is_today = (target_date == date.today().isoformat())

    for r in rows:
        item = dict(r)
        sched_time = item["schedule_time"]
        is_overdue = False

        if is_today and item["status"] == "pending":
            if sched_time < current_time_str:
                is_overdue = True
        elif target_date < date.today().isoformat() and item["status"] == "pending":
            is_overdue = True

        item["is_overdue"] = is_overdue
        item["period"] = get_time_period(sched_time)

        # Friendly formatted time
        try:
            t_obj = datetime.strptime(sched_time, "%H:%M")
            item["formatted_time"] = t_obj.strftime("%I:%M %p")
        except Exception:
            item["formatted_time"] = sched_time

        schedule.append(item)

    return schedule


def get_grouped_daily_schedule(elderly_user_id: int, target_date: str = None, user: dict = None) -> dict:
    """
    Groups the day's scheduled doses into Morning, Afternoon, Evening, and Night.
    """
    schedule = get_today_schedule(elderly_user_id, target_date, user=user)
    grouped = {
        "Morning": [],
        "Afternoon": [],
        "Evening": [],
        "Night": [],
    }
    for item in schedule:
        period = item.get("period", "Morning")
        if period in grouped:
            grouped[period].append(item)
        else:
            grouped["Morning"].append(item)
    return grouped


def record_dose_status(
    medication_id: int,
    elderly_user_id: int,
    scheduled_date: str,
    scheduled_time: str,
    status: str,
    recorded_by: int,
    notes: str = "",
    actual_action_time: str = None,
    user: dict = None,
) -> bool:
    """
    Records or updates the status of a specific scheduled dose.
    Prevents duplicate dose records using SQLite ON CONFLICT(medication_id, scheduled_date, scheduled_time).
    Verifies backend authorization:
    - Elderly can record for self.
    - Caregiver can record for linked ward with editor access.
    - Family cannot record unless authorized as editor.
    """
    if user:
        actor = user
    elif recorded_by:
        with get_connection() as conn:
            u_row = conn.execute("SELECT id, role, name FROM users WHERE id = ?", (recorded_by,)).fetchone()
            actor = dict(u_row) if u_row else {"id": recorded_by, "role": "caregiver"}
    else:
        actor = None
    if actor:
        # Check if user is elderly recording their own dose, or caregiver with editor access
        if actor.get("role") == "elderly":
            if actor["id"] != elderly_user_id:
                raise PermissionError("Elderly users cannot record medication doses for another person.")
        else:
            enforce_elderly_access(actor, elderly_user_id, write_access=True)

    valid_statuses = ("taken", "missed", "skipped", "pending")
    status_lower = status.strip().lower()
    if status_lower not in valid_statuses:
        raise ValueError(f"Invalid dose status '{status}'. Must be one of {valid_statuses}")

    if not actual_action_time:
        actual_action_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, status FROM medication_logs WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ?",
            (medication_id, scheduled_date, scheduled_time),
        ).fetchone()

        prev_status = existing["status"] if existing else None

        # Idempotent Upsert to prevent duplicate dose records
        conn.execute(
            """INSERT INTO medication_logs
               (medication_id, scheduled_date, scheduled_time, actual_action_time, status, notes, recorded_by, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(medication_id, scheduled_date, scheduled_time) DO UPDATE SET
                   status = excluded.status,
                   actual_action_time = excluded.actual_action_time,
                   notes = excluded.notes,
                   recorded_by = excluded.recorded_by,
                   recorded_at = CURRENT_TIMESTAMP""",
            (medication_id, scheduled_date, scheduled_time, actual_action_time, status_lower, notes.strip(), recorded_by),
        )

        # Stock management: decrement on taken, increment if reverting
        if status_lower == "taken" and prev_status != "taken":
            conn.execute(
                "UPDATE medications SET stock_quantity = MAX(0, stock_quantity - 1) WHERE id = ?",
                (medication_id,),
            )
            # Resolve any active caregiver escalation for this scheduled dose
            conn.execute(
                """UPDATE caregiver_escalations
                   SET status = 'resolved'
                   WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ? AND status = 'pending'""",
                (medication_id, scheduled_date, scheduled_time),
            )
        elif prev_status == "taken" and status_lower != "taken":
            conn.execute(
                "UPDATE medications SET stock_quantity = stock_quantity + 1 WHERE id = ?",
                (medication_id,),
            )

        med = conn.execute(
            "SELECT medicine_name, dosage FROM medications WHERE id = ?",
            (medication_id,),
        ).fetchone()
        med_name = f"{med['medicine_name']} ({med['dosage']})" if med else f"Medication #{medication_id}"

    action_label = {
        "taken": "Dose Confirmed Taken",
        "missed": "Dose Marked as Missed",
        "skipped": "Dose Marked as Skipped",
        "pending": "Dose Reset to Pending",
    }.get(status_lower, "Dose Status Updated")

    log_activity(
        elderly_user_id,
        recorded_by,
        action_label,
        f"{med_name} scheduled for {scheduled_time} marked as '{status_lower.upper()}'. {notes}".strip(),
    )
    return True


def get_adherence_metrics(elderly_user_id: int, days: int = 7, user: dict = None) -> dict:
    """
    Computes medication adherence summary strictly excluding future doses:
    Adherence % = (Taken doses / Total due doses) * 100
    Where Total due doses = doses scheduled on or before current time whose time has passed.
    If no doses are due, returns has_data=False and adherence_percentage=None with helpful empty state.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    today = date.today()
    start_date = (today - timedelta(days=days - 1)).isoformat()
    end_date = today.isoformat()
    now = datetime.now()
    current_time_str = now.strftime("%H:%M")

    with get_connection() as conn:
        # Fetch active medications to know valid regimens
        meds = conn.execute(
            "SELECT id, medicine_name, dosage, stock_quantity FROM medications WHERE elderly_user_id = ? AND active = 1",
            (elderly_user_id,),
        ).fetchall()

        # Fetch logs in window
        logs = conn.execute(
            """SELECT ml.scheduled_date, ml.scheduled_time, ml.status, m.id as medication_id
               FROM medication_logs ml
               JOIN medications m ON ml.medication_id = m.id
               WHERE m.elderly_user_id = ? AND ml.scheduled_date BETWEEN ? AND ?""",
            (elderly_user_id, start_date, end_date),
        ).fetchall()

        low_stock = [dict(m) for m in meds if m["stock_quantity"] <= 7]

    total_taken = 0
    total_missed = 0
    total_skipped = 0
    total_due = 0
    future_doses_count = 0

    daily_data = {}
    for i in range(days):
        d_str = (today - timedelta(days=days - 1 - i)).isoformat()
        daily_data[d_str] = {"taken": 0, "missed": 0, "skipped": 0, "pending": 0}

    for log in logs:
        log_d = log["scheduled_date"]
        log_t = log["scheduled_time"]
        status = log["status"]

        # Check if dose is in the future
        is_future = False
        if log_d > end_date:
            is_future = True
        elif log_d == end_date and log_t > current_time_str:
            is_future = True

        if is_future:
            future_doses_count += 1
            continue  # Strictly exclude future doses from due calculations

        if log_d in daily_data:
            if status in daily_data[log_d]:
                daily_data[log_d][status] += 1

        if status == "taken":
            total_taken += 1
            total_due += 1
        elif status == "missed":
            total_missed += 1
            total_due += 1
        elif status == "skipped":
            total_skipped += 1
            total_due += 1
        elif status == "pending":
            # Past or due pending counts towards due
            total_due += 1

    if total_due > 0:
        adherence_pct = round((total_taken / total_due) * 100, 1)
        has_data = True
    else:
        adherence_pct = None
        has_data = False

    return {
        "has_data": has_data,
        "adherence_percentage": adherence_pct,
        "total_due": total_due,
        "total_taken": total_taken,
        "total_missed": total_missed,
        "total_skipped": total_skipped,
        "total_pending": max(0, total_due - (total_taken + total_missed + total_skipped)),
        "future_excluded": future_doses_count,
        "daily_breakdown": daily_data,
        "low_stock_meds": low_stock,
    }


def get_overdue_doses(elderly_user_id: int, user: dict = None) -> list[dict]:
    """
    Identifies in-app overdue doses for today where:
    - schedule_time < current local time
    - status is not 'taken' and not 'skipped'
    Excludes future doses (scheduled time >= current local time).
    Never advises taking extra doses or doubling medication.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    today_str = date.today().isoformat()
    current_time_str = datetime.now().strftime("%H:%M")

    with get_connection() as conn:
        # Get elderly name
        user_row = conn.execute("SELECT name FROM users WHERE id = ?", (elderly_user_id,)).fetchone()
        elderly_name = user_row["name"] if user_row else "Patient"

        rows = conn.execute(
            """SELECT m.id as medication_id, m.medicine_name, m.dosage, m.medication_type,
                      m.schedule_time, m.instructions, m.meal_timing,
                      COALESCE(ml.status, 'pending') as status
               FROM medications m
               LEFT JOIN medication_logs ml ON m.id = ml.medication_id AND ml.scheduled_date = ?
               WHERE m.elderly_user_id = ? AND m.active = 1
                 AND (m.start_date IS NULL OR m.start_date <= ?)
                 AND (m.end_date IS NULL OR m.end_date = '' OR m.end_date >= ?)
                 AND m.schedule_time < ?
               ORDER BY m.schedule_time ASC""",
            (today_str, elderly_user_id, today_str, today_str, current_time_str),
        ).fetchall()

    overdue = []
    for r in rows:
        st = r["status"]
        if st not in ("taken", "skipped"):
            item = dict(r)
            item["elderly_name"] = elderly_name
            try:
                t_obj = datetime.strptime(item["schedule_time"], "%H:%M")
                item["formatted_time"] = t_obj.strftime("%I:%M %p")
            except Exception:
                item["formatted_time"] = item["schedule_time"]
            overdue.append(item)

    return overdue
