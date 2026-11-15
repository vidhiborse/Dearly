import re
import sqlite3
from datetime import date, datetime, timedelta
from database import get_connection
from services.activity_service import log_activity
from services.permissions import enforce_elderly_access, can_manage_elderly_care


def parse_appointment_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parses date and time strings into a datetime object."""
    if not date_str or not time_str:
        return None
    d_clean = date_str.strip()
    t_clean = time_str.strip().upper()

    formats = [
        ("%Y-%m-%d %I:%M %p", f"{d_clean} {t_clean}"),
        ("%Y-%m-%d %H:%M", f"{d_clean} {t_clean}"),
        ("%Y-%m-%d %I:%M%p", f"{d_clean} {t_clean}"),
    ]
    for fmt, val in formats:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def validate_appointment_input(
    doctor_name: str,
    hospital: str,
    appointment_date: str,
    appointment_time: str,
    allow_past: bool = False,
):
    """Validates required appointment parameters and dates."""
    if not doctor_name or len(doctor_name.strip()) < 2:
        raise ValueError("Doctor's name is required (minimum 2 characters).")

    if not hospital or len(hospital.strip()) < 2:
        raise ValueError("Hospital or clinic name is required (minimum 2 characters).")

    if not appointment_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", appointment_date.strip()):
        raise ValueError("Appointment date must be in YYYY-MM-DD format.")

    try:
        appt_d = datetime.strptime(appointment_date.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid calendar date.")

    if not allow_past and appt_d < date.today():
        raise ValueError("Appointment date cannot be in the past.")

    if not appointment_time or len(appointment_time.strip()) < 3:
        raise ValueError("Appointment time is required.")

    parsed_dt = parse_appointment_datetime(appointment_date, appointment_time)
    if not parsed_dt:
        raise ValueError("Invalid appointment time format. Use '10:30 AM' or '14:30'.")

    if not allow_past and parsed_dt < datetime.now():
        raise ValueError("Appointment scheduled time has already passed.")


def add_appointment(
    elderly_user_id: int,
    doctor_name: str,
    hospital: str,
    appointment_date: str,
    appointment_time: str,
    purpose: str = "",
    specialization: str = "",
    appointment_type: str = "General check-up",
    location: str = "",
    reason: str = "",
    notes: str = "",
    created_by: int = None,
    user: dict = None,
    allow_past: bool = False,
) -> int:
    """
    Creates a new doctor appointment for an elderly profile with server-side validation and authorization.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    validate_appointment_input(doctor_name, hospital, appointment_date, appointment_time, allow_past=allow_past)

    clean_reason = reason.strip() or purpose.strip()
    clean_type = appointment_type.strip() if appointment_type else "General check-up"

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO appointments
               (elderly_user_id, doctor_name, specialization, hospital, appointment_date, appointment_time,
                appointment_type, location, reason, purpose, notes, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?, CURRENT_TIMESTAMP)""",
            (
                elderly_user_id,
                doctor_name.strip(),
                specialization.strip(),
                hospital.strip(),
                appointment_date.strip(),
                appointment_time.strip(),
                clean_type,
                location.strip(),
                clean_reason,
                clean_reason,
                notes.strip(),
                created_by or (user.get("id") if user else None),
            ),
        )
        appt_id = cursor.lastrowid

    actor_id = created_by or (user.get("id") if user else elderly_user_id)
    log_activity(
        elderly_user_id,
        actor_id,
        "Scheduled Doctor Appointment",
        f"Scheduled {clean_type} with {doctor_name.strip()} on {appointment_date.strip()} at {appointment_time.strip()} ({hospital.strip()})",
    )
    return appt_id


def get_appointments(
    elderly_user_id: int,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    doctor_search: str = None,
    user: dict = None,
) -> list[dict]:
    """
    Retrieves filtered appointments for an elderly user with creator and updater metadata.
    Enforces server-side read access.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    query = """
        SELECT a.id, a.elderly_user_id, a.doctor_name, a.specialization, a.hospital,
               a.appointment_date, a.appointment_time, a.appointment_type, a.location,
               COALESCE(a.reason, a.purpose) as reason, a.purpose, a.notes, a.post_visit_notes,
               a.status, a.reminder_sent, a.created_by, a.updated_by, a.created_at, a.updated_at,
               u_eld.name as elderly_name,
               u_creator.name as created_by_name,
               u_updater.name as updated_by_name
        FROM appointments a
        JOIN users u_eld ON a.elderly_user_id = u_eld.id
        LEFT JOIN users u_creator ON a.created_by = u_creator.id
        LEFT JOIN users u_updater ON a.updated_by = u_updater.id
        WHERE a.elderly_user_id = ?
    """
    params = [elderly_user_id]

    if status and status.lower() != "all":
        st_clean = status.lower()
        if st_clean == "today":
            today_str = date.today().isoformat()
            query += " AND a.appointment_date = ?"
            params.append(today_str)
        elif st_clean == "upcoming":
            today_str = date.today().isoformat()
            query += " AND a.status = 'upcoming' AND a.appointment_date >= ?"
            params.append(today_str)
        elif st_clean == "past":
            today_str = date.today().isoformat()
            query += " AND (a.appointment_date < ? OR a.status IN ('completed', 'cancelled', 'missed'))"
            params.append(today_str)
        else:
            query += " AND a.status = ?"
            params.append(st_clean)

    if start_date:
        query += " AND a.appointment_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND a.appointment_date <= ?"
        params.append(end_date)

    if doctor_search:
        query += " AND (a.doctor_name LIKE ? OR a.specialization LIKE ? OR a.hospital LIKE ?)"
        term = f"%{doctor_search.strip()}%"
        params.extend([term, term, term])

    query += " ORDER BY a.appointment_date ASC, a.appointment_time ASC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_appointment_by_id(appointment_id: int, user: dict = None) -> dict | None:
    """Fetches full details of a single appointment with access verification."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT a.id, a.elderly_user_id, a.doctor_name, a.specialization, a.hospital,
                      a.appointment_date, a.appointment_time, a.appointment_type, a.location,
                      COALESCE(a.reason, a.purpose) as reason, a.purpose, a.notes, a.post_visit_notes,
                      a.status, a.reminder_sent, a.created_by, a.updated_by, a.created_at, a.updated_at,
                      u_eld.name as elderly_name,
                      u_creator.name as created_by_name,
                      u_updater.name as updated_by_name
               FROM appointments a
               JOIN users u_eld ON a.elderly_user_id = u_eld.id
               LEFT JOIN users u_creator ON a.created_by = u_creator.id
               LEFT JOIN users u_updater ON a.updated_by = u_updater.id
               WHERE a.id = ?""",
            (appointment_id,),
        ).fetchone()

        if not row:
            return None

        appt = dict(row)
        if user:
            enforce_elderly_access(user, appt["elderly_user_id"], write_access=False)
        return appt


