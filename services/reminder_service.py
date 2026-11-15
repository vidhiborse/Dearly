import sqlite3
from datetime import datetime, date, timedelta
from database import get_connection
from services.permissions import enforce_elderly_access, can_access_elderly_record, can_manage_elderly_care
from services.activity_service import log_activity


def get_user_reminder_settings(user_id: int) -> dict:
    """
    Fetches reminder settings for a user.
    If no record exists, inserts and returns default configuration:
    - grace_period_minutes: 15
    - enable_reminders: 1
    - enable_escalation: 1
    - time_format: '12h'
    """
    with get_connection() as conn:
        row = conn.execute(
            """SELECT user_id, grace_period_minutes, enable_reminders, enable_escalation, time_format, updated_at
               FROM reminder_settings WHERE user_id = ?""",
            (user_id,),
        ).fetchone()

        if row:
            return dict(row)

        # Initialize defaults
        conn.execute(
            """INSERT OR IGNORE INTO reminder_settings
               (user_id, grace_period_minutes, enable_reminders, enable_escalation, time_format)
               VALUES (?, 15, 1, 1, '12h')""",
            (user_id,),
        )
        created = conn.execute(
            """SELECT user_id, grace_period_minutes, enable_reminders, enable_escalation, time_format, updated_at
               FROM reminder_settings WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        return dict(created) if created else {
            "user_id": user_id,
            "grace_period_minutes": 15,
            "enable_reminders": 1,
            "enable_escalation": 1,
            "time_format": "12h",
        }


def update_user_reminder_settings(
    user_id: int,
    grace_period_minutes: int = 15,
    enable_reminders: bool = True,
    enable_escalation: bool = True,
    time_format: str = "12h",
) -> bool:
    """
    Updates a user's reminder and notification preferences.
    Validates grace period (0 - 180 min) and time format ('12h' or '24h').
    """
    if grace_period_minutes < 0 or grace_period_minutes > 180:
        raise ValueError("Grace period must be between 0 and 180 minutes.")

    fmt = time_format.strip().lower()
    if fmt not in ("12h", "24h"):
        raise ValueError("Time format must be either '12h' or '24h'.")

    rem_val = 1 if enable_reminders else 0
    esc_val = 1 if enable_escalation else 0

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO reminder_settings
               (user_id, grace_period_minutes, enable_reminders, enable_escalation, time_format, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   grace_period_minutes = excluded.grace_period_minutes,
                   enable_reminders = excluded.enable_reminders,
                   enable_escalation = excluded.enable_escalation,
                   time_format = excluded.time_format,
                   updated_at = CURRENT_TIMESTAMP""",
            (user_id, int(grace_period_minutes), rem_val, esc_val, fmt),
        )
    return True


def format_time_display(time_str: str, time_format: str = "12h") -> str:
    """Formats 24h HH:MM string to '12h' (e.g. 08:30 AM) or '24h' (e.g. 08:30)."""
    if not time_str:
        return ""
    try:
        t_obj = datetime.strptime(time_str.strip(), "%H:%M")
        if time_format == "24h":
            return t_obj.strftime("%H:%M")
        return t_obj.strftime("%I:%M %p")
    except Exception:
        return time_str


