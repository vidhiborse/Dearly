import unittest
import sqlite3
from datetime import date, datetime, timedelta

from database import init_db, create_demo_users, get_connection
from services.medication_service import (
    add_medication,
    record_dose_status,
    get_today_schedule,
    get_adherence_metrics,
)
from services.reminder_service import (
    get_user_reminder_settings,
    update_user_reminder_settings,
    format_time_display,
    calculate_reminder_status,
    get_upcoming_and_active_reminders,
    sync_reminders_and_escalations,
    get_user_notifications,
    get_unread_notification_count,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_caregiver_escalations,
    acknowledge_caregiver_escalation,
)


class TestPhase4Reminders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()
        with get_connection() as conn:
            # Clean prior test artifacts
            conn.execute("DELETE FROM users WHERE email LIKE '%@testreminders.demo'")

            # Elderly Profile A
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Alpha', 'alpha@testreminders.demo', 'hash123', 'elderly', '+91 98888 11111')"""
            )
            cls.elderly_a_id = conn.execute("SELECT id FROM users WHERE email = 'alpha@testreminders.demo'").fetchone()["id"]

            # Elderly Profile B (for multi-profile isolation testing)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Beta', 'beta@testreminders.demo', 'hash123', 'elderly', '+91 98888 22222')"""
            )
            cls.elderly_b_id = conn.execute("SELECT id FROM users WHERE email = 'beta@testreminders.demo'").fetchone()["id"]

            # Caregiver (Editor for A)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Nurse Priya', 'priya@testreminders.demo', 'hash123', 'caregiver', '+91 98888 33333')"""
            )
            cls.caregiver_id = conn.execute("SELECT id FROM users WHERE email = 'priya@testreminders.demo'").fetchone()["id"]

            # Family Member (Viewer for A)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Family Rohan', 'rohan@testreminders.demo', 'hash123', 'family', '+91 98888 44444')"""
            )
            cls.family_id = conn.execute("SELECT id FROM users WHERE email = 'rohan@testreminders.demo'").fetchone()["id"]

            # Unrelated Caregiver (No access to A)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Stranger Doc', 'stranger@testreminders.demo', 'hash123', 'caregiver', '+91 98888 55555')"""
            )
            cls.unrelated_id = conn.execute("SELECT id FROM users WHERE email = 'stranger@testreminders.demo'").fetchone()["id"]

            # Establish Care Circle permissions
            conn.execute(
                """INSERT INTO care_circle (elderly_user_id, member_user_id, relationship, permission_level)
                   VALUES (?, ?, 'Nurse', 'editor')""",
                (cls.elderly_a_id, cls.caregiver_id),
            )
            conn.execute(
                """INSERT INTO care_circle (elderly_user_id, member_user_id, relationship, permission_level)
                   VALUES (?, ?, 'Son', 'viewer')""",
                (cls.elderly_a_id, cls.family_id),
            )

        cls.elderly_a_user = {"id": cls.elderly_a_id, "role": "elderly", "name": "Senior Alpha"}
        cls.elderly_b_user = {"id": cls.elderly_b_id, "role": "elderly", "name": "Senior Beta"}
        cls.caregiver_user = {"id": cls.caregiver_id, "role": "caregiver", "name": "Nurse Priya"}
        cls.family_user = {"id": cls.family_id, "role": "family", "name": "Family Rohan"}
        cls.unrelated_user = {"id": cls.unrelated_id, "role": "caregiver", "name": "Stranger Doc"}

    @classmethod
    def tearDownClass(cls):
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE email LIKE '%@testreminders.demo'")

    def setUp(self):
        # Clear reminders and logs for elderly A and B before each test
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE elderly_user_id IN (?, ?)", (self.elderly_a_id, self.elderly_b_id))
            conn.execute("DELETE FROM caregiver_escalations WHERE elderly_user_id IN (?, ?)", (self.elderly_a_id, self.elderly_b_id))
            conn.execute("DELETE FROM medication_logs WHERE medication_id IN (SELECT id FROM medications WHERE elderly_user_id IN (?, ?))", (self.elderly_a_id, self.elderly_b_id))
            conn.execute("DELETE FROM medications WHERE elderly_user_id IN (?, ?)", (self.elderly_a_id, self.elderly_b_id))
            conn.execute("DELETE FROM reminder_settings WHERE user_id IN (?, ?, ?, ?)", (self.elderly_a_id, self.elderly_b_id, self.caregiver_id, self.family_id))

    # Scenario 1: Upcoming reminder generation
    def test_01_upcoming_reminder_generation(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Metformin",
            dosage="500 mg",
            schedule_time="14:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Mock time: 10:00 (before scheduled time 14:00)
        simulated_now = datetime.strptime(f"{today_str} 10:00", "%Y-%m-%d %H:%M")
        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["medication_id"], med_id)
        self.assertEqual(reminders[0]["status"], "upcoming")
        self.assertEqual(reminders[0]["reminder_status"], "upcoming")

    # Scenario 2: Due-now reminder generation
    def test_02_due_now_reminder_generation(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Amlodipine",
            dosage="5 mg",
            schedule_time="14:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Mock time: 14:05 (within default 15 min grace period)
        simulated_now = datetime.strptime(f"{today_str} 14:05", "%Y-%m-%d %H:%M")
        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(reminders[0]["status"], "due_now")

        # Sync and verify notification creation
        sync_res = sync_reminders_and_escalations(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(sync_res["due_now"], 1)

        # Elderly sees notification
        notifs = get_user_notifications(self.elderly_a_user, alert_type="due_now")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["medication_id"], med_id)
        self.assertEqual(notifs[0]["alert_type"], "due_now")

    # Scenario 3: Overdue detection & caregiver escalation
    def test_03_overdue_detection(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Atorvastatin",
            dosage="20 mg",
            schedule_time="09:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Mock time: 09:25 (past 15-minute grace period ending at 09:15)
        simulated_now = datetime.strptime(f"{today_str} 09:25", "%Y-%m-%d %H:%M")
        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(reminders[0]["status"], "overdue")

        # Sync triggers escalation
        sync_res = sync_reminders_and_escalations(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(sync_res["overdue"], 1)
        self.assertEqual(sync_res["escalated"], 1)

        # Caregiver receives escalation notification
        cg_notifs = get_user_notifications(self.caregiver_user, alert_type="escalation")
        self.assertEqual(len(cg_notifs), 1)
        self.assertIn("Overdue Dose", cg_notifs[0]["title"])

        # Caregiver escalations table has record
        escalations = get_caregiver_escalations(self.caregiver_user, elderly_id=self.elderly_a_id)
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations[0]["status"], "pending")
        self.assertEqual(escalations[0]["is_acknowledged"], 0)

    # Scenario 4: Completed dose status
    def test_04_completed_dose_status(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Thyroxine",
            dosage="50 mcg",
            schedule_time="07:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Record dose as taken
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_a_id,
            scheduled_date=today_str,
            scheduled_time="07:00",
            status="taken",
            recorded_by=self.elderly_a_id,
            notes="Taken before breakfast",
            user=self.elderly_a_user,
        )
        # Check reminder status at 12:00 (past scheduled time)
        simulated_now = datetime.strptime(f"{today_str} 12:00", "%Y-%m-%d %H:%M")
        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(reminders[0]["status"], "completed")

    # Scenario 5: Skipped dose status
    def test_05_skipped_dose_status(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Paracetamol",
            dosage="500 mg",
            schedule_time="13:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Record dose as skipped
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_a_id,
            scheduled_date=today_str,
            scheduled_time="13:00",
            status="skipped",
            recorded_by=self.elderly_a_id,
            notes="Doctor advised to pause today",
            user=self.elderly_a_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 14:00", "%Y-%m-%d %H:%M")
        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        self.assertEqual(reminders[0]["status"], "skipped")

    # Scenario 6: Grace-period calculation
    def test_06_grace_period_calculation(self):
        # Configure 20 min grace period for Elderly A
        update_user_reminder_settings(self.elderly_a_id, grace_period_minutes=20)
        today_str = date.today().isoformat()
        sched_time = "10:00"

        # 1. Before scheduled time -> upcoming
        t1 = datetime.strptime(f"{today_str} 09:59", "%Y-%m-%d %H:%M")
        st1 = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=20, now_dt=t1)
        self.assertEqual(st1, "upcoming")

        # 2. At scheduled time -> due_now
        t2 = datetime.strptime(f"{today_str} 10:00", "%Y-%m-%d %H:%M")
        st2 = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=20, now_dt=t2)
        self.assertEqual(st2, "due_now")

        # 3. Inside grace period (10:15) -> due_now
        t3 = datetime.strptime(f"{today_str} 10:15", "%Y-%m-%d %H:%M")
        st3 = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=20, now_dt=t3)
        self.assertEqual(st3, "due_now")

        # 4. At exact boundary (10:20) -> due_now
        t4 = datetime.strptime(f"{today_str} 10:20", "%Y-%m-%d %H:%M")
        st4 = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=20, now_dt=t4)
        self.assertEqual(st4, "due_now")

        # 5. Past grace period (10:21) -> overdue
        t5 = datetime.strptime(f"{today_str} 10:21", "%Y-%m-%d %H:%M")
        st5 = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=20, now_dt=t5)
        self.assertEqual(st5, "overdue")

    # Scenario 7: Medication start and end date handling
    def test_07_medication_start_and_end_date_handling(self):
        today = date.today()
        yesterday_str = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()
        tomorrow_str = (today + timedelta(days=1)).isoformat()

        # Med 1: Active today (starts today)
        m_active = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Active Med",
            dosage="1 tab",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Med 2: Future start (starts tomorrow)
        m_future = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Future Med",
            dosage="1 tab",
            schedule_time="09:00",
            start_date=tomorrow_str,
            user=self.caregiver_user,
        )
        # Med 3: Expired yesterday (ended yesterday)
        m_expired = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Expired Med",
            dosage="1 tab",
            schedule_time="10:00",
            start_date=yesterday_str,
            end_date=yesterday_str,
            user=self.caregiver_user,
        )

        reminders = get_upcoming_and_active_reminders(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            user=self.elderly_a_user,
        )
        med_ids = [r["medication_id"] for r in reminders]
        self.assertIn(m_active, med_ids)
        self.assertNotIn(m_future, med_ids)
        self.assertNotIn(m_expired, med_ids)

    # Scenario 8: Duplicate reminder prevention
    def test_08_duplicate_reminder_prevention(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Calcium",
            dosage="500 mg",
            schedule_time="11:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 11:05", "%Y-%m-%d %H:%M")

        # Call sync 5 times consecutively
        for _ in range(5):
            sync_reminders_and_escalations(
                elderly_user_id=self.elderly_a_id,
                target_date=today_str,
                now_dt=simulated_now,
                user=self.elderly_a_user,
            )

        with get_connection() as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE elderly_user_id = ? AND alert_type = 'due_now'",
                (self.elderly_a_id,),
            ).fetchone()["c"]
        self.assertEqual(cnt, 1, "Expected exactly 1 due_now notification despite 5 sync invocations")

    # Scenario 9: Duplicate caregiver escalation prevention
    def test_09_duplicate_caregiver_escalation_prevention(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Losartan",
            dosage="50 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 09:30", "%Y-%m-%d %H:%M")

        # Call sync 5 times when overdue
        for _ in range(5):
            sync_reminders_and_escalations(
                elderly_user_id=self.elderly_a_id,
                target_date=today_str,
                now_dt=simulated_now,
                user=self.elderly_a_user,
            )

        with get_connection() as conn:
            esc_cnt = conn.execute(
                "SELECT COUNT(*) as c FROM caregiver_escalations WHERE elderly_user_id = ? AND caregiver_user_id = ?",
                (self.elderly_a_id, self.caregiver_id),
            ).fetchone()["c"]
            notif_cnt = conn.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND alert_type = 'escalation'",
                (self.caregiver_id,),
            ).fetchone()["c"]
        self.assertEqual(esc_cnt, 1, "Expected exactly 1 caregiver escalation record")
        self.assertEqual(notif_cnt, 1, "Expected exactly 1 escalation notification for caregiver")

    # Scenario 10: Caregiver acknowledgement
    def test_10_caregiver_acknowledgement(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Metoprolol",
            dosage="25 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 09:00", "%Y-%m-%d %H:%M")
        sync_reminders_and_escalations(
            elderly_user_id=self.elderly_a_id,
            target_date=today_str,
            now_dt=simulated_now,
            user=self.elderly_a_user,
        )
        escalations = get_caregiver_escalations(self.caregiver_user, elderly_id=self.elderly_a_id)
        self.assertEqual(len(escalations), 1)
        esc_id = escalations[0]["id"]

        # Caregiver acknowledges
        success = acknowledge_caregiver_escalation(
            escalation_id=esc_id,
            caregiver_user=self.caregiver_user,
            notes="Called patient, assisting in 10 minutes",
        )
        self.assertTrue(success)

        # Verify acknowledgement recorded
        updated_escs = get_caregiver_escalations(self.caregiver_user, elderly_id=self.elderly_a_id)
        self.assertEqual(updated_escs[0]["is_acknowledged"], 1)
        self.assertEqual(updated_escs[0]["acknowledged_by"], self.caregiver_id)
        self.assertEqual(updated_escs[0]["status"], "acknowledged")
        self.assertIsNotNone(updated_escs[0]["acknowledged_at"])

        # Crucial check: Acknowledging does NOT falsely mark the medication as taken!
        with get_connection() as conn:
            log_row = conn.execute(
                "SELECT status FROM medication_logs WHERE medication_id = ? AND scheduled_date = ?",
                (med_id, today_str),
            ).fetchone()
        status_val = log_row["status"] if log_row else "pending"
        self.assertNotEqual(status_val, "taken", "Acknowledging an escalation must not mark dose as taken")

    # Scenario 11: Notification read/unread status
    def test_11_notification_read_unread_status(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Vitamin D3",
            dosage="1000 IU",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 08:05", "%Y-%m-%d %H:%M")
        sync_reminders_and_escalations(self.elderly_a_id, today_str, now_dt=simulated_now, user=self.elderly_a_user)

        initial_unread = get_unread_notification_count(self.elderly_a_id)
        self.assertGreater(initial_unread, 0)

        notifs = get_user_notifications(self.elderly_a_user, unread_only=True)
        self.assertEqual(len(notifs), initial_unread)
        notif_id = notifs[0]["id"]

        # Mark single as read
        mark_notification_as_read(notif_id, self.elderly_a_id)
        self.assertEqual(get_unread_notification_count(self.elderly_a_id), initial_unread - 1)

        # Mark all as read
        mark_all_notifications_as_read(self.elderly_a_id)
        self.assertEqual(get_unread_notification_count(self.elderly_a_id), 0)

    # Scenario 12: Notification persistence after restart
    def test_12_notification_persistence_after_restart(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Zinc Sulfate",
            dosage="50 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        simulated_now = datetime.strptime(f"{today_str} 08:05", "%Y-%m-%d %H:%M")
        sync_reminders_and_escalations(self.elderly_a_id, today_str, now_dt=simulated_now, user=self.elderly_a_user)

        # Verify DB connection close and re-open
        with get_connection() as conn:
            row = conn.execute(
                "SELECT title FROM notifications WHERE elderly_user_id = ? AND alert_type = 'due_now'",
                (self.elderly_a_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertIn("Zinc Sulfate", row["title"])

    # Scenario 13: Role-based access control
    def test_13_role_based_access_control(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Digoxin",
            dosage="0.25 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )

        # 1. Elderly A can access their own reminders
        rems = get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.elderly_a_user)
        self.assertEqual(len(rems), 1)

        # 2. Caregiver Priya is authorized for Elderly A
        cg_rems = get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.caregiver_user)
        self.assertEqual(len(cg_rems), 1)

        # 3. Family Rohan is authorized viewer for Elderly A
        fam_rems = get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.family_user)
        self.assertEqual(len(fam_rems), 1)

        # 4. Stranger caregiver is NOT authorized -> PermissionError
        with self.assertRaises(PermissionError):
            get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.unrelated_user)

        with self.assertRaises(PermissionError):
            get_caregiver_escalations(self.unrelated_user, elderly_id=self.elderly_a_id)

    # Scenario 14: Multiple elderly profiles isolation
    def test_14_multiple_elderly_profiles_isolation(self):
        today_str = date.today().isoformat()
        # Add med for Senior Alpha
        m_a = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Med Alpha",
            dosage="10 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        # Add med for Senior Beta
        m_b = add_medication(
            elderly_user_id=self.elderly_b_id,
            medicine_name="Med Beta",
            dosage="20 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.elderly_b_user,
        )

        sim_now = datetime.strptime(f"{today_str} 08:05", "%Y-%m-%d %H:%M")
        sync_reminders_and_escalations(self.elderly_a_id, today_str, now_dt=sim_now, user=self.elderly_a_user)
        sync_reminders_and_escalations(self.elderly_b_id, today_str, now_dt=sim_now, user=self.elderly_b_user)

        rems_a = get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.elderly_a_user)
        rems_b = get_upcoming_and_active_reminders(self.elderly_b_id, today_str, user=self.elderly_b_user)

        self.assertEqual(len(rems_a), 1)
        self.assertEqual(rems_a[0]["medicine_name"], "Med Alpha")
        self.assertEqual(len(rems_b), 1)
        self.assertEqual(rems_b[0]["medicine_name"], "Med Beta")

        # Notifications isolation
        notifs_a = get_user_notifications(self.elderly_a_user)
        notifs_b = get_user_notifications(self.elderly_b_user)
        self.assertTrue(all(n["elderly_user_id"] == self.elderly_a_id for n in notifs_a))
        self.assertTrue(all(n["elderly_user_id"] == self.elderly_b_id for n in notifs_b))

    # Scenario 15: Timezone and date-boundary handling
    def test_15_timezone_and_date_boundary_handling(self):
        # Test reminder evaluation for a midnight boundary edge case (23:55)
        today_str = "2026-11-15"
        sched_time = "23:55"
        now_dt = datetime.strptime("2026-11-16 00:05", "%Y-%m-%d %H:%M") # 10 min past midnight
        # Grace period 15 min: 23:55 to 00:10 next day
        st = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=15, now_dt=now_dt)
        self.assertEqual(st, "due_now")

        now_dt_overdue = datetime.strptime("2026-11-16 00:15", "%Y-%m-%d %H:%M")
        st_overdue = calculate_reminder_status(sched_time, today_str, "pending", grace_period_minutes=15, now_dt=now_dt_overdue)
        self.assertEqual(st_overdue, "overdue")

    # Scenario 16: Reminder generation after application refresh
    def test_16_reminder_generation_after_application_refresh(self):
        today_str = date.today().isoformat()
        add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Aspirin",
            dosage="81 mg",
            schedule_time="08:00",
            start_date=today_str,
            user=self.caregiver_user,
        )
        sim_now = datetime.strptime(f"{today_str} 08:30", "%Y-%m-%d %H:%M") # Overdue

        # Refresh 1
        res1 = sync_reminders_and_escalations(self.elderly_a_id, today_str, now_dt=sim_now, user=self.elderly_a_user)
        count_notifs_1 = len(get_user_notifications(self.caregiver_user))
        count_escs_1 = len(get_caregiver_escalations(self.caregiver_user, elderly_id=self.elderly_a_id))

        # Refresh 2
        res2 = sync_reminders_and_escalations(self.elderly_a_id, today_str, now_dt=sim_now, user=self.elderly_a_user)
        count_notifs_2 = len(get_user_notifications(self.caregiver_user))
        count_escs_2 = len(get_caregiver_escalations(self.caregiver_user, elderly_id=self.elderly_a_id))

        self.assertEqual(count_notifs_1, count_notifs_2)
        self.assertEqual(count_escs_1, count_escs_2)

    # Scenario 17: Existing Phase 3 medication functionality regression
    def test_17_existing_phase3_medication_regression(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.elderly_a_id,
            medicine_name="Glipizide",
            dosage="5 mg",
            schedule_time="08:00",
            frequency="Daily",
            start_date=today_str,
            stock_quantity=30,
            user=self.caregiver_user,
        )
        # Verify Phase 3 schedule fetching
        sched = get_today_schedule(self.elderly_a_id, today_str, user=self.elderly_a_user)
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0]["medication_id"], med_id)

        # Record dose taken
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_a_id,
            scheduled_date=today_str,
            scheduled_time="08:00",
            status="taken",
            recorded_by=self.elderly_a_id,
            user=self.elderly_a_user,
        )

        # Adherence calculation
        metrics = get_adherence_metrics(self.elderly_a_id, days=7)
        self.assertEqual(metrics["adherence_percentage"], 100.0)
        self.assertEqual(metrics["total_taken"], 1)

        # Reminder service confirms completed status
        rems = get_upcoming_and_active_reminders(self.elderly_a_id, today_str, user=self.elderly_a_user)
        self.assertEqual(rems[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