def get_next_upcoming_appointment(elderly_user_id: int, user: dict = None) -> dict | None:
    """Retrieves the closest upcoming doctor appointment."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    today_str = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT a.*, u_eld.name as elderly_name
               FROM appointments a
               JOIN users u_eld ON a.elderly_user_id = u_eld.id
               WHERE a.elderly_user_id = ? AND a.status = 'upcoming' AND a.appointment_date >= ?
               ORDER BY a.appointment_date ASC, a.appointment_time ASC
               LIMIT 1""",
            (elderly_user_id, today_str),
        ).fetchone()
        return dict(row) if row else None


def update_appointment(
    appointment_id: int,
    elderly_user_id: int,
    doctor_name: str,
    hospital: str,
    appointment_date: str,
    appointment_time: str,
    specialization: str = "",
    appointment_type: str = "General check-up",
    location: str = "",
    reason: str = "",
    notes: str = "",
    updated_by: int = None,
    user: dict = None,
    allow_past: bool = False,
) -> bool:
    """Updates an existing appointment's details."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    validate_appointment_input(doctor_name, hospital, appointment_date, appointment_time, allow_past=allow_past)

    clean_reason = reason.strip()
    clean_type = appointment_type.strip() if appointment_type else "General check-up"
    actor_id = updated_by or (user.get("id") if user else None)

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET doctor_name = ?, specialization = ?, hospital = ?,
                   appointment_date = ?, appointment_time = ?, appointment_type = ?,
                   location = ?, reason = ?, purpose = ?, notes = ?,
                   updated_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (
                doctor_name.strip(),
                specialization.strip(),
                hospital.strip(),
                appointment_date.strip(),
                appointment_time.strip(),
                clean_type,
                location.strip(),
                clean_reason,
                clean_reason,
                notes.strip(),
                actor_id,
                appointment_id,
                elderly_user_id,
            ),
        )

    log_activity(
        elderly_user_id,
        actor_id,
        "Updated Doctor Appointment",
        f"Updated details for appointment with {doctor_name.strip()} ({appointment_date.strip()})",
    )
    return True


def reschedule_appointment(
    appointment_id: int,
    elderly_user_id: int,
    new_date: str,
    new_time: str,
    reschedule_reason: str = "",
    updated_by: int = None,
    user: dict = None,
) -> bool:
    """
    Reschedules an upcoming appointment to a new date and time.
    Validates that the new date and time are in the future.
    Resets reminder tracking so new reminders fire for the rescheduled date.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    appt = get_appointment_by_id(appointment_id)
    if not appt:
        raise ValueError("Appointment not found.")

    validate_appointment_input(appt["doctor_name"], appt["hospital"], new_date, new_time, allow_past=False)

    actor_id = updated_by or (user.get("id") if user else None)

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET appointment_date = ?, appointment_time = ?, status = 'upcoming',
                   reminder_sent = 0, updated_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (new_date.strip(), new_time.strip(), actor_id, appointment_id, elderly_user_id),
        )
        # Clear prior reminders so new ones will be dispatched
        conn.execute("DELETE FROM appointment_reminders WHERE appointment_id = ?", (appointment_id,))

    reason_txt = f" Reason: {reschedule_reason.strip()}" if reschedule_reason else ""
    log_activity(
        elderly_user_id,
        actor_id,
        "Rescheduled Doctor Appointment",
        f"Rescheduled {appt['doctor_name']} to {new_date.strip()} at {new_time.strip()}.{reason_txt}",
    )
    return True


