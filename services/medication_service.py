import sqlite3
from datetime import datetime, date, timedelta
from database import get_connection
from services.activity_service import log_activity

def get_medications(elderly_user_id: int, active_only: bool = False):
    with get_connection() as conn:
        query = "SELECT * FROM medications WHERE elderly_user_id = ?"
        params = [elderly_user_id]
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY schedule_time ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def add_medication(
    elderly_user_id: int,
    medicine_name: str,
    dosage: str,
    schedule_time: str,
    frequency: str = "Daily",
    meal_timing: str = "After Meal",
    instructions: str = "",
    purpose: str = "",
    stock_quantity: int = 30,
    created_by: int = None,
):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO medications
               (elderly_user_id, medicine_name, dosage, schedule_time, frequency, meal_timing, instructions, purpose, stock_quantity, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (elderly_user_id, medicine_name.strip(), dosage.strip(), schedule_time.strip(), frequency, meal_timing, instructions.strip(), purpose.strip(), int(stock_quantity)),
        )
        med_id = cursor.lastrowid
        
    if created_by:
        log_activity(
            elderly_user_id,
            created_by,
            "Added Medication",
            f"Added {medicine_name} {dosage} ({schedule_time}, {meal_timing})",
        )
    return med_id

def update_medication(
    medication_id: int,
    elderly_user_id: int,
    medicine_name: str,
    dosage: str,
    schedule_time: str,
    frequency: str,
    meal_timing: str,
    instructions: str,
    purpose: str,
    stock_quantity: int,
    updated_by: int = None,
):
    with get_connection() as conn:
        conn.execute(
            """UPDATE medications
               SET medicine_name = ?, dosage = ?, schedule_time = ?, frequency = ?, meal_timing = ?, instructions = ?, purpose = ?, stock_quantity = ?
               WHERE id = ? AND elderly_user_id = ?""",
            (medicine_name.strip(), dosage.strip(), schedule_time.strip(), frequency, meal_timing, instructions.strip(), purpose.strip(), int(stock_quantity), medication_id, elderly_user_id),
        )
    if updated_by:
        log_activity(
            elderly_user_id,
            updated_by,
            "Updated Medication",
            f"Updated {medicine_name} {dosage} details",
        )

def toggle_medication_status(medication_id: int, elderly_user_id: int, active: int, updated_by: int = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE medications SET active = ? WHERE id = ? AND elderly_user_id = ?",
            (active, medication_id, elderly_user_id),
        )
    status_label = "Reactivated" if active else "Paused"
    if updated_by:
        log_activity(
            elderly_user_id,
            updated_by,
            f"{status_label} Medication",
            f"Medication ID #{medication_id} marked as {status_label.lower()}",
        )

def delete_medication(medication_id: int, elderly_user_id: int, deleted_by: int = None):
    with get_connection() as conn:
        med = conn.execute("SELECT medicine_name FROM medications WHERE id = ? AND elderly_user_id = ?", (medication_id, elderly_user_id)).fetchone()
        name = med["medicine_name"] if med else f"#{medication_id}"
        conn.execute("DELETE FROM medications WHERE id = ? AND elderly_user_id = ?", (medication_id, elderly_user_id))
    if deleted_by:
        log_activity(
            elderly_user_id,
            deleted_by,
            "Discontinued Medication",
            f"Removed medication {name}",
        )

