import html
import sqlite3
from datetime import datetime, date
from database import get_connection

def format_accessible_email_html(
    title: str,
    preheader: str,
    recipient_name: str,
    senior_name: str,
    alert_badge: str,
    alert_badge_color: str,
    main_details: list[tuple[str, str]],
    action_guidance: str,
    disclaimer: str = "Informational reminder from Dearly. For urgent medical emergencies, immediately contact local emergency services.",
) -> str:
    """
    Renders clean, accessible HTML email markup meeting healthcare communication guidelines.
    High contrast, readable typography, and explicit clinical safety guardrails.
    """
    s_title = html.escape(title)
    s_pre = html.escape(preheader)
    s_rec = html.escape(recipient_name)
    s_sen = html.escape(senior_name)
    s_badge = html.escape(alert_badge)
    s_action = html.escape(action_guidance)
    s_disc = html.escape(disclaimer)

    detail_rows_html = ""
    for label, val in main_details:
        detail_rows_html += f"""
        <tr>
            <td style="padding: 8px 12px; font-weight: 600; color: #234B70; width: 35%; border-bottom: 1px solid #DFE6EE;">{html.escape(label)}</td>
            <td style="padding: 8px 12px; color: #243447; border-bottom: 1px solid #DFE6EE;">{html.escape(str(val))}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{s_title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F5F8FC; margin: 0; padding: 24px; color: #243447;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 8px; overflow: hidden;">
        <tr>
            <td style="background-color: #234B70; padding: 20px 24px;">
                <h2 style="color: #FFFFFF; margin: 0; font-size: 22px;">Dearly</h2>
                <p style="color: #E2E8F0; margin: 2px 0 0 0; font-size: 13px;">Care that stays close • Healthcare Routine Notification</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 24px;">
                <div style="display: inline-block; background-color: {alert_badge_color}; color: #FFFFFF; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 4px; margin-bottom: 12px;">
                    {s_badge}
                </div>
                <h3 style="color: #234B70; margin: 0 0 8px 0; font-size: 18px;">{s_pre}</h3>
                <p style="font-size: 15px; color: #475569; margin: 0 0 16px 0;">Dear {s_rec}, this is an automated routine reminder for <strong>{s_sen}</strong>.</p>
                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #F8FAFD; border: 1px solid #E2E8F0; border-radius: 6px; margin-bottom: 16px;">
                    {detail_rows_html}
                </table>
                <div style="background-color: #FFFBEB; border-left: 4px solid #F59E0B; padding: 12px 14px; border-radius: 4px; margin-bottom: 18px;">
                    <strong style="color: #92400E; font-size: 14px;">Care Action Guidance:</strong>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #78350F;">{s_action}</p>
                </div>
                <p style="font-size: 12px; color: #64748B; margin: 0; line-height: 1.5; border-top: 1px solid #E2E8F0; padding-top: 14px;">
                    {s_disc}
                </p>
            </td>
        </tr>
    </table>
</body>
</html>"""


def log_email_dispatch(
    elderly_user_id: int,
    recipient_email: str,
    subject: str,
    message_content: str,
    channel: str = "email",
    status: str = "sent",
    conn=None,
) -> int:
    """
    Records an outbound simulated email reminder in the database.
    Reuses existing database connection if provided to eliminate lock contention.
    """
    query = """INSERT INTO simulated_reminders
               (elderly_user_id, recipient_email, subject, message, channel, status, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)"""
    params = (elderly_user_id, recipient_email.strip().lower(), subject.strip(), message_content, channel, status)

    if conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid

    with get_connection() as c:
        cursor = c.execute(query, params)
        return cursor.lastrowid


def send_upcoming_dose_email(
    elderly_user_id: int,
    recipient_email: str,
    recipient_name: str,
    senior_name: str,
    medicine_name: str,
    dosage: str,
    scheduled_time: str,
    meal_timing: str = "After Meal",
    instructions: str = "",
    conn=None,
) -> int:
    """Dispatches an upcoming medication routine email reminder."""
    subject = f"Upcoming Dose Reminder: {medicine_name} ({dosage}) at {scheduled_time} for {senior_name}"
    html_body = format_accessible_email_html(
        title="Upcoming Dose Reminder",
        preheader=f"Medicine Scheduled: {medicine_name} ({dosage})",
        recipient_name=recipient_name,
        senior_name=senior_name,
        alert_badge="UPCOMING DOSE",
        alert_badge_color="#234B70",
        main_details=[
            ("Medication", medicine_name),
            ("Dosage", dosage),
            ("Scheduled Time", scheduled_time),
            ("Meal Timing", meal_timing),
            ("Instructions", instructions or "Follow regular directions"),
        ],
        action_guidance="Please ensure this medicine is taken as scheduled. If taken, confirm via the Dearly dashboard to keep the care circle updated.",
    )
    return log_email_dispatch(elderly_user_id, recipient_email, subject, html_body, channel="email", status="sent", conn=conn)