def calculate_reminder_status(
    schedule_time: str,
    scheduled_date: str,
    dose_status: str,
    grace_period_minutes: int = 15,
    now_dt: datetime = None,
) -> str:
    """
    Deterministic evaluation of dose reminder status based on time and grace period:
    - 'completed': dose has been explicitly confirmed taken.
    - 'skipped': dose has been explicitly marked as skipped.
    - 'upcoming': scheduled datetime is in the future.
    - 'due_now': scheduled time has arrived and now is within [schedule_time, schedule_time + grace_period].
    - 'overdue': now has passed [schedule_time + grace_period] without a recorded taken or skipped status.
    """
    st_lower = (dose_status or "pending").strip().lower()
    if st_lower == "taken":
        return "completed"
    if st_lower == "skipped":
        return "skipped"

    if now_dt is None:
        now_dt = datetime.now()

    try:
        sched_dt = datetime.strptime(f"{scheduled_date} {schedule_time.strip()}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "upcoming"

    grace_delta = timedelta(minutes=max(0, int(grace_period_minutes)))
    due_window_end = sched_dt + grace_delta

    if now_dt < sched_dt:
        return "upcoming"
    elif sched_dt <= now_dt <= due_window_end:
        return "due_now"
    else:
        return "overdue"


def get_upcoming_and_active_reminders(
    elderly_user_id: int,
    target_date: str = None,
    now_dt: datetime = None,
    user: dict = None,
) -> list[dict]:
    """
    Returns structured reminders for an elderly individual on target_date.
    Respects active medication bounds (start_date <= target_date <= end_date).
    Uses the user's configured grace period and time format.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    if not target_date:
        target_date = (now_dt.date() if now_dt else date.today()).isoformat()

    if now_dt is None:
        now_dt = datetime.now()

    # Load elderly user's reminder settings
    settings = get_user_reminder_settings(elderly_user_id)
    grace_period = settings.get("grace_period_minutes", 15)
    time_format = settings.get("time_format", "12h")

    with get_connection() as conn:
        elderly_row = conn.execute("SELECT name FROM users WHERE id = ?", (elderly_user_id,)).fetchone()
        elderly_name = elderly_row["name"] if elderly_row else "Patient"

        rows = conn.execute(
            """SELECT m.id as medication_id, m.medicine_name, m.dosage, m.medication_type,
                      m.schedule_time, m.frequency, m.meal_timing, m.instructions, m.purpose,
                      m.prescribing_doctor, m.notes as med_notes, m.stock_quantity,
                      m.start_date, m.end_date, m.active,
                      COALESCE(ml.status, 'pending') as log_status,
                      ml.actual_action_time, ml.notes as log_notes, ml.recorded_at
               FROM medications m
               LEFT JOIN medication_logs ml ON m.id = ml.medication_id AND ml.scheduled_date = ?
               WHERE m.elderly_user_id = ? AND m.active = 1
                 AND (m.start_date IS NULL OR m.start_date <= ?)
                 AND (m.end_date IS NULL OR m.end_date = '' OR m.end_date >= ?)
               ORDER BY m.schedule_time ASC""",
            (target_date, elderly_user_id, target_date, target_date),
        ).fetchall()

    reminders = []
    for r in rows:
        item = dict(r)
        status = calculate_reminder_status(
            schedule_time=item["schedule_time"],
            scheduled_date=target_date,
            dose_status=item["log_status"],
            grace_period_minutes=grace_period,
            now_dt=now_dt,
        )
        item["status"] = status
        item["reminder_status"] = status
        item["elderly_name"] = elderly_name
        item["elderly_user_id"] = elderly_user_id
        item["target_date"] = target_date
        item["grace_period_minutes"] = grace_period
        item["formatted_time"] = format_time_display(item["schedule_time"], time_format)
        reminders.append(item)

    return reminders


def sync_reminders_and_escalations(
    elderly_user_id: int,
    target_date: str = None,
    now_dt: datetime = None,
    user: dict = None,
) -> dict:
    """
    Idempotent synchronization of reminders, in-app notifications, and caregiver escalations.
    Can be invoked on every Streamlit page load or background poll without creating duplicate records.
    - Generates 'due_now' and 'overdue' in-app notifications for elderly user.
    - When a dose is 'overdue', escalates to authorized caregivers with 'editor' access in care_circle.
    - Prevents duplicate alerts via SQLite unique constraints.
    """
    if user:
        enforce_elderly_access(user, elderly_user_id, write_access=False)

    if not target_date:
        target_date = (now_dt.date() if now_dt else date.today()).isoformat()

    if now_dt is None:
        now_dt = datetime.now()

    reminders = get_upcoming_and_active_reminders(
        elderly_user_id=elderly_user_id,
        target_date=target_date,
        now_dt=now_dt,
        user=user,
    )

    settings = get_user_reminder_settings(elderly_user_id)
    reminders_enabled = bool(settings.get("enable_reminders", 1))
    escalation_enabled = bool(settings.get("enable_escalation", 1))

    counts = {"due_now": 0, "overdue": 0, "escalated": 0, "completed": 0}

    with get_connection() as conn:
        # Fetch caregivers linked with editor permissions
        caregiver_rows = conn.execute(
            """SELECT u.id, u.name, u.email
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ? AND cc.permission_level = 'editor'""",
            (elderly_user_id,),
        ).fetchall()
        caregivers = [dict(c) for c in caregiver_rows]

        for rem in reminders:
            status = rem["status"]
            med_id = rem["medication_id"]
            sched_time = rem["schedule_time"]
            formatted_time = rem["formatted_time"]
            med_name = rem["medicine_name"]
            dosage = rem["dosage"]
            elderly_name = rem["elderly_name"]
            instructions = rem.get("instructions") or "Follow standard administration instructions."

            if status == "due_now" and reminders_enabled:
                counts["due_now"] += 1
                conn.execute(
                    """INSERT OR IGNORE INTO notifications
                       (user_id, elderly_user_id, alert_type, title, message, medication_id, scheduled_date, scheduled_time)
                       VALUES (?, ?, 'due_now', ?, ?, ?, ?, ?)""",
                    (
                        elderly_user_id,
                        elderly_user_id,
                        f"Medicine Due Now: {med_name} ({dosage})",
                        f"It is time to take your {med_name} scheduled for {formatted_time}. {instructions}".strip(),
                        med_id,
                        target_date,
                        sched_time,
                    ),
                )

            elif status == "overdue":
                counts["overdue"] += 1
                if reminders_enabled:
                    # Notify elderly user
                    conn.execute(
                        """INSERT OR IGNORE INTO notifications
                           (user_id, elderly_user_id, alert_type, title, message, medication_id, scheduled_date, scheduled_time)
                           VALUES (?, ?, 'overdue', ?, ?, ?, ?, ?)""",
                        (
                            elderly_user_id,
                            elderly_user_id,
                            f"Overdue Notice: {med_name} ({dosage})",
                            f"Your dose of {med_name} scheduled for {formatted_time} is past due. Please take your prescribed medicine or check with your caregiver. Do not take an extra dose or double up.",
                            med_id,
                            target_date,
                            sched_time,
                        ),
                    )

                # Caregiver Escalation
                if escalation_enabled and caregivers:
                    for cg in caregivers:
                        cg_id = cg["id"]
                        # Insert caregiver escalation record
                        cursor = conn.execute(
                            """INSERT OR IGNORE INTO caregiver_escalations
                               (medication_id, elderly_user_id, caregiver_user_id, scheduled_date, scheduled_time, status)
                               VALUES (?, ?, ?, ?, ?, 'pending')""",
                            (med_id, elderly_user_id, cg_id, target_date, sched_time),
                        )
                        if cursor.rowcount > 0:
                            counts["escalated"] += 1

                        # Insert notification for caregiver
                        conn.execute(
                            """INSERT OR IGNORE INTO notifications
                               (user_id, elderly_user_id, alert_type, title, message, medication_id, scheduled_date, scheduled_time)
                               VALUES (?, ?, 'escalation', ?, ?, ?, ?, ?)""",
                            (
                                cg_id,
                                elderly_user_id,
                                f"Caregiver Escalation: Overdue Dose for {elderly_name}",
                                f"{elderly_name} has an overdue dose of {med_name} ({dosage}) scheduled for {formatted_time}. Please check in to verify dose status.",
                                med_id,
                                target_date,
                                sched_time,
                            ),
                        )

            elif status == "completed":
                counts["completed"] += 1
                # When dose is completed, resolve active caregiver escalations for that scheduled dose
                conn.execute(
                    """UPDATE caregiver_escalations
                       SET status = 'resolved'
                       WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ? AND status = 'pending'""",
                    (med_id, target_date, sched_time),
                )

    return counts


def get_user_notifications(
    user: dict,
    alert_type: str = "all",
    elderly_id: int = None,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """
    Fetches notifications destined for the current user.
    Enforces RBAC:
    - Elderly sees only their own notifications.
    - Caregivers see notifications assigned to them for linked elderly wards.
    - Family members see notifications assigned to them for linked elderly wards.
    """
    if not user:
        return []

    user_id = user["id"]
    query = """
        SELECT n.id, n.user_id, n.elderly_user_id, n.alert_type, n.title, n.message,
               n.medication_id, n.scheduled_date, n.scheduled_time, n.is_read, n.read_at, n.created_at,
               u_eld.name as elderly_name, m.medicine_name, m.dosage
        FROM notifications n
        JOIN users u_eld ON n.elderly_user_id = u_eld.id
        LEFT JOIN medications m ON n.medication_id = m.id
        WHERE n.user_id = ?
    """
    params = [user_id]

    if elderly_id:
        if not can_access_elderly_record(user, elderly_id):
            raise PermissionError(f"User #{user_id} lacks access to notifications for elderly profile #{elderly_id}")
        query += " AND n.elderly_user_id = ?"
        params.append(elderly_id)

    if alert_type and alert_type != "all":
        query += " AND n.alert_type = ?"
        params.append(alert_type)

    if unread_only:
        query += " AND n.is_read = 0"

    query += " ORDER BY n.created_at DESC LIMIT ?"
    params.append(int(limit))

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_unread_notification_count(user_id: int, elderly_id: int = None) -> int:
    """Returns number of unread notifications for a user."""
    query = "SELECT COUNT(*) as cnt FROM notifications WHERE user_id = ? AND is_read = 0"
    params = [user_id]
    if elderly_id:
        query += " AND elderly_user_id = ?"
        params.append(elderly_id)

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return row["cnt"] if row else 0


def mark_notification_as_read(notification_id: int, user_id: int) -> bool:
    """Marks a single notification as read."""
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE notifications
               SET is_read = 1, read_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (notification_id, user_id),
        )
        return cursor.rowcount > 0


def mark_all_notifications_as_read(user_id: int, elderly_id: int = None) -> int:
    """Marks all notifications as read for a user."""
    query = "UPDATE notifications SET is_read = 1, read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND is_read = 0"
    params = [user_id]
    if elderly_id:
        query += " AND elderly_user_id = ?"
        params.append(elderly_id)

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.rowcount


def get_caregiver_escalations(
    caregiver_user: dict,
    elderly_id: int = None,
    pending_only: bool = False,
) -> list[dict]:
    """
    Fetches escalations for a caregiver with patient details.
    """
    if not caregiver_user:
        return []

    cg_id = caregiver_user["id"]
    query = """
        SELECT ce.id, ce.medication_id, ce.elderly_user_id, ce.caregiver_user_id,
               ce.scheduled_date, ce.scheduled_time, ce.status, ce.escalated_at,
               ce.is_acknowledged, ce.acknowledged_at, ce.acknowledged_by,
               u_eld.name as elderly_name, u_ack.name as acknowledged_by_name,
               m.medicine_name, m.dosage, m.instructions
        FROM caregiver_escalations ce
        JOIN users u_eld ON ce.elderly_user_id = u_eld.id
        LEFT JOIN users u_ack ON ce.acknowledged_by = u_ack.id
        JOIN medications m ON ce.medication_id = m.id
        WHERE ce.caregiver_user_id = ?
    """
    params = [cg_id]

    if elderly_id:
        if not can_access_elderly_record(caregiver_user, elderly_id):
            raise PermissionError("Unauthorized to view escalations for this profile.")
        query += " AND ce.elderly_user_id = ?"
        params.append(elderly_id)

    if pending_only:
        query += " AND ce.is_acknowledged = 0"

    query += " ORDER BY ce.escalated_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def acknowledge_caregiver_escalation(
    escalation_id: int,
    caregiver_user: dict,
    notes: str = "",
) -> bool:
    """
    Allows an authorized caregiver to acknowledge an overdue escalation.
    Note: Acknowledging an escalation records oversight; it does NOT mark the dose as taken.
    """
    if not caregiver_user:
        return False

    cg_id = caregiver_user["id"]
    with get_connection() as conn:
        esc = conn.execute(
            """SELECT ce.id, ce.elderly_user_id, ce.medication_id, ce.scheduled_date, ce.scheduled_time,
                      m.medicine_name, u.name as elderly_name
               FROM caregiver_escalations ce
               JOIN medications m ON ce.medication_id = m.id
               JOIN users u ON ce.elderly_user_id = u.id
               WHERE ce.id = ? AND ce.caregiver_user_id = ?""",
            (escalation_id, cg_id),
        ).fetchone()

        if not esc:
            return False

        conn.execute(
            """UPDATE caregiver_escalations
               SET is_acknowledged = 1,
                   acknowledged_at = CURRENT_TIMESTAMP,
                   acknowledged_by = ?,
                   status = 'acknowledged'
               WHERE id = ?""",
            (cg_id, escalation_id),
        )

        # Mark corresponding notification as read
        conn.execute(
            """UPDATE notifications
               SET is_read = 1, read_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND medication_id = ? AND scheduled_date = ? AND scheduled_time = ? AND alert_type = 'escalation'""",
            (cg_id, esc["medication_id"], esc["scheduled_date"], esc["scheduled_time"]),
        )

    log_activity(
        esc["elderly_user_id"],
        cg_id,
        "Acknowledged Overdue Dose Escalation",
        f"Caregiver acknowledged escalation for {esc['medicine_name']} ({esc['scheduled_time']}) for {esc['elderly_name']}. {notes}".strip(),
    )
    return True
