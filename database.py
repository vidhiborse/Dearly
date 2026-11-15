import sqlite3
import hashlib
import bcrypt
from pathlib import Path
from datetime import datetime, date, timedelta

DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "dearly.db"

def get_connection():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    # Use bcrypt with standard work factor 12
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("$2a$") or hashed_password.startswith("$2b$") or hashed_password.startswith("$2y$"):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        # Fallback for existing prototype SHA-256 hashes
        return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password
    except Exception:
        return False

def ensure_column(conn, table, col_name, col_type):
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing_cols = [col[1] for col in info]
    if col_name not in existing_cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('elderly','caregiver','family')),
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS elderly_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            date_of_birth TEXT,
            blood_group TEXT,
            emergency_contact TEXT,
            allergies TEXT,
            primary_physician TEXT,
            primary_physician_phone TEXT,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            medication_type TEXT DEFAULT 'Tablet',
            schedule_time TEXT NOT NULL,
            frequency TEXT DEFAULT 'Daily',
            meal_timing TEXT DEFAULT 'After Meal',
            instructions TEXT,
            purpose TEXT,
            start_date TEXT,
            end_date TEXT,
            prescribing_doctor TEXT,
            notes TEXT,
            stock_quantity INTEGER DEFAULT 30,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS medication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            scheduled_date TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            actual_action_time TEXT,
            status TEXT NOT NULL CHECK(status IN ('taken','missed','skipped','pending')),
            notes TEXT,
            recorded_by INTEGER,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(medication_id, scheduled_date, scheduled_time),
            FOREIGN KEY(medication_id) REFERENCES medications(id) ON DELETE CASCADE,
            FOREIGN KEY(recorded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            specialization TEXT,
            hospital TEXT,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            appointment_type TEXT DEFAULT 'General check-up',
            location TEXT,
            reason TEXT,
            purpose TEXT,
            notes TEXT,
            post_visit_notes TEXT,
            status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming','completed','cancelled','missed')),
            reminder_sent INTEGER DEFAULT 0,
            created_by INTEGER,
            updated_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS appointment_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            elderly_user_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL CHECK(reminder_type IN ('1_day_before', '1_hour_before')),
            scheduled_for TEXT NOT NULL,
            is_sent INTEGER DEFAULT 0,
            sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(appointment_id, user_id, reminder_type),
            FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS health_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            reading_type TEXT NOT NULL,
            reading_value TEXT NOT NULL,
            recorded_on TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS care_circle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            member_user_id INTEGER NOT NULL,
            relationship TEXT,
            permission_level TEXT DEFAULT 'viewer' CHECK(permission_level IN ('editor','viewer')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(elderly_user_id, member_user_id),
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(member_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS emergency_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            triggered_by_user_id INTEGER NOT NULL,
            alert_type TEXT DEFAULT 'SOS',
            status TEXT DEFAULT 'active' CHECK(status IN ('active','acknowledged','resolved')),
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(triggered_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS simulated_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            channel TEXT DEFAULT 'email',
            status TEXT DEFAULT 'simulated_sent',
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            elderly_user_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL CHECK(alert_type IN ('upcoming', 'due_now', 'overdue', 'completed', 'skipped', 'escalation', 'system')),
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            medication_id INTEGER,
            scheduled_date TEXT,
            scheduled_time TEXT,
            is_read INTEGER DEFAULT 0,
            read_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, medication_id, scheduled_date, scheduled_time, alert_type),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(medication_id) REFERENCES medications(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS caregiver_escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL,
            elderly_user_id INTEGER NOT NULL,
            caregiver_user_id INTEGER NOT NULL,
            scheduled_date TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'acknowledged', 'resolved')),
            escalated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_acknowledged INTEGER DEFAULT 0,
            acknowledged_at TEXT,
            acknowledged_by INTEGER,
            UNIQUE(medication_id, scheduled_date, scheduled_time, caregiver_user_id),
            FOREIGN KEY(medication_id) REFERENCES medications(id) ON DELETE CASCADE,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(caregiver_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(acknowledged_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reminder_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            grace_period_minutes INTEGER DEFAULT 15,
            enable_reminders INTEGER DEFAULT 1,
            enable_escalation INTEGER DEFAULT 1,
            time_format TEXT DEFAULT '12h' CHECK(time_format IN ('12h', '24h')),
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS care_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            inviter_user_id INTEGER NOT NULL,
            invitee_email TEXT NOT NULL,
            invitee_user_id INTEGER,
            relationship TEXT NOT NULL,
            connection_role TEXT NOT NULL CHECK(connection_role IN ('caregiver', 'family')),
            permission_level TEXT DEFAULT 'viewer' CHECK(permission_level IN ('editor', 'viewer')),
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected', 'revoked', 'expired')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            responded_at TEXT,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(inviter_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(invitee_user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS care_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elderly_user_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            visibility TEXT DEFAULT 'circle' CHECK(visibility IN ('circle', 'caregivers_only')),
            is_archived INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_medications_elderly ON medications(elderly_user_id, active);
        CREATE INDEX IF NOT EXISTS idx_medication_logs_lookup ON medication_logs(medication_id, scheduled_date);
        CREATE INDEX IF NOT EXISTS idx_appointments_elderly ON appointments(elderly_user_id, appointment_date);
        CREATE INDEX IF NOT EXISTS idx_health_readings_elderly ON health_readings(elderly_user_id, recorded_on);
        CREATE INDEX IF NOT EXISTS idx_activity_logs_elderly ON activity_logs(elderly_user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
        CREATE INDEX IF NOT EXISTS idx_notifications_elderly ON notifications(elderly_user_id, alert_type);
        CREATE INDEX IF NOT EXISTS idx_escalations_caregiver ON caregiver_escalations(caregiver_user_id, is_acknowledged);
        CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON care_invitations(invitee_email, status);
        CREATE INDEX IF NOT EXISTS idx_invitations_elderly ON care_invitations(elderly_user_id, status);
        CREATE INDEX IF NOT EXISTS idx_care_notes_elderly ON care_notes(elderly_user_id, is_archived);
        CREATE INDEX IF NOT EXISTS idx_appt_reminders_user ON appointment_reminders(user_id, is_sent);
        CREATE INDEX IF NOT EXISTS idx_appt_reminders_appt ON appointment_reminders(appointment_id, reminder_type);
        """)

        # Migration: Ensure appointments table accommodates 'missed' status and new fields
        appt_schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='appointments'").fetchone()
        if appt_schema and "'missed'" not in appt_schema["sql"]:
            conn.execute("""
                CREATE TABLE appointments_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    elderly_user_id INTEGER NOT NULL,
                    doctor_name TEXT NOT NULL,
                    specialization TEXT,
                    hospital TEXT,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    appointment_type TEXT DEFAULT 'General check-up',
                    location TEXT,
                    reason TEXT,
                    purpose TEXT,
                    notes TEXT,
                    post_visit_notes TEXT,
                    status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming','completed','cancelled','missed')),
                    reminder_sent INTEGER DEFAULT 0,
                    created_by INTEGER,
                    updated_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO appointments_migrated (
                    id, elderly_user_id, doctor_name, hospital, appointment_date, appointment_time,
                    purpose, reason, status, notes, reminder_sent, created_at
                )
                SELECT id, elderly_user_id, doctor_name, hospital, appointment_date, appointment_time,
                       purpose, purpose, status, notes, reminder_sent, created_at
                FROM appointments
            """)
            conn.execute("DROP TABLE appointments")
            conn.execute("ALTER TABLE appointments_migrated RENAME TO appointments")

        ensure_column(conn, "users", "phone", "TEXT")
        ensure_column(conn, "users", "updated_at", "TEXT")
        ensure_column(conn, "elderly_profiles", "blood_group", "TEXT")
        ensure_column(conn, "elderly_profiles", "allergies", "TEXT")
        ensure_column(conn, "elderly_profiles", "primary_physician", "TEXT")
        ensure_column(conn, "elderly_profiles", "primary_physician_phone", "TEXT")
        ensure_column(conn, "medications", "meal_timing", "TEXT DEFAULT 'After Meal'")
        ensure_column(conn, "medications", "instructions", "TEXT")
        ensure_column(conn, "medications", "purpose", "TEXT")
        ensure_column(conn, "medications", "medication_type", "TEXT DEFAULT 'Tablet'")
        ensure_column(conn, "medications", "prescribing_doctor", "TEXT")
        ensure_column(conn, "medications", "notes", "TEXT")
        ensure_column(conn, "medications", "updated_at", "TEXT")
        ensure_column(conn, "medication_logs", "actual_action_time", "TEXT")
        ensure_column(conn, "care_circle", "connection_role", "TEXT DEFAULT 'family'")
        ensure_column(conn, "care_circle", "status", "TEXT DEFAULT 'active'")
        ensure_column(conn, "care_circle", "is_primary", "INTEGER DEFAULT 0")
        ensure_column(conn, "care_circle", "created_by", "INTEGER")
        ensure_column(conn, "care_circle", "updated_at", "TEXT")
        ensure_column(conn, "appointments", "specialization", "TEXT")
        ensure_column(conn, "appointments", "appointment_type", "TEXT DEFAULT 'General check-up'")
        ensure_column(conn, "appointments", "location", "TEXT")
        ensure_column(conn, "appointments", "reason", "TEXT")
        ensure_column(conn, "appointments", "post_visit_notes", "TEXT")
        ensure_column(conn, "appointments", "created_by", "INTEGER")
        ensure_column(conn, "appointments", "updated_by", "INTEGER")
        ensure_column(conn, "appointments", "updated_at", "TEXT")

def create_demo_users():
    demo_users = [
        ("Asha Patil", "elderly@dearly.demo", "demo123", "elderly", "+91 98201 11000"),
        ("Rahul Patil", "caregiver@dearly.demo", "demo123", "caregiver", "+91 98200 12345"),
        ("Neha Patil", "family@dearly.demo", "demo123", "family", "+91 98200 54321"),
    ]
    with get_connection() as conn:
        for name, email, password, role, phone in demo_users:
            conn.execute(
                """INSERT OR IGNORE INTO users (name, email, password_hash, role, phone)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, email, hash_password(password), role, phone),
            )

        elderly = conn.execute("SELECT id FROM users WHERE email = ?", ("elderly@dearly.demo",)).fetchone()
        caregiver = conn.execute("SELECT id FROM users WHERE email = ?", ("caregiver@dearly.demo",)).fetchone()
        family = conn.execute("SELECT id FROM users WHERE email = ?", ("family@dearly.demo",)).fetchone()

        if elderly:
            e_id = elderly["id"]
            # Seed profile if not exists
            conn.execute(
                """INSERT OR IGNORE INTO elderly_profiles
                   (user_id, date_of_birth, blood_group, emergency_contact, allergies, primary_physician, primary_physician_phone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    e_id,
                    "1952-04-12",
                    "O+",
                    "Rahul Patil (Caregiver / Son): +91 98200 12345",
                    "Penicillin (Mild rash)",
                    "Dr. Sunita Kulkarni (Cardiology)",
                    "+91 98111 22334",
                    "Mild hypertension, osteoarthritis in right knee. Manages daily routine with supervision."
                ),
            )

            # Care circle
            if caregiver:
                conn.execute(
                    """INSERT OR REPLACE INTO care_circle
                       (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                       VALUES (?, ?, ?, ?, 'caregiver', 'active', 1)""",
                    (e_id, caregiver["id"], "Son", "editor"),
                )
            if family:
                conn.execute(
                    """INSERT OR REPLACE INTO care_circle
                       (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                       VALUES (?, ?, ?, ?, 'family', 'active', 0)""",
                    (e_id, family["id"], "Daughter", "viewer"),
                )

            # Seed demo care note
            if caregiver:
                conn.execute(
                    """INSERT OR IGNORE INTO care_notes
                       (elderly_user_id, author_id, title, content, category, visibility)
                       VALUES (?, ?, 'Morning Routine & Vitals Check', 'Asha completed morning routine comfortably. Blood pressure measured at 126/80 mmHg. Morning medications taken with warm breakfast.', 'routine', 'circle')""",
                    (e_id, caregiver["id"]),
                )

            # Seed demo medications if none exist
            existing_meds = conn.execute("SELECT COUNT(*) as count FROM medications WHERE elderly_user_id = ?", (e_id,)).fetchone()
            if existing_meds["count"] == 0:
                med_list = [
                    (e_id, "Metformin", "500 mg", "08:30", "Daily", "After Meal", "Take with water immediately after breakfast", "Type 2 Diabetes", "2026-01-01", 24, 1),
                    (e_id, "Amlodipine", "5 mg", "09:00", "Daily", "After Meal", "Blood pressure management", "Hypertension", "2026-01-01", 18, 1),
                    (e_id, "Calcium + Vit D3", "500 mg", "13:30", "Daily", "After Meal", "Take with milk or water after lunch", "Bone Density", "2026-01-01", 28, 1),
                    (e_id, "Atorvastatin", "10 mg", "20:30", "Daily", "After Meal", "Take after dinner before sleeping", "Cholesterol Control", "2026-01-01", 22, 1),
                    (e_id, "Paracetamol", "650 mg", "14:00", "As needed", "After Meal", "Take only if knee joint pain is severe", "Pain Relief", "2026-01-01", 12, 1),
                ]
                for med in med_list:
                    conn.execute(
                        """INSERT INTO medications
                           (elderly_user_id, medicine_name, dosage, schedule_time, frequency, meal_timing, instructions, purpose, start_date, stock_quantity, active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        med,
                    )

                # Seed medication logs for past 5 days and today
                all_meds = conn.execute("SELECT id, schedule_time FROM medications WHERE elderly_user_id = ? AND active = 1", (e_id,)).fetchall()
                today = date.today()
                c_id = caregiver["id"] if caregiver else e_id

                for offset in range(5, 0, -1):
                    past_date = (today - timedelta(days=offset)).isoformat()
                    for m in all_meds:
                        # 90% taken, 10% missed
                        status = "taken" if (m["id"] + offset) % 7 != 0 else "missed"
                        conn.execute(
                            """INSERT OR IGNORE INTO medication_logs
                               (medication_id, scheduled_date, scheduled_time, status, notes, recorded_by)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (m["id"], past_date, m["schedule_time"], status, "Routine verification", c_id),
                        )

                # Today's schedule: morning taken, afternoon and night pending
                today_str = today.isoformat()
                for m in all_meds:
                    if m["schedule_time"] in ["08:30", "09:00"]:
                        status = "taken"
                        notes = "Confirmed by Asha Patil at breakfast"
                    else:
                        status = "pending"
                        notes = "Awaiting scheduled time"
                    conn.execute(
                        """INSERT OR IGNORE INTO medication_logs
                           (medication_id, scheduled_date, scheduled_time, status, notes, recorded_by)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (m["id"], today_str, m["schedule_time"], status, notes, e_id),
                    )

            # Seed demo appointments
            existing_appts = conn.execute("SELECT COUNT(*) as count FROM appointments WHERE elderly_user_id = ?", (e_id,)).fetchone()
            if existing_appts["count"] == 0:
                today = date.today()
                appts = [
                    (e_id, "Dr. Sunita Kulkarni", "Apollo Heart Clinic, Khar", (today + timedelta(days=3)).isoformat(), "10:30 AM", "Quarterly Blood Pressure & ECG Review", "upcoming", "Carry previous prescription and last 14 days BP logs"),
                    (e_id, "Dr. Arvind Mehta", "Netra Eye Hospital, Bandra", (today + timedelta(days=12)).isoformat(), "04:00 PM", "Annual Diabetic Retinopathy Screen", "upcoming", "Dilation drops will be applied; arrange ride back"),
                    (e_id, "Dr. Ramesh Shah", "Pathcare Diagnostic Labs", (today - timedelta(days=14)).isoformat(), "08:00 AM", "Fasting Blood Sugar & Lipid Profile", "completed", "Reports uploaded to health records. Normal results."),
                ]
                for a in appts:
                    conn.execute(
                        """INSERT INTO appointments
                           (elderly_user_id, doctor_name, hospital, appointment_date, appointment_time, purpose, status, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        a,
                    )

            # Seed demo health readings (last 7 days)
            existing_readings = conn.execute("SELECT COUNT(*) as count FROM health_readings WHERE elderly_user_id = ?", (e_id,)).fetchone()
            if existing_readings["count"] == 0:
                today = date.today()
                readings = [
                    ("Blood Pressure", "124/80 mmHg", (today - timedelta(days=6)).isoformat(), "Resting morning reading"),
                    ("Blood Sugar (Fasting)", "112 mg/dL", (today - timedelta(days=6)).isoformat(), "Before breakfast"),
                    ("Heart Rate", "72 bpm", (today - timedelta(days=6)).isoformat(), "Normal rhythm"),
                    ("Blood Pressure", "128/82 mmHg", (today - timedelta(days=4)).isoformat(), "Post-breakfast"),
                    ("Blood Sugar (Fasting)", "118 mg/dL", (today - timedelta(days=4)).isoformat(), "Before breakfast"),
                    ("Oxygen Saturation (SpO2)", "98 %", (today - timedelta(days=3)).isoformat(), "Pulse oximeter"),
                    ("Blood Pressure", "122/78 mmHg", (today - timedelta(days=2)).isoformat(), "Resting morning reading"),
                    ("Blood Sugar (Fasting)", "108 mg/dL", (today - timedelta(days=2)).isoformat(), "Before breakfast"),
                    ("Heart Rate", "74 bpm", (today - timedelta(days=1)).isoformat(), "Morning reading"),
                    ("Blood Pressure", "126/80 mmHg", today.isoformat(), "Morning checkup with caregiver"),
                    ("Blood Sugar (Fasting)", "114 mg/dL", today.isoformat(), "Fasting reading"),
                    ("Oxygen Saturation (SpO2)", "98 %", today.isoformat(), "Resting state"),
                    ("Weight", "64.2 kg", today.isoformat(), "Weekly weigh-in"),
                ]
                for r in readings:
                    conn.execute(
                        """INSERT INTO health_readings (elderly_user_id, reading_type, reading_value, recorded_on, notes)
                           VALUES (?, ?, ?, ?, ?)""",
                        (e_id, r[0], r[1], r[2], r[3]),
                    )

            # Seed demo activity logs
            existing_act = conn.execute("SELECT COUNT(*) as count FROM activity_logs WHERE elderly_user_id = ?", (e_id,)).fetchone()
            if existing_act["count"] == 0:
                today = date.today()
                c_id = caregiver["id"] if caregiver else e_id
                activities = [
                    (e_id, e_id, "Dose Taken", "Asha marked Metformin 500 mg as Taken (08:30 AM dose)"),
                    (e_id, e_id, "Dose Taken", "Asha marked Amlodipine 5 mg as Taken (09:00 AM dose)"),
                    (e_id, c_id, "Health Reading Added", "Rahul recorded Blood Pressure: 126/80 mmHg"),
                    (e_id, c_id, "Appointment Scheduled", "Rahul scheduled Cardiology Follow-up with Dr. Sunita Kulkarni"),
                    (e_id, c_id, "Care Routine Verified", "Rahul checked daily medicine inventory (all doses in stock)"),
                ]
                for act in activities:
                    conn.execute(
                        """INSERT INTO activity_logs (elderly_user_id, actor_user_id, action, details)
                           VALUES (?, ?, ?, ?)""",
                        act,
                    )

            # Seed default reminder settings
            for u in [elderly, caregiver, family]:
                if u:
                    conn.execute(
                        """INSERT OR IGNORE INTO reminder_settings
                           (user_id, grace_period_minutes, enable_reminders, enable_escalation, time_format)
                           VALUES (?, 15, 1, 1, '12h')""",
                        (u["id"],),
                    )

def authenticate_user(email: str, password: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash, role, phone, created_at FROM users WHERE LOWER(email) = LOWER(?)",
            (email.strip(),),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            user = dict(row)
            user.pop("password_hash", None)
            return user
        return None
