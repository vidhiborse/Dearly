import sqlite3
from database import get_connection
from services.activity_service import log_activity

def get_health_readings(elderly_user_id: int, reading_type: str = None, limit: int = 40):
    with get_connection() as conn:
        query = "SELECT * FROM health_readings WHERE elderly_user_id = ?"
        params = [elderly_user_id]
        if reading_type:
            query += " AND reading_type = ?"
            params.append(reading_type)
        query += " ORDER BY recorded_on DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def add_health_reading(
    elderly_user_id: int,
    reading_type: str,
    reading_value: str,
    recorded_on: str,
    notes: str = "",
    recorded_by: int = None,
):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO health_readings (elderly_user_id, reading_type, reading_value, recorded_on, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (elderly_user_id, reading_type.strip(), reading_value.strip(), recorded_on.strip(), notes.strip()),
        )
        reading_id = cursor.lastrowid

    if recorded_by:
        log_activity(
            elderly_user_id,
            recorded_by,
            "Logged Health Reading",
            f"Recorded {reading_type}: {reading_value} on {recorded_on}. {notes}".strip(),
        )
    return reading_id

def get_latest_vitals(elderly_user_id: int):
    types = [
        "Blood Pressure",
        "Blood Sugar (Fasting)",
        "Heart Rate",
        "Oxygen Saturation (SpO2)",
        "Weight",
    ]
    latest = {}
    with get_connection() as conn:
        for t in types:
            row = conn.execute(
                """SELECT reading_type, reading_value, recorded_on, notes
                   FROM health_readings
                   WHERE elderly_user_id = ? AND reading_type = ?
                   ORDER BY recorded_on DESC, id DESC
                   LIMIT 1""",
                (elderly_user_id, t),
            ).fetchone()
            latest[t] = dict(row) if row else None
    return latest