def cancel_appointment(
    appointment_id: int,
    elderly_user_id: int,
    cancellation_reason: str = "",
    cancelled_by: int = None,
    user: dict = None,
) -> bool:
    """
    Cancels an appointment with audit trail while preserving the clinical record.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    appt = get_appointment_by_id(appointment_id)
    if not appt:
        raise ValueError("Appointment not found.")

    actor_id = cancelled_by or (user.get("id") if user else None)

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET status = 'cancelled', updated_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (actor_id, appointment_id, elderly_user_id),
        )
        # Clean pending reminders for cancelled visit
        conn.execute("DELETE FROM appointment_reminders WHERE appointment_id = ?", (appointment_id,))

    reason_txt = f" Reason: {cancellation_reason.strip()}" if cancellation_reason else ""
    log_activity(
        elderly_user_id,
        actor_id,
        "Cancelled Doctor Appointment",
        f"Cancelled appointment with {appt['doctor_name']} scheduled for {appt['appointment_date']}.{reason_txt}",
    )
    return True


def complete_appointment(
    appointment_id: int,
    elderly_user_id: int,
    post_visit_notes: str = "",
    completed_by: int = None,
    user: dict = None,
) -> bool:
    """
    Marks an appointment as completed and saves post-visit consultation notes.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    appt = get_appointment_by_id(appointment_id)
    if not appt:
        raise ValueError("Appointment not found.")

    actor_id = completed_by or (user.get("id") if user else None)

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET status = 'completed', post_visit_notes = ?,
                   updated_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (post_visit_notes.strip(), actor_id, appointment_id, elderly_user_id),
        )

    log_activity(
        elderly_user_id,
        actor_id,
        "Completed Doctor Appointment",
        f"Marked appointment with {appt['doctor_name']} ({appt['appointment_date']}) as Completed",
    )
    return True


