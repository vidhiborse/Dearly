import sqlite3
from database import get_connection
from services.activity_service import log_activity

def trigger_sos_alert(elderly_user_id: int, triggered_by_user_id: int, message: str = "Urgent SOS button activated by elderly user"):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO emergency_alerts (elderly_user_id, triggered_by_user_id, alert_type, status, message)
               VALUES (?, ?, 'SOS', 'active', ?)""",
            (elderly_user_id, triggered_by_user_id, message),
        )
        alert_id = cursor.lastrowid

        # Also log simulated notifications sent to all care circle members
        members = conn.execute(
            """SELECT u.email, u.name, u.phone, cc.relationship
               FROM care_circle cc
               JOIN users u ON cc.member_user_id = u.id
               WHERE cc.elderly_user_id = ?""",
            (elderly_user_id,),
        ).fetchall()

        for m in members:
            conn.execute(
                """INSERT INTO simulated_reminders
                   (elderly_user_id, recipient_email, subject, message, channel, status)
                   VALUES (?, ?, ?, ?, 'sms+email', 'simulated_dispatched')""",
                (
                    elderly_user_id,
                    m["email"],
                    "URGENT: Dearly Emergency Alert Triggered",
                    f"Dearly Emergency Alert for your care recipient. Alert ID #{alert_id}. Note: This is a hackathon simulation. In real emergencies call emergency dispatch (e.g. 911 / 112).",
                ),
            )

    log_activity(
        elderly_user_id,
        triggered_by_user_id,
        "EMERGENCY ALERT TRIGGERED",
        f"Emergency alert #{alert_id} dispatched to {len(members)} care circle member(s). [SIMULATED]",
    )
    return alert_id

def get_active_emergency_alerts(elderly_user_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT ea.id, ea.alert_type, ea.status, ea.message, ea.created_at,
                      u.name as triggered_by_name
               FROM emergency_alerts ea
               JOIN users u ON ea.triggered_by_user_id = u.id
               WHERE ea.elderly_user_id = ? AND ea.status = 'active'
               ORDER BY ea.created_at DESC""",
            (elderly_user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

def acknowledge_alert(alert_id: int, elderly_user_id: int, acknowledged_by_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE emergency_alerts SET status = 'acknowledged' WHERE id = ?",
            (alert_id,),
        )
    log_activity(
        elderly_user_id,
        acknowledged_by_id,
        "Emergency Alert Acknowledged",
        f"SOS alert #{alert_id} was acknowledged and marked safe by responder.",
    )

def simulate_reminder_notification(elderly_user_id: int, recipient_email: str, subject: str, message: str, channel: str = "email"):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO simulated_reminders (elderly_user_id, recipient_email, subject, message, channel, status)
               VALUES (?, ?, ?, ?, ?, 'simulated_sent')""",
            (elderly_user_id, recipient_email.strip(), subject.strip(), message.strip(), channel),
        )

def get_simulated_reminders(elderly_user_id: int, limit: int = 15):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM simulated_reminders
               WHERE elderly_user_id = ?
               ORDER BY sent_at DESC LIMIT ?""",
            (elderly_user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
