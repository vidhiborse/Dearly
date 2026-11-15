import sqlite3
from database import get_connection
from services.permissions import can_access_elderly_record


def log_activity(elderly_user_id: int, actor_user_id: int, action: str, details: str):
    """Logs an auditable activity for an elderly individual's record."""
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO activity_logs (elderly_user_id, actor_user_id, action, details)
                   VALUES (?, ?, ?, ?)""",
                (elderly_user_id, actor_user_id, action, details),
            )
    except Exception as e:
        print(f"Failed to log activity: {e}")


def get_recent_activities(elderly_user_id: int, limit: int = 25):
    """Retrieves recent care activities for an elderly user."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT al.id, al.action, al.details, al.created_at,
                      u.name as actor_name, u.role as actor_role
               FROM activity_logs al
               LEFT JOIN users u ON al.actor_user_id = u.id
               WHERE al.elderly_user_id = ?
               ORDER BY al.created_at DESC
               LIMIT ?""",
            (elderly_user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_care_activity_timeline(
    elderly_user_id: int,
    user: dict = None,
    action_filter: str = "all",
    start_date: str = None,
    end_date: str = None,
    limit: int = 50,
) -> list[dict]:
    """
    Returns filtered, server-authorized care activity timeline events.
    Supports filtering by event category and date range.
    """
    if user and not can_access_elderly_record(user, elderly_user_id):
        raise PermissionError(f"User #{user.get('id')} lacks access to activity logs for profile #{elderly_user_id}")

    query = """
        SELECT al.id, al.elderly_user_id, al.action, al.details, al.created_at,
               u_act.name as actor_name, u_act.role as actor_role,
               u_eld.name as elderly_name
        FROM activity_logs al
        JOIN users u_eld ON al.elderly_user_id = u_eld.id
        LEFT JOIN users u_act ON al.actor_user_id = u_act.id
        WHERE al.elderly_user_id = ?
    """
    params = [elderly_user_id]

    # Category or exact action filter
    if action_filter and action_filter.lower() != "all":
        filt = action_filter.lower()
        if filt == "medication":
            query += " AND (al.action LIKE '%Medication%' OR al.action LIKE '%Dose%')"
        elif filt == "reminder":
            query += " AND (al.action LIKE '%Reminder%' OR al.action LIKE '%Escalation%' OR al.action LIKE '%Overdue%')"
        elif filt == "circle":
            query += " AND (al.action LIKE '%Circle%' OR al.action LIKE '%Caregiver%' OR al.action LIKE '%Invitation%')"
        elif filt == "notes":
            query += " AND al.action LIKE '%Note%'"
        else:
            query += " AND LOWER(al.action) = LOWER(?)"
            params.append(action_filter)

    if start_date:
        query += " AND date(al.created_at) >= date(?)"
        params.append(start_date)

    if end_date:
        query += " AND date(al.created_at) <= date(?)"
        params.append(end_date)

    query += " ORDER BY al.created_at DESC LIMIT ?"
    params.append(int(limit))

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