def mark_appointment_missed(
    appointment_id: int,
    elderly_user_id: int,
    notes: str = "",
    updated_by: int = None,
    user: dict = None,
) -> bool:
    """Marks an appointment as missed when the senior was unable to attend."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    appt = get_appointment_by_id(appointment_id)
    if not appt:
        raise ValueError("Appointment not found.")

    actor_id = updated_by or (user.get("id") if user else None)

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET status = 'missed', updated_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (actor_id, appointment_id, elderly_user_id),
        )

    log_activity(
        elderly_user_id,
        actor_id,
        "Recorded Missed Appointment",
        f"Recorded missed appointment with {appt['doctor_name']} on {appt['appointment_date']}. {notes}".strip(),
    )
    return True


def sync_appointment_reminders(
    elderly_user_id: int = None,
    now_dt: datetime = None,
    user: dict = None,
) -> dict:
    """
    Generates in-app appointment reminders:
    - 1 day before the scheduled visit (within 24 hours of appointment).
    - 1 hour before the scheduled visit (within 60 minutes of appointment).
    Prevents duplicate reminders via SQLite unique constraint on appointment_reminders.
    Dispatches in-app notifications to elderly user and authorized caregivers.
    """
    if now_dt is None:
        now_dt = datetime.now()

    counts = {"one_day_reminders": 0, "one_hour_reminders": 0}

    with get_connection() as conn:
        query = "SELECT * FROM appointments WHERE status = 'upcoming'"
        params = []
        if elderly_user_id:
            query += " AND elderly_user_id = ?"
            params.append(elderly_user_id)

        appts = conn.execute(query, params).fetchall()

        for a in appts:
            appt_id = a["id"]
            e_id = a["elderly_user_id"]
            doc_name = a["doctor_name"]
            hospital = a["hospital"]
            appt_date = a["appointment_date"]
            appt_time = a["appointment_time"]
            spec = a["specialization"] or "Doctor"
            reason = a["reason"] or a["purpose"] or "Routine consultation"

            appt_dt = parse_appointment_datetime(appt_date, appt_time)
            if not appt_dt:
                continue

            # Fetch recipients: elderly user + authorized caregivers in care_circle
            recipients = [e_id]
            cg_rows = conn.execute(
                """SELECT member_user_id FROM care_circle
                   WHERE elderly_user_id = ? AND status = 'active'""",
                (e_id,),
            ).fetchall()
            recipients.extend([r["member_user_id"] for r in cg_rows])

            eld_name_row = conn.execute("SELECT name FROM users WHERE id = ?", (e_id,)).fetchone()
            elderly_name = eld_name_row["name"] if eld_name_row else "Patient"

            # 1. One Day Before Reminder (within [appt_dt - 24h, appt_dt - 1h])
            one_day_window_start = appt_dt - timedelta(days=1)
            if one_day_window_start <= now_dt < appt_dt:
                for uid in recipients:
                    cursor = conn.execute(
                        """INSERT OR IGNORE INTO appointment_reminders
                           (appointment_id, elderly_user_id, user_id, reminder_type, scheduled_for, is_sent, sent_at)
                           VALUES (?, ?, ?, '1_day_before', ?, 1, CURRENT_TIMESTAMP)""",
                        (appt_id, e_id, uid, appt_dt.isoformat()),
                    )
                    if cursor.rowcount > 0:
                        counts["one_day_reminders"] += 1
                        conn.execute(
                            """INSERT INTO notifications
                               (user_id, elderly_user_id, alert_type, title, message)
                               VALUES (?, ?, 'system', ?, ?)""",
                            (
                                uid,
                                e_id,
                                f"Appointment Tomorrow: {doc_name}",
                                f"{elderly_name} has an appointment tomorrow with {doc_name} ({spec}) at {hospital} on {appt_date} at {appt_time}. Reason: {reason}.",
                            ),
                        )

            # 2. One Hour Before Reminder (within [appt_dt - 1h, appt_dt])
            one_hour_window_start = appt_dt - timedelta(hours=1)
            if one_hour_window_start <= now_dt < appt_dt:
                for uid in recipients:
                    cursor = conn.execute(
                        """INSERT OR IGNORE INTO appointment_reminders
                           (appointment_id, elderly_user_id, user_id, reminder_type, scheduled_for, is_sent, sent_at)
                           VALUES (?, ?, ?, '1_hour_before', ?, 1, CURRENT_TIMESTAMP)""",
                        (appt_id, e_id, uid, appt_dt.isoformat()),
                    )
                    if cursor.rowcount > 0:
                        counts["one_hour_reminders"] += 1
                        conn.execute(
                            """INSERT INTO notifications
                               (user_id, elderly_user_id, alert_type, title, message)
                               VALUES (?, ?, 'system', ?, ?)""",
                            (
                                uid,
                                e_id,
                                f"Appointment in 1 Hour: {doc_name}",
                                f"Reminder: {elderly_name}'s appointment with {doc_name} is in 1 hour ({appt_time}) at {hospital}.",
                            ),
                        )

    return counts


def get_appointment_calendar(elderly_user_id: int, user: dict = None) -> dict:
    """
    Returns calendar-grouped dictionary mapping dates ('YYYY-MM-DD') to scheduled appointments.
    """
    appts = get_appointments(elderly_user_id, status="all", user=user)
    cal_data = {}
    for a in appts:
        d = a["appointment_date"]
        if d not in cal_data:
            cal_data[d] = []
        cal_data[d].append(a)
    return cal_data


def get_appointment_history(elderly_user_id: int, user: dict = None) -> list[dict]:
    """Returns past, completed, cancelled, and missed visits with full clinical notes."""
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    today_str = date.today().isoformat()
    query = """
        SELECT a.id, a.elderly_user_id, a.doctor_name, a.specialization, a.hospital,
               a.appointment_date, a.appointment_time, a.appointment_type, a.location,
               COALESCE(a.reason, a.purpose) as reason, a.notes, a.post_visit_notes,
               a.status, a.created_at, a.updated_at,
               u_eld.name as elderly_name,
               u_creator.name as created_by_name,
               u_updater.name as updated_by_name
        FROM appointments a
        JOIN users u_eld ON a.elderly_user_id = u_eld.id
        LEFT JOIN users u_creator ON a.created_by = u_creator.id
        LEFT JOIN users u_updater ON a.updated_by = u_updater.id
        WHERE a.elderly_user_id = ?
          AND (a.status IN ('completed', 'cancelled', 'missed') OR a.appointment_date < ?)
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """
    with get_connection() as conn:
        rows = conn.execute(query, (elderly_user_id, today_str)).fetchall()
        return [dict(r) for r in rows]


def update_appointment_status(
    appointment_id: int,
    elderly_user_id: int,
    status: str,
    updated_by: int = None,
    post_visit_notes: str = "",
    user: dict = None,
):
    """
    Backward-compatible helper to update appointment status.
    Maps to complete_appointment, cancel_appointment, or direct status update.
    """
    clean_status = status.strip().lower()
    if clean_status not in ("upcoming", "completed", "cancelled", "missed"):
        raise ValueError(f"Invalid appointment status: {status}")

    with get_connection() as conn:
        conn.execute(
            """UPDATE appointments
               SET status = ?,
                   post_visit_notes = CASE WHEN ? != '' THEN ? ELSE post_visit_notes END,
                   updated_by = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND elderly_user_id = ?""",
            (clean_status, post_visit_notes.strip(), post_visit_notes.strip(), updated_by, appointment_id, elderly_user_id),
        )

    appt = get_appointment_by_id(appointment_id)
    doc = appt["doctor_name"] if appt else f"Appointment #{appointment_id}"
    actor_id = updated_by or (user.get("id") if user else elderly_user_id)
    log_activity(
        elderly_user_id,
        actor_id,
        f"Appointment {clean_status.title()}",
        f"Status for appointment with {doc} changed to {clean_status}",
    )


def delete_appointment(appointment_id: int, elderly_user_id: int, deleted_by: int = None, user: dict = None):
    """
    Deletes an appointment record and its related reminders.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=True)

    appt = get_appointment_by_id(appointment_id)
    doc = appt["doctor_name"] if appt else f"Appointment #{appointment_id}"

    with get_connection() as conn:
        conn.execute("DELETE FROM appointment_reminders WHERE appointment_id = ?", (appointment_id,))
        conn.execute("DELETE FROM appointments WHERE id = ? AND elderly_user_id = ?", (appointment_id, elderly_user_id))

    actor_id = deleted_by or (user.get("id") if user else elderly_user_id)
    log_activity(elderly_user_id, actor_id, "Deleted Appointment", f"Removed appointment with {doc}")

