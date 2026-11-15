import sqlite3
from database import get_connection

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
