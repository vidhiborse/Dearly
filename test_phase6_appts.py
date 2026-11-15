import unittest
import sqlite3
from datetime import date, datetime, timedelta

from database import init_db, create_demo_users, get_connection
from services.permissions import (
    can_access_elderly_record,
    can_manage_elderly_care,
    enforce_elderly_access,
)
from services.appointment_service import (
    add_appointment,
    get_appointments,
    get_appointment_by_id,
    get_next_upcoming_appointment,
    update_appointment,
    reschedule_appointment,
    cancel_appointment,
    complete_appointment,
    mark_appointment_missed,
    sync_appointment_reminders,
    get_appointment_calendar,
    get_appointment_history,
)
from services.reminder_service import get_user_notifications
from services.medication_service import add_medication, record_dose_status, get_today_schedule
from services.care_circle_service import get_care_circle_members


class TestPhase6DoctorAppointments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()
        with get_connection() as conn:
            # Clean prior test artifacts
            conn.execute("DELETE FROM users WHERE email LIKE '%@testappts.demo'")

            # Senior Alpha
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Alpha', 'alpha@testappts.demo', 'hash123', 'elderly', '+91 96666 11111')"""
            )
            cls.senior_a_id = conn.execute("SELECT id FROM users WHERE email = 'alpha@testappts.demo'").fetchone()["id"]

            # Senior Beta (Isolated)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Beta', 'beta@testappts.demo', 'hash123', 'elderly', '+91 96666 22222')"""
            )
            cls.senior_b_id = conn.execute("SELECT id FROM users WHERE email = 'beta@testappts.demo'").fetchone()["id"]

            # Caregiver (Editor for Alpha)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Nurse Shweta', 'shweta@testappts.demo', 'hash123', 'caregiver', '+91 96666 33333')"""
            )
            cls.caregiver_id = conn.execute("SELECT id FROM users WHERE email = 'shweta@testappts.demo'").fetchone()["id"]

            # Family Member (Viewer for Alpha)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Family Varun', 'varun@testappts.demo', 'hash123', 'family', '+91 96666 44444')"""
            )
            cls.family_id = conn.execute("SELECT id FROM users WHERE email = 'varun@testappts.demo'").fetchone()["id"]

            # Unrelated Stranger
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Stranger Seth', 'seth@testappts.demo', 'hash123', 'caregiver', '+91 96666 55555')"""
            )
            cls.stranger_id = conn.execute("SELECT id FROM users WHERE email = 'seth@testappts.demo'").fetchone()["id"]

            # Set up care circle links for Senior Alpha
            conn.execute(
                """INSERT INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                   VALUES (?, ?, 'Primary Caregiver', 'editor', 'caregiver', 'active', 1)""",
                (cls.senior_a_id, cls.caregiver_id),
            )
            conn.execute(
                """INSERT INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                   VALUES (?, ?, 'Son', 'viewer', 'family', 'active', 0)""",
                (cls.senior_a_id, cls.family_id),
            )

        cls.senior_a_user = {"id": cls.senior_a_id, "role": "elderly", "name": "Senior Alpha", "email": "alpha@testappts.demo"}
        cls.senior_b_user = {"id": cls.senior_b_id, "role": "elderly", "name": "Senior Beta", "email": "beta@testappts.demo"}
        cls.caregiver_user = {"id": cls.caregiver_id, "role": "caregiver", "name": "Nurse Shweta", "email": "shweta@testappts.demo"}
        cls.family_user = {"id": cls.family_id, "role": "family", "name": "Family Varun", "email": "varun@testappts.demo"}
        cls.stranger_user = {"id": cls.stranger_id, "role": "caregiver", "name": "Stranger Seth", "email": "seth@testappts.demo"}

    @classmethod
    def tearDownClass(cls):
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE email LIKE '%@testappts.demo'")

    def setUp(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM appointment_reminders WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))
            conn.execute("DELETE FROM appointments WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))
            conn.execute("DELETE FROM notifications WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))

    # Scenario 1: Create an appointment
    def test_01_create_appointment(self):
        target_date = (date.today() + timedelta(days=5)).isoformat()
        appt_id = add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Sunita Kulkarni",
            specialization="Cardiology",
            hospital="Apollo Heart Clinic, Khar",
            appointment_date=target_date,
            appointment_time="10:30 AM",
            appointment_type="Specialist consultation",
            location="2nd Floor, Room 204",
            reason="Quarterly blood pressure review",
            notes="Carry recent ECG and BP logs",
            user=self.caregiver_user,
        )
        self.assertIsNotNone(appt_id)
        self.assertGreater(appt_id, 0)

        appt = get_appointment_by_id(appt_id)
        self.assertEqual(appt["doctor_name"], "Dr. Sunita Kulkarni")
        self.assertEqual(appt["status"], "upcoming")
        self.assertEqual(appt["appointment_type"], "Specialist consultation")

    # Scenario 2: Reject missing required fields
    def test_02_reject_missing_required_fields(self):
        target_date = (date.today() + timedelta(days=3)).isoformat()

        # Missing doctor name
        with self.assertRaises(ValueError):
            add_appointment(
                elderly_user_id=self.senior_a_id,
                doctor_name="",
                hospital="City Clinic",
                appointment_date=target_date,
                appointment_time="10:00 AM",
                user=self.caregiver_user,
            )

        # Missing hospital
        with self.assertRaises(ValueError):
            add_appointment(
                elderly_user_id=self.senior_a_id,
                doctor_name="Dr. Smith",
                hospital="",
                appointment_date=target_date,
                appointment_time="10:00 AM",
                user=self.caregiver_user,
            )

        # Missing appointment time
        with self.assertRaises(ValueError):
            add_appointment(
                elderly_user_id=self.senior_a_id,
                doctor_name="Dr. Smith",
                hospital="City Clinic",
                appointment_date=target_date,
                appointment_time="",
                user=self.caregiver_user,
            )

    # Scenario 3: Reject invalid appointment dates
    def test_03_reject_invalid_appointment_dates(self):
        # Invalid format
        with self.assertRaises(ValueError):
            add_appointment(
                elderly_user_id=self.senior_a_id,
                doctor_name="Dr. Smith",
                hospital="City Clinic",
                appointment_date="invalid-date",
                appointment_time="10:00 AM",
                user=self.caregiver_user,
            )

        # Past date
        past_date = (date.today() - timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):
            add_appointment(
                elderly_user_id=self.senior_a_id,
                doctor_name="Dr. Smith",
                hospital="City Clinic",
                appointment_date=past_date,
                appointment_time="10:00 AM",
                user=self.caregiver_user,
                allow_past=False,
            )

    # Scenario 4: Display today's appointments
    def test_04_display_todays_appointments(self):
        today_str = date.today().isoformat()
        add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Today Reviewer",
            hospital="Metro Clinic",
            appointment_date=today_str,
            appointment_time="11:30 AM",
            user=self.caregiver_user,
            allow_past=True,
        )
        today_appts = get_appointments(self.senior_a_id, status="today", user=self.caregiver_user)
        self.assertEqual(len(today_appts), 1)
        self.assertEqual(today_appts[0]["doctor_name"], "Dr. Today Reviewer")

    # Scenario 5: Display upcoming appointments
    def test_05_display_upcoming_appointments(self):
        d1 = (date.today() + timedelta(days=2)).isoformat()
        d2 = (date.today() + timedelta(days=8)).isoformat()

        add_appointment(self.senior_a_id, "Dr. Soon", "Clinic A", d1, "10:00 AM", user=self.caregiver_user)
        add_appointment(self.senior_a_id, "Dr. Later", "Clinic B", d2, "02:00 PM", user=self.caregiver_user)

        upcoming = get_appointments(self.senior_a_id, status="upcoming", user=self.caregiver_user)
        self.assertEqual(len(upcoming), 2)
        doc_names = [a["doctor_name"] for a in upcoming]
        self.assertIn("Dr. Soon", doc_names)
        self.assertIn("Dr. Later", doc_names)

    # Scenario 6: Filter appointments by status
    def test_06_filter_appointments_by_status(self):
        d_future = (date.today() + timedelta(days=4)).isoformat()

        a1 = add_appointment(self.senior_a_id, "Dr. One", "Hosp 1", d_future, "09:00 AM", user=self.caregiver_user)
        a2 = add_appointment(self.senior_a_id, "Dr. Two", "Hosp 2", d_future, "11:00 AM", user=self.caregiver_user)
        a3 = add_appointment(self.senior_a_id, "Dr. Three", "Hosp 3", d_future, "03:00 PM", user=self.caregiver_user)

        complete_appointment(a2, self.senior_a_id, user=self.caregiver_user)
        cancel_appointment(a3, self.senior_a_id, user=self.caregiver_user)

        completed_list = get_appointments(self.senior_a_id, status="completed", user=self.caregiver_user)
        cancelled_list = get_appointments(self.senior_a_id, status="cancelled", user=self.caregiver_user)
        upcoming_list = get_appointments(self.senior_a_id, status="upcoming", user=self.caregiver_user)

        self.assertEqual(len(completed_list), 1)
        self.assertEqual(completed_list[0]["id"], a2)
        self.assertEqual(len(cancelled_list), 1)
        self.assertEqual(cancelled_list[0]["id"], a3)
        self.assertEqual(len(upcoming_list), 1)
        self.assertEqual(upcoming_list[0]["id"], a1)

    # Scenario 7: Edit appointment details
    def test_07_edit_appointment_details(self):
        target_date = (date.today() + timedelta(days=6)).isoformat()
        a_id = add_appointment(self.senior_a_id, "Dr. Arvind", "Old Clinic", target_date, "10:00 AM", user=self.caregiver_user)

        ok = update_appointment(
            appointment_id=a_id,
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Arvind Mehta",
            specialization="Ophthalmology",
            hospital="Netra Eye Super Specialty, Bandra",
            appointment_date=target_date,
            appointment_time="10:45 AM",
            appointment_type="Specialist consultation",
            location="Room 301, 3rd Floor",
            reason="Annual diabetic retinopathy examination",
            notes="Dilation drops will be applied",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        updated = get_appointment_by_id(a_id)
        self.assertEqual(updated["doctor_name"], "Dr. Arvind Mehta")
        self.assertEqual(updated["specialization"], "Ophthalmology")
        self.assertEqual(updated["appointment_time"], "10:45 AM")
        self.assertIsNotNone(updated["updated_at"])

    # Scenario 8: Reschedule an appointment
    def test_08_reschedule_appointment(self):
        d_orig = (date.today() + timedelta(days=3)).isoformat()
        d_new = (date.today() + timedelta(days=7)).isoformat()
        a_id = add_appointment(self.senior_a_id, "Dr. Shah", "Pathcare", d_orig, "09:00 AM", user=self.caregiver_user)

        ok = reschedule_appointment(
            appointment_id=a_id,
            elderly_user_id=self.senior_a_id,
            new_date=d_new,
            new_time="11:30 AM",
            reschedule_reason="Patient had family function on original date",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        rescheduled = get_appointment_by_id(a_id)
        self.assertEqual(rescheduled["appointment_date"], d_new)
        self.assertEqual(rescheduled["appointment_time"], "11:30 AM")
        self.assertEqual(rescheduled["status"], "upcoming")

    # Scenario 9: Cancel an appointment
    def test_09_cancel_appointment(self):
        d_target = (date.today() + timedelta(days=5)).isoformat()
        a_id = add_appointment(self.senior_a_id, "Dr. Patil", "City Hospital", d_target, "10:00 AM", user=self.caregiver_user)

        ok = cancel_appointment(
            appointment_id=a_id,
            elderly_user_id=self.senior_a_id,
            cancellation_reason="Doctor on emergency leave",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        cancelled = get_appointment_by_id(a_id)
        self.assertEqual(cancelled["status"], "cancelled")

    # Scenario 10: Mark an appointment completed
    def test_10_mark_appointment_completed(self):
        d_target = (date.today() + timedelta(days=2)).isoformat()
        a_id = add_appointment(self.senior_a_id, "Dr. Deshmukh", "Care Clinic", d_target, "10:00 AM", user=self.caregiver_user)

        ok = complete_appointment(
            appointment_id=a_id,
            elderly_user_id=self.senior_a_id,
            post_visit_notes="Blood pressure 122/80 mmHg. Continue current dosage of Amlodipine 5 mg.",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        completed = get_appointment_by_id(a_id)
        self.assertEqual(completed["status"], "completed")
        self.assertIn("Amlodipine", completed["post_visit_notes"])

    # Scenario 11: Record a missed appointment
    def test_11_record_missed_appointment(self):
        d_target = (date.today() + timedelta(days=1)).isoformat()
        a_id = add_appointment(self.senior_a_id, "Dr. Rao", "Apollo", d_target, "09:00 AM", user=self.caregiver_user)

        ok = mark_appointment_missed(
            appointment_id=a_id,
            elderly_user_id=self.senior_a_id,
            notes="Senior was unwell and unable to travel",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        missed = get_appointment_by_id(a_id)
        self.assertEqual(missed["status"], "missed")

    # Scenario 12: Preserve historical appointment records
    def test_12_preserve_historical_appointment_records(self):
        d_past = (date.today() - timedelta(days=10)).isoformat()
        a1 = add_appointment(self.senior_a_id, "Dr. Historical 1", "Clinic", d_past, "10:00 AM", user=self.caregiver_user, allow_past=True)
        complete_appointment(a1, self.senior_a_id, post_visit_notes="Followup after 6 months", user=self.caregiver_user)

        d_past2 = (date.today() - timedelta(days=5)).isoformat()
        a2 = add_appointment(self.senior_a_id, "Dr. Historical 2", "Clinic", d_past2, "11:00 AM", user=self.caregiver_user, allow_past=True)
        cancel_appointment(a2, self.senior_a_id, cancellation_reason="Cancelled by patient", user=self.caregiver_user)

        history = get_appointment_history(self.senior_a_id, user=self.caregiver_user)
        self.assertGreaterEqual(len(history), 2)
        h_ids = [h["id"] for h in history]
        self.assertIn(a1, h_ids)
        self.assertIn(a2, h_ids)

    # Scenario 13: Generate one-day reminder
    def test_13_generate_one_day_reminder(self):
        appt_date = "2026-11-20"
        appt_time = "10:30 AM"
        a_id = add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Cardio Lead",
            hospital="Apollo Khar",
            appointment_date=appt_date,
            appointment_time=appt_time,
            user=self.caregiver_user,
            allow_past=True,
        )
        # Mock now: 2026-11-19 14:00 (within 24 hours of appointment)
        now_dt = datetime.strptime("2026-11-19 14:00", "%Y-%m-%d %H:%M")
        counts = sync_appointment_reminders(self.senior_a_id, now_dt=now_dt)
        self.assertGreater(counts["one_day_reminders"], 0)

        # In-app notification delivered
        notifs = get_user_notifications(self.caregiver_user, alert_type="system")
        self.assertTrue(any("Appointment Tomorrow" in n["title"] for n in notifs))

    # Scenario 14: Generate one-hour reminder
    def test_14_generate_one_hour_reminder(self):
        appt_date = "2026-11-20"
        appt_time = "10:30 AM"
        a_id = add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Urgent Consult",
            hospital="Apollo Khar",
            appointment_date=appt_date,
            appointment_time=appt_time,
            user=self.caregiver_user,
            allow_past=True,
        )
        # Mock now: 2026-11-20 09:45 (within 60 minutes)
        now_dt = datetime.strptime("2026-11-20 09:45", "%Y-%m-%d %H:%M")
        counts = sync_appointment_reminders(self.senior_a_id, now_dt=now_dt)
        self.assertGreater(counts["one_hour_reminders"], 0)

        notifs = get_user_notifications(self.caregiver_user, alert_type="system")
        self.assertTrue(any("in 1 Hour" in n["title"] for n in notifs))

    # Scenario 15: Prevent duplicate reminders
    def test_15_prevent_duplicate_reminders(self):
        appt_date = "2026-11-20"
        appt_time = "10:30 AM"
        add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Anti Duplicate",
            hospital="City Hospital",
            appointment_date=appt_date,
            appointment_time=appt_time,
            user=self.caregiver_user,
            allow_past=True,
        )
        now_dt = datetime.strptime("2026-11-19 14:00", "%Y-%m-%d %H:%M")

        # Run sync 5 times
        for _ in range(5):
            sync_appointment_reminders(self.senior_a_id, now_dt=now_dt)

        with get_connection() as conn:
            cnt = conn.execute(
                """SELECT COUNT(*) as c FROM appointment_reminders
                   WHERE elderly_user_id = ? AND reminder_type = '1_day_before' AND user_id = ?""",
                (self.senior_a_id, self.caregiver_id),
            ).fetchone()["c"]
        self.assertEqual(cnt, 1, "Expected exactly 1 reminder record despite 5 sync calls")

    # Scenario 16: Prevent reminders for cancelled appointments
    def test_16_prevent_reminders_for_cancelled_appointments(self):
        appt_date = "2026-11-20"
        appt_time = "10:30 AM"
        a_id = add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Cancelled Visit",
            hospital="City Hospital",
            appointment_date=appt_date,
            appointment_time=appt_time,
            user=self.caregiver_user,
            allow_past=True,
        )
        cancel_appointment(a_id, self.senior_a_id, user=self.caregiver_user)

        now_dt = datetime.strptime("2026-11-19 14:00", "%Y-%m-%d %H:%M")
        counts = sync_appointment_reminders(self.senior_a_id, now_dt=now_dt)
        self.assertEqual(counts["one_day_reminders"], 0)

    # Scenario 17: Verify caregiver permissions
    def test_17_verify_caregiver_permissions(self):
        d_future = (date.today() + timedelta(days=5)).isoformat()
        # Authorized caregiver can add
        a_id = add_appointment(self.senior_a_id, "Dr. Nurse Assigned", "Hosp", d_future, "10:00 AM", user=self.caregiver_user)
        self.assertIsNotNone(a_id)

        # Authorized caregiver can edit
        ok = update_appointment(a_id, self.senior_a_id, "Dr. Nurse Assigned", "New Hosp", d_future, "11:00 AM", user=self.caregiver_user)
        self.assertTrue(ok)

    # Scenario 18: Verify family-member permissions
    def test_18_verify_family_member_permissions(self):
        d_future = (date.today() + timedelta(days=5)).isoformat()
        # Family member can VIEW appointments
        appts = get_appointments(self.senior_a_id, user=self.family_user)
        self.assertIsInstance(appts, list)

        # Family member with viewer access CANNOT add appointment
        with self.assertRaises(PermissionError):
            add_appointment(self.senior_a_id, "Dr. Blocked", "Hosp", d_future, "10:00 AM", user=self.family_user)

        # Family member CANNOT cancel appointment
        a_id = add_appointment(self.senior_a_id, "Dr. Protected", "Hosp", d_future, "10:00 AM", user=self.caregiver_user)
        with self.assertRaises(PermissionError):
            cancel_appointment(a_id, self.senior_a_id, user=self.family_user)

    # Scenario 19: Prevent access to unrelated elderly profiles
    def test_19_prevent_access_to_unrelated_elderly_profiles(self):
        with self.assertRaises(PermissionError):
            get_appointments(self.senior_a_id, user=self.stranger_user)

        with self.assertRaises(PermissionError):
            add_appointment(self.senior_a_id, "Dr. Stranger", "Hosp", (date.today() + timedelta(days=2)).isoformat(), "10:00 AM", user=self.stranger_user)

    # Scenario 20: Verify appointment persistence after restart
    def test_20_verify_appointment_persistence_after_restart(self):
        d_target = (date.today() + timedelta(days=4)).isoformat()
        a_id = add_appointment(
            elderly_user_id=self.senior_a_id,
            doctor_name="Dr. Persistent",
            specialization="Neurology",
            hospital="Global Hospital",
            appointment_date=d_target,
            appointment_time="02:30 PM",
            user=self.caregiver_user,
        )

        with get_connection() as conn:
            row = conn.execute("SELECT * FROM appointments WHERE id = ?", (a_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["doctor_name"], "Dr. Persistent")
            self.assertEqual(row["specialization"], "Neurology")

    # Scenario 21: Verify previous medication and care-circle functionality still works
    def test_21_verify_previous_functionality_regression(self):
        # 1. Medication
        today_str = date.today().isoformat()
        m_id = add_medication(self.senior_a_id, "Vitamin B12", "500 mcg", "08:00", start_date=today_str, user=self.caregiver_user)
        self.assertIsNotNone(m_id)
        sched = get_today_schedule(self.senior_a_id, user=self.caregiver_user)
        self.assertTrue(any(s["medication_id"] == m_id for s in sched))

        # 2. Care Circle
        members = get_care_circle_members(self.senior_a_id, user=self.caregiver_user)
        self.assertGreaterEqual(len(members), 2)


if __name__ == "__main__":
    unittest.main()
