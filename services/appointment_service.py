import sqlite3
from datetime import date
from database import get_connection
from services.activity_service import log_activity

def get_appointments(elderly_user_id: int, status: str = None):
    with get_connection() as conn:
        query = "SELECT * FROM appointments WHERE elderly_user_id = ?"
        params = [elderly_user_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY appointment_date ASC, appointment_time ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def get_next_upcoming_appointment(elderly_user_id: int):
    today_str = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM appointments
               WHERE elderly_user_id = ? AND status = 'upcoming' AND appointment_date >= ?
               ORDER BY appointment_date ASC, appointment_time ASC
               LIMIT 1""",
            (elderly_user_id, today_str),
        ).fetchone()
        return dict(row) if row else None

def add_appointment(
    elderly_user_id: int,
    doctor_name: str,
    hospital: str,
    appointment_date: str,
    appointment_time: str,
    purpose: str,
    notes: str = "",
    created_by: int = None,
):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO appointments
               (elderly_user_id, doctor_name, hospital, appointment_date, appointment_time, purpose, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'upcoming', ?)""",
            (elderly_user_id, doctor_name.strip(), hospital.strip(), appointment_date.strip(), appointment_time.strip(), purpose.strip(), notes.strip()),
        )
        appt_id = cursor.lastrowid

    if created_by:
        log_activity(
            elderly_user_id,
            created_by,
            "Scheduled Doctor Appointment",
            f"Scheduled appointment with {doctor_name} on {appointment_date} at {appointment_time} ({hospital})",
        )
    return appt_id

def update_appointment_status(appointment_id: int, elderly_user_id: int, status: str, updated_by: int = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE appointments SET status = ? WHERE id = ? AND elderly_user_id = ?",
            (status, appointment_id, elderly_user_id),
        )
        appt = conn.execute("SELECT doctor_name, appointment_date FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        doctor = appt["doctor_name"] if appt else f"Appointment #{appointment_id}"

    if updated_by:
        log_activity(
            elderly_user_id,
            updated_by,
            f"Appointment {status.title()}",
            f"Status for appointment with {doctor} changed to {status}",
        )

def delete_appointment(appointment_id: int, elderly_user_id: int, deleted_by: int = None):
    with get_connection() as conn:
        appt = conn.execute("SELECT doctor_name, appointment_date FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
        doctor = appt["doctor_name"] if appt else f"Appointment #{appointment_id}"
        conn.execute("DELETE FROM appointments WHERE id = ? AND elderly_user_id = ?", (appointment_id, elderly_user_id))

    if deleted_by:
        log_activity(
            elderly_user_id,
            deleted_by,
            "Deleted Appointment",
            f"Removed appointment with {doctor}",
        )