def get_today_schedule(elderly_user_id: int, target_date: str = None):
    if not target_date:
        target_date = date.today().isoformat()
        
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT m.id as medication_id, m.medicine_name, m.dosage, m.schedule_time,
                      m.frequency, m.meal_timing, m.instructions, m.purpose, m.stock_quantity,
                      COALESCE(ml.status, 'pending') as status,
                      ml.id as log_id, ml.notes as log_notes, ml.recorded_at,
                      u.name as recorded_by_name
               FROM medications m
               LEFT JOIN medication_logs ml ON m.id = ml.medication_id AND ml.scheduled_date = ?
               LEFT JOIN users u ON ml.recorded_by = u.id
               WHERE m.elderly_user_id = ? AND m.active = 1
               ORDER BY m.schedule_time ASC""",
            (target_date, elderly_user_id),
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
        item["is_overdue"] = is_overdue
        schedule.append(item)

    return schedule

def record_dose_status(
    medication_id: int,
    elderly_user_id: int,
    scheduled_date: str,
    scheduled_time: str,
    status: str,
    recorded_by: int,
    notes: str = "",
):
    with get_connection() as conn:
        # Check existing log
        existing = conn.execute(
            "SELECT id, status FROM medication_logs WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ?",
            (medication_id, scheduled_date, scheduled_time),
        ).fetchone()

        if existing:
            prev_status = existing["status"]
            conn.execute(
                """UPDATE medication_logs
                   SET status = ?, notes = ?, recorded_by = ?, recorded_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (status, notes, recorded_by, existing["id"]),
            )
            # If changing to 'taken' from non-taken, decrement stock
            if status == "taken" and prev_status != "taken":
                conn.execute(
                    "UPDATE medications SET stock_quantity = MAX(0, stock_quantity - 1) WHERE id = ?",
                    (medication_id,),
                )
            # If reverting from 'taken' to something else, restore stock
            elif prev_status == "taken" and status != "taken":
                conn.execute(
                    "UPDATE medications SET stock_quantity = stock_quantity + 1 WHERE id = ?",
                    (medication_id,),
                )
        else:
            conn.execute(
                """INSERT INTO medication_logs
                   (medication_id, scheduled_date, scheduled_time, status, notes, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (medication_id, scheduled_date, scheduled_time, status, notes, recorded_by),
            )
            if status == "taken":
                conn.execute(
                    "UPDATE medications SET stock_quantity = MAX(0, stock_quantity - 1) WHERE id = ?",
                    (medication_id,),
                )

        med = conn.execute("SELECT medicine_name, dosage FROM medications WHERE id = ?", (medication_id,)).fetchone()
        med_name = f"{med['medicine_name']} ({med['dosage']})" if med else f"Medication #{medication_id}"

    user_label = "Caregiver / User"
    action_label = {
        "taken": "Dose Confirmed Taken",
        "missed": "Dose Marked as Missed",
        "skipped": "Dose Skipped",
        "pending": "Dose Reset to Pending",
    }.get(status, "Dose Status Updated")

    log_activity(
        elderly_user_id,
        recorded_by,
        action_label,
        f"{med_name} scheduled for {scheduled_time} marked as '{status.upper()}'. {notes}".strip(),
    )

def get_adherence_metrics(elderly_user_id: int, days: int = 7):
    today = date.today()
    start_date = (today - timedelta(days=days - 1)).isoformat()
    end_date = today.isoformat()

    with get_connection() as conn:
        logs = conn.execute(
            """SELECT ml.scheduled_date, ml.status, COUNT(*) as count
               FROM medication_logs ml
               JOIN medications m ON ml.medication_id = m.id
               WHERE m.elderly_user_id = ? AND ml.scheduled_date BETWEEN ? AND ?
               GROUP BY ml.scheduled_date, ml.status""",
            (elderly_user_id, start_date, end_date),
        ).fetchall()

        low_stock = conn.execute(
            """SELECT id, medicine_name, dosage, stock_quantity
               FROM medications
               WHERE elderly_user_id = ? AND active = 1 AND stock_quantity <= 7
               ORDER BY stock_quantity ASC""",
            (elderly_user_id,),
        ).fetchall()

    daily_data = {}
    for i in range(days):
        d_str = (today - timedelta(days=days - 1 - i)).isoformat()
        daily_data[d_str] = {"taken": 0, "missed": 0, "skipped": 0, "pending": 0}

    total_taken = 0
    total_missed = 0
    total_skipped = 0
    total_pending = 0

    for r in logs:
        d = r["scheduled_date"]
        st = r["status"]
        cnt = r["count"]
        if d in daily_data and st in daily_data[d]:
            daily_data[d][st] += cnt
        if st == "taken":
            total_taken += cnt
        elif st == "missed":
            total_missed += cnt
        elif st == "skipped":
            total_skipped += cnt
        elif st == "pending":
            total_pending += cnt

    scheduled_total = total_taken + total_missed + total_skipped
    adherence_pct = round((total_taken / scheduled_total * 100), 1) if scheduled_total > 0 else 100.0

    return {
        "adherence_percentage": adherence_pct,
        "total_taken": total_taken,
        "total_missed": total_missed,
        "total_skipped": total_skipped,
        "total_pending": total_pending,
        "daily_breakdown": daily_data,
        "low_stock_meds": [dict(m) for m in low_stock],
    }
