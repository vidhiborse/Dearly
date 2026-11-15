import unittest
import sqlite3
from datetime import date, datetime, timedelta

from database import init_db, create_demo_users, get_connection
from services.auth_service import authenticate_user
from services.user_service import update_user_profile
from services.medication_service import (
    add_medication,
    get_medications,
    get_medication_by_id,
    update_medication,
    deactivate_medication,
    activate_medication,
    delete_medication,
    get_today_schedule,
    get_grouped_daily_schedule,
    record_dose_status,
    get_adherence_metrics,
    get_overdue_doses,
    validate_medication_input,
)


class TestPhase3MedicationManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()
        with get_connection() as conn:
            # Clean any previous test artifacts
            conn.execute("DELETE FROM users WHERE email LIKE '%@testmeds.demo'")
            
            # Create a dedicated elderly user and caregiver for test isolation
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Test Senior', 'elderly@testmeds.demo', 'hash123', 'elderly', '+91 99999 11111')"""
            )
            cls.elderly_id = conn.execute("SELECT id FROM users WHERE email = 'elderly@testmeds.demo'").fetchone()["id"]
            
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Test Nurse', 'caregiver@testmeds.demo', 'hash123', 'caregiver', '+91 99999 22222')"""
            )
            cls.caregiver_id = conn.execute("SELECT id FROM users WHERE email = 'caregiver@testmeds.demo'").fetchone()["id"]

            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Test Kin', 'family@testmeds.demo', 'hash123', 'family', '+91 99999 33333')"""
            )
            cls.family_id = conn.execute("SELECT id FROM users WHERE email = 'family@testmeds.demo'").fetchone()["id"]

            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Stranger Danger', 'unrelated@testmeds.demo', 'hash123', 'caregiver', '+91 99999 44444')"""
            )
            cls.unrelated_id = conn.execute("SELECT id FROM users WHERE email = 'unrelated@testmeds.demo'").fetchone()["id"]

            # Authorize caregiver in care_circle
            conn.execute(
                """INSERT INTO care_circle (elderly_user_id, member_user_id, relationship, permission_level)
                   VALUES (?, ?, 'Nurse', 'editor')""",
                (cls.elderly_id, cls.caregiver_id),
            )

            # Authorize family as viewer in care_circle
            conn.execute(
                """INSERT INTO care_circle (elderly_user_id, member_user_id, relationship, permission_level)
                   VALUES (?, ?, 'Child', 'viewer')""",
                (cls.elderly_id, cls.family_id),
            )

        cls.caregiver_user = {"id": cls.caregiver_id, "role": "caregiver", "name": "Test Nurse"}
        cls.elderly_user = {"id": cls.elderly_id, "role": "elderly", "name": "Test Senior"}
        cls.family_user = {"id": cls.family_id, "role": "family", "name": "Test Kin"}
        cls.unrelated_user = {"id": cls.unrelated_id, "role": "caregiver", "name": "Stranger"}

    @classmethod
    def tearDownClass(cls):
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE email LIKE '%@testmeds.demo'")

    # Scenario 1: Add a medication successfully
    def test_01_add_medication_successfully(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Lisinopril",
            dosage="10 mg",
            medication_type="Tablet",
            schedule_time="08:00",
            frequency="Daily",
            start_date=date.today().isoformat(),
            instructions="Take in the morning with water",
            prescribing_doctor="Dr. Sunita Kulkarni",
            notes="Blood pressure management",
            stock_quantity=30,
            user=self.caregiver_user,
        )
        self.assertIsNotNone(med_id)
        self.assertGreater(med_id, 0)
        
        med = get_medication_by_id(med_id, self.elderly_id)
        self.assertIsNotNone(med)
        self.assertEqual(med["medicine_name"], "Lisinopril")
        self.assertEqual(med["dosage"], "10 mg")
        self.assertEqual(med["medication_type"], "Tablet")
        self.assertEqual(med["active"], 1)

    # Scenario 2: Reject missing required fields
    def test_02_reject_missing_required_fields(self):
        # Empty medication name
        with self.assertRaises(ValueError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="",
                dosage="500 mg",
                schedule_time="08:00",
                user=self.caregiver_user,
            )

        # Empty dosage
        with self.assertRaises(ValueError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Aspirin",
                dosage="",
                schedule_time="08:00",
                user=self.caregiver_user,
            )

        # Invalid time format
        with self.assertRaises(ValueError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Aspirin",
                dosage="75 mg",
                schedule_time="8am",
                user=self.caregiver_user,
            )

    # Scenario 3: Reject invalid dates
    def test_03_reject_invalid_dates(self):
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()

        # End date earlier than start date
        with self.assertRaises(ValueError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Amoxicillin",
                dosage="250 mg",
                schedule_time="12:00",
                start_date=tomorrow,
                end_date=yesterday,
                user=self.caregiver_user,
            )

        # Malformed date string
        with self.assertRaises(ValueError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Amoxicillin",
                dosage="250 mg",
                schedule_time="12:00",
                start_date="not-a-date",
                user=self.caregiver_user,
            )

    # Scenario 4: Display active medications
    def test_04_display_active_medications(self):
        active_meds = get_medications(self.elderly_id, status_filter="active", user=self.caregiver_user)
        self.assertTrue(len(active_meds) >= 1)
        for m in active_meds:
            self.assertEqual(m["active"], 1)

    # Scenario 5: Display inactive medications
    def test_05_display_inactive_medications(self):
        # Add a med and deactivate it
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Temporary Antibiotic",
            dosage="500 mg",
            schedule_time="14:00",
            user=self.caregiver_user,
        )
        deactivate_medication(med_id, self.elderly_id, user=self.caregiver_user)

        inactive_meds = get_medications(self.elderly_id, status_filter="inactive", user=self.caregiver_user)
        self.assertTrue(any(m["id"] == med_id for m in inactive_meds))
        for m in inactive_meds:
            self.assertEqual(m["active"], 0)

    # Scenario 6: Edit an existing medication
    def test_06_edit_existing_medication(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Atorvastatin",
            dosage="10 mg",
            schedule_time="20:00",
            user=self.caregiver_user,
        )
        
        ok = update_medication(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            medicine_name="Atorvastatin",
            dosage="20 mg",  # Updated dosage
            schedule_time="20:30",  # Updated time
            medication_type="Tablet",
            frequency="Daily",
            start_date=date.today().isoformat(),
            end_date=None,
            meal_timing="After Dinner",
            instructions="Take with water at bedtime",
            purpose="Lipid Control",
            prescribing_doctor="Dr. Sunita Kulkarni",
            notes="Dose titrated from 10mg",
            stock_quantity=45,
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        updated = get_medication_by_id(med_id, self.elderly_id)
        self.assertEqual(updated["dosage"], "20 mg")
        self.assertEqual(updated["schedule_time"], "20:30")
        self.assertEqual(updated["stock_quantity"], 45)

    # Scenario 7: Deactivate a medication and preserve history
    def test_07_deactivate_medication(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Vitamin C",
            dosage="500 mg",
            schedule_time="11:00",
            user=self.caregiver_user,
        )
        # Log a dose
        today_str = date.today().isoformat()
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=today_str,
            scheduled_time="11:00",
            status="taken",
            recorded_by=self.elderly_id,
            user=self.elderly_user,
        )

        ok = deactivate_medication(med_id, self.elderly_id, user=self.caregiver_user)
        self.assertTrue(ok)

        med = get_medication_by_id(med_id, self.elderly_id)
        self.assertEqual(med["active"], 0)

        # Historical logs must remain in database
        with get_connection() as conn:
            log = conn.execute(
                "SELECT * FROM medication_logs WHERE medication_id = ?",
                (med_id,),
            ).fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log["status"], "taken")

    # Scenario 8: Prevent unauthorized medication changes
    def test_08_prevent_unauthorized_medication_changes(self):
        # Family member lacks write permission (viewer only)
        with self.assertRaises(PermissionError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Unauthorized Med",
                dosage="10 mg",
                schedule_time="09:00",
                user=self.family_user,
            )

        # Unrelated user has zero care circle link
        with self.assertRaises(PermissionError):
            add_medication(
                elderly_user_id=self.elderly_id,
                medicine_name="Intruder Med",
                dosage="10 mg",
                schedule_time="09:00",
                user=self.unrelated_user,
            )

    # Scenario 9: Display the correct daily schedule
    def test_09_display_correct_daily_schedule(self):
        grouped = get_grouped_daily_schedule(self.elderly_id, user=self.caregiver_user)
        self.assertIn("Morning", grouped)
        self.assertIn("Afternoon", grouped)
        self.assertIn("Evening", grouped)
        self.assertIn("Night", grouped)

        # Morning items must be scheduled between 05:00 and 11:59
        for item in grouped["Morning"]:
            t = item["schedule_time"]
            self.assertTrue("05:00" <= t <= "11:59")

    # Scenario 10: Mark a dose as taken
    def test_10_mark_dose_as_taken(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Thyroxine",
            dosage="50 mcg",
            schedule_time="06:30",
            user=self.caregiver_user,
        )
        today_str = date.today().isoformat()
        ok = record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=today_str,
            scheduled_time="06:30",
            status="taken",
            recorded_by=self.elderly_id,
            notes="Taken empty stomach",
            user=self.elderly_user,
        )
        self.assertTrue(ok)

        with get_connection() as conn:
            log = conn.execute(
                "SELECT status, notes, actual_action_time FROM medication_logs WHERE medication_id = ? AND scheduled_date = ?",
                (med_id, today_str),
            ).fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log["status"], "taken")
            self.assertEqual(log["notes"], "Taken empty stomach")
            self.assertIsNotNone(log["actual_action_time"])

    # Scenario 11: Mark a dose as skipped
    def test_11_mark_dose_as_skipped(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Antacid",
            dosage="10 ml",
            schedule_time="15:00",
            medication_type="Syrup",
            user=self.caregiver_user,
        )
        today_str = date.today().isoformat()
        ok = record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=today_str,
            scheduled_time="15:00",
            status="skipped",
            recorded_by=self.caregiver_id,
            notes="Patient had no acidity symptoms",
            user=self.caregiver_user,
        )
        self.assertTrue(ok)

        with get_connection() as conn:
            log = conn.execute(
                "SELECT status FROM medication_logs WHERE medication_id = ? AND scheduled_date = ?",
                (med_id, today_str),
            ).fetchone()
            self.assertEqual(log["status"], "skipped")

    # Scenario 12: Prevent duplicate dose records
    def test_12_prevent_duplicate_dose_records(self):
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Glimepiride",
            dosage="1 mg",
            schedule_time="08:15",
            user=self.caregiver_user,
        )
        today_str = date.today().isoformat()

        # First record: pending
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=today_str,
            scheduled_time="08:15",
            status="pending",
            recorded_by=self.elderly_id,
            user=self.elderly_user,
        )

        # Second record on same scheduled dose: update to taken
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=today_str,
            scheduled_time="08:15",
            status="taken",
            recorded_by=self.elderly_id,
            user=self.elderly_user,
        )

        # Count records in SQLite
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM medication_logs WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ?",
                (med_id, today_str, "08:15"),
            ).fetchone()["cnt"]
            # Must strictly be 1 row, not 2
            self.assertEqual(count, 1)

            final_status = conn.execute(
                "SELECT status FROM medication_logs WHERE medication_id = ? AND scheduled_date = ?",
                (med_id, today_str),
            ).fetchone()["status"]
            self.assertEqual(final_status, "taken")

    # Scenario 13: Calculate adherence correctly: (Taken / Total Due) * 100
    def test_13_calculate_adherence_correctly(self):
        # Isolated test on demo user 1 (Asha Patil)
        metrics = get_adherence_metrics(1, days=7)
        self.assertTrue(metrics["has_data"])
        self.assertGreater(metrics["total_due"], 0)
        
        expected_pct = round((metrics["total_taken"] / metrics["total_due"]) * 100, 1)
        self.assertEqual(metrics["adherence_percentage"], expected_pct)

    # Scenario 14: Identify overdue doses correctly (scheduled time < current local time)
    def test_14_identify_overdue_doses_correctly(self):
        # Add a medication scheduled in the past today (00:01)
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Midnight Check",
            dosage="5 mg",
            schedule_time="00:01",
            user=self.caregiver_user,
        )
        overdue_list = get_overdue_doses(self.elderly_id, user=self.caregiver_user)
        self.assertTrue(any(d["medication_id"] == med_id for d in overdue_list))

        # Once marked taken, it must no longer be overdue
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.elderly_id,
            scheduled_date=date.today().isoformat(),
            scheduled_time="00:01",
            status="taken",
            recorded_by=self.elderly_id,
            user=self.elderly_user,
        )
        overdue_after = get_overdue_doses(self.elderly_id, user=self.caregiver_user)
        self.assertFalse(any(d["medication_id"] == med_id for d in overdue_after))

    # Scenario 15: Exclude future doses from overdue calculations
    def test_15_exclude_future_doses_from_overdue_calculations(self):
        # Add a medication scheduled in late night (23:59)
        med_id = add_medication(
            elderly_user_id=self.elderly_id,
            medicine_name="Future Sleep Aid",
            dosage="5 mg",
            schedule_time="23:59",
            user=self.caregiver_user,
        )
        now_time = datetime.now().strftime("%H:%M")
        if now_time < "23:59":
            overdue_list = get_overdue_doses(self.elderly_id, user=self.caregiver_user)
            self.assertFalse(any(d["medication_id"] == med_id for d in overdue_list))

    # Scenario 16: Verify medication records persist after application restart
    def test_16_verify_medication_records_persist_after_restart(self):
        # Close connection and re-open to simulate application process restart
        conn = get_connection()
        conn.close()

        # Re-initialize database schema
        init_db()
        meds = get_medications(self.elderly_id, user=self.caregiver_user)
        self.assertTrue(len(meds) >= 1)

    # Scenario 17: Verify existing login and profile functionality still works
    def test_17_verify_existing_auth_and_profile_regression(self):
        # Test demo authentication
        auth_elderly = authenticate_user("elderly@dearly.demo", "demo123")
        self.assertIsNotNone(auth_elderly)
        self.assertEqual(auth_elderly["role"], "elderly")

        auth_caregiver = authenticate_user("caregiver@dearly.demo", "demo123")
        self.assertIsNotNone(auth_caregiver)
        self.assertEqual(auth_caregiver["role"], "caregiver")

        # Test profile update
        ok, msg = update_user_profile(
            user_id=auth_caregiver["id"],
            name="Rahul Patil",
            phone="+91 98200 12345",
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
