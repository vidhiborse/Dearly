import unittest
import sqlite3
from database import init_db, create_demo_users, authenticate_with_passcode, check_login_rate_limit, record_failed_login, clear_failed_login
from services.auth_service import authenticate_passcode
from services.user_service import update_user_passcode, get_user_profile
from services.email_service import (
    send_upcoming_dose_email,
    send_missed_dose_email,
    send_appointment_email,
    get_outbound_emails,
    get_email_statistics,
    format_accessible_email_html,
)

class TestEmailAndPasscodeFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()

    def test_01_authenticate_with_valid_demo_passcode(self):
        user = authenticate_passcode("1234")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "elderly@dearly.demo")
        self.assertEqual(user["role"], "elderly")

    def test_02_authenticate_caregiver_passcode(self):
        user = authenticate_passcode("2345")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "caregiver@dearly.demo")
        self.assertEqual(user["role"], "caregiver")

    def test_03_reject_invalid_passcode(self):
        user = authenticate_passcode("9999")
        self.assertIsNone(user)

    def test_04_reject_short_or_empty_passcode(self):
        self.assertIsNone(authenticate_passcode(""))
        self.assertIsNone(authenticate_passcode("12"))

    def test_05_update_passcode_valid(self):
        user = authenticate_passcode("3456")
        self.assertIsNotNone(user)
        uid = user["id"]
        ok, msg = update_user_passcode(uid, "7890")
        self.assertTrue(ok)
        
        # Verify new PIN works
        updated_user = authenticate_passcode("7890")
        self.assertIsNotNone(updated_user)
        self.assertEqual(updated_user["id"], uid)

        # Restore original PIN
        update_user_passcode(uid, "3456")

    def test_06_reject_invalid_new_passcode(self):
        ok, msg = update_user_passcode(1, "abc")
        self.assertFalse(ok)
        ok, msg = update_user_passcode(1, "12")
        self.assertFalse(ok)
        ok, msg = update_user_passcode(1, "1234567")
        self.assertFalse(ok)

    def test_07_send_upcoming_dose_email(self):
        email_id = send_upcoming_dose_email(
            elderly_user_id=1,
            recipient_email="elderly@dearly.demo",
            recipient_name="Asha Patil",
            senior_name="Asha Patil",
            medicine_name="Metformin",
            dosage="500mg",
            scheduled_time="08:00 AM",
            meal_timing="After Breakfast",
            instructions="With water",
        )
        self.assertIsInstance(email_id, int)
        self.assertGreater(email_id, 0)

        emails = get_outbound_emails(elderly_user_id=1, limit=5)
        self.assertTrue(any("Upcoming Dose Reminder" in e["subject"] for e in emails))

    def test_08_send_missed_dose_email(self):
        email_id = send_missed_dose_email(
            elderly_user_id=1,
            recipient_email="caregiver@dearly.demo",
            recipient_name="Rahul Patil",
            senior_name="Asha Patil",
            medicine_name="Amlodipine",
            dosage="5mg",
            scheduled_time="09:00 AM",
        )
        self.assertIsInstance(email_id, int)
        self.assertGreater(email_id, 0)

        emails = get_outbound_emails(elderly_user_id=1, limit=5)
        self.assertTrue(any("OVERDUE MEDICATION NOTICE" in e["subject"] for e in emails))

    def test_09_send_appointment_email(self):
        email_id = send_appointment_email(
            elderly_user_id=1,
            recipient_email="family@dearly.demo",
            recipient_name="Neha Patil",
            senior_name="Asha Patil",
            doctor_name="Rajesh Sharma",
            hospital="Apollo Health",
            appointment_date="2026-11-20",
            appointment_time="10:00 AM",
            reminder_type="1_day_before",
            notes="Bring blood sugar log",
        )
        self.assertIsInstance(email_id, int)
        self.assertGreater(email_id, 0)

        emails = get_outbound_emails(elderly_user_id=1, limit=5)
        self.assertTrue(any("Doctor Visit Reminder" in e["subject"] for e in emails))

    def test_10_email_statistics_aggregation(self):
        stats = get_email_statistics(elderly_user_id=1)
        self.assertIn("total_sent", stats)
        self.assertIn("recipients_count", stats)
        self.assertGreaterEqual(stats["total_sent"], 3)
        self.assertGreaterEqual(stats["recipients_count"], 1)

    def test_11_login_rate_limiting(self):
        test_email = "brute_force_test@example.com"
        clear_failed_login(test_email)
        
        allowed, msg = check_login_rate_limit(test_email)
        self.assertTrue(allowed)

        # Record 8 failed logins
        for _ in range(8):
            record_failed_login(test_email)

        allowed, msg = check_login_rate_limit(test_email)
        self.assertFalse(allowed)
        self.assertIn("locked", msg.lower())

        clear_failed_login(test_email)
        allowed, _ = check_login_rate_limit(test_email)
        self.assertTrue(allowed)

if __name__ == "__main__":
    unittest.main()