def send_missed_dose_email(
    elderly_user_id: int,
    recipient_email: str,
    recipient_name: str,
    senior_name: str,
    medicine_name: str,
    dosage: str,
    scheduled_time: str,
    conn=None,
) -> int:
    """Dispatches a missed/overdue medication email alert to caregivers and family."""
    subject = f"OVERDUE MEDICATION NOTICE: {medicine_name} ({dosage}) for {senior_name}"
    html_body = format_accessible_email_html(
        title="Overdue Medication Alert",
        preheader=f"Scheduled Time Passed for {medicine_name}",
        recipient_name=recipient_name,
        senior_name=senior_name,
        alert_badge="ACTION REQUIRED: OVERDUE DOSE",
        alert_badge_color="#B84040",
        main_details=[
            ("Patient", senior_name),
            ("Medication", medicine_name),
            ("Dosage", dosage),
            ("Scheduled Time", scheduled_time),
            ("Status", "Past Due / Unconfirmed"),
        ],
        action_guidance="Please verify directly with the care recipient if this dose was taken. Clinical safety guidance: Never advise taking an extra dose or doubling medication to compensate for a missed dose.",
    )
    return log_email_dispatch(elderly_user_id, recipient_email, subject, html_body, channel="email", status="sent", conn=conn)


def send_appointment_email(
    elderly_user_id: int,
    recipient_email: str,
    recipient_name: str,
    senior_name: str,
    doctor_name: str,
    hospital: str,
    appointment_date: str,
    appointment_time: str,
    reminder_type: str = "1_day_before",
    notes: str = "",
    conn=None,
) -> int:
    """Dispatches a medical appointment email reminder."""
    urgency_label = "Tomorrow" if reminder_type == "1_day_before" else "In 1 Hour"
    subject = f"Doctor Visit Reminder: Dr. {doctor_name} ({urgency_label}) for {senior_name}"
    html_body = format_accessible_email_html(
        title=f"Doctor Appointment Reminder ({urgency_label})",
        preheader=f"Medical Consultation: Dr. {doctor_name}",
        recipient_name=recipient_name,
        senior_name=senior_name,
        alert_badge=f"APPOINTMENT REMINDER ({urgency_label.upper()})",
        alert_badge_color="#065F46" if reminder_type == "1_day_before" else "#B84040",
        main_details=[
            ("Doctor Name", f"Dr. {doctor_name}"),
            ("Hospital / Clinic", hospital),
            ("Visit Date", appointment_date),
            ("Visit Time", appointment_time),
            ("Preparation Notes", notes or "Carry existing prescription and recent health readings"),
        ],
        action_guidance="Please arrange transport and ensure all previous diagnostic reports are carried to the clinic. Check in early.",
    )
    return log_email_dispatch(elderly_user_id, recipient_email, subject, html_body, channel="email", status="sent", conn=conn)


def get_outbound_emails(elderly_user_id: int = None, limit: int = 50) -> list[dict]:
    """Fetches chronological outbound email reminders log with delivery status."""
    with get_connection() as conn:
        if elderly_user_id:
            rows = conn.execute(
                """SELECT id, elderly_user_id, recipient_email, subject, message, channel, status, sent_at
                   FROM simulated_reminders
                   WHERE elderly_user_id = ?
                   ORDER BY sent_at DESC
                   LIMIT ?""",
                (elderly_user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, elderly_user_id, recipient_email, subject, message, channel, status, sent_at
                   FROM simulated_reminders
                   ORDER BY sent_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_email_statistics(elderly_user_id: int = None) -> dict:
    """Aggregates email delivery metrics for evaluator observability."""
    with get_connection() as conn:
        query = "SELECT COUNT(*) as total_sent, COUNT(DISTINCT recipient_email) as recipients_count FROM simulated_reminders"
        params = []
        if elderly_user_id:
            query += " WHERE elderly_user_id = ?"
            params.append(elderly_user_id)
        row = conn.execute(query, params).fetchone()
        return {
            "total_sent": row["total_sent"] if row else 0,
            "recipients_count": row["recipients_count"] if row else 0,
        }
