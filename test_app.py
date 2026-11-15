import unittest
from datetime import date
import database
from services.auth_service import authenticate, get_accessible_elderly_wards
from services.medication_service import (
    get_medications,
    get_today_schedule,
    record_dose_status,
    add_medication,
    get_adherence_metrics,
)
from services.appointment_service import (
    get_appointments,
    add_appointment,
    update_appointment_status,
    get_next_upcoming_appointment,
)
from services.health_service import get_health_readings, add_health_reading, get_latest_vitals
from services.care_circle_service import (
    get_care_circle_members,
    get_elderly_profile,
    check_permission,
)
from services.emergency_service import (
    trigger_sos_alert,
    get_active_emergency_alerts,
    acknowledge_alert,
)
from services.summary_service import generate_daily_care_summary

class TestDearlyPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.create_demo_users()

    def test_authentication_demo_users(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        self.assertIsNotNone(elderly)
        self.assertEqual(elderly["role"], "elderly")
        self.assertEqual(elderly["name"], "Asha Patil")

        caregiver = authenticate("caregiver@dearly.demo", "demo123")
        self.assertIsNotNone(caregiver)
        self.assertEqual(caregiver["role"], "caregiver")

        family = authenticate("family@dearly.demo", "demo123")
        self.assertIsNotNone(family)
        self.assertEqual(family["role"], "family")

        invalid = authenticate("elderly@dearly.demo", "wrongpassword")
        self.assertIsNone(invalid)

    def test_accessible_wards(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        wards = get_accessible_elderly_wards(elderly)
        self.assertEqual(len(wards), 1)
        self.assertEqual(wards[0]["id"], elderly["id"])

        caregiver = authenticate("caregiver@dearly.demo", "demo123")
        cg_wards = get_accessible_elderly_wards(caregiver)
        self.assertGreaterEqual(len(cg_wards), 1)
        self.assertEqual(cg_wards[0]["id"], elderly["id"])

    def test_medication_schedule_and_dose_logging(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        e_id = elderly["id"]
        schedule = get_today_schedule(e_id)
        self.assertGreaterEqual(len(schedule), 1)

        first_med = schedule[0]
        med_id = first_med["medication_id"]
        today_str = date.today().isoformat()

        # Mark taken
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=e_id,
            scheduled_date=today_str,
            scheduled_time=first_med["schedule_time"],
            status="taken",
            recorded_by=e_id,
            notes="Automated test dose confirmation",
        )

        updated_sched = get_today_schedule(e_id)
        matching = next(s for s in updated_sched if s["medication_id"] == med_id)
        self.assertEqual(matching["status"], "taken")

        metrics = get_adherence_metrics(e_id, days=7)
        self.assertGreater(metrics["adherence_percentage"], 0)

    def test_appointment_management(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        e_id = elderly["id"]

        appt_id = add_appointment(
            elderly_user_id=e_id,
            doctor_name="Dr. Test Specialist",
            hospital="Test Clinic",
            appointment_date="2026-12-01",
            appointment_time="11:00 AM",
            purpose="Routine Checkup",
            notes="Bring reports",
            created_by=e_id,
        )
        self.assertIsNotNone(appt_id)

        update_appointment_status(appt_id, e_id, "completed", updated_by=e_id)
        appts = get_appointments(e_id)
        test_appt = next(a for a in appts if a["id"] == appt_id)
        self.assertEqual(test_appt["status"], "completed")

    def test_health_vitals(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        e_id = elderly["id"]

        reading_id = add_health_reading(
            elderly_user_id=e_id,
            reading_type="Blood Pressure",
            reading_value="120/80 mmHg",
            recorded_on=date.today().isoformat(),
            notes="Ideal baseline",
            recorded_by=e_id,
        )
        self.assertIsNotNone(reading_id)

        vitals = get_latest_vitals(e_id)
        self.assertIn("Blood Pressure", vitals)
        self.assertIsNotNone(vitals["Blood Pressure"])

    def test_care_circle_and_permissions(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        caregiver = authenticate("caregiver@dearly.demo", "demo123")
        family = authenticate("family@dearly.demo", "demo123")

        self.assertTrue(check_permission(elderly["id"], elderly, "editor"))
        self.assertTrue(check_permission(elderly["id"], caregiver, "editor"))
        self.assertTrue(check_permission(elderly["id"], family, "viewer"))

    def test_emergency_alert_flow(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        caregiver = authenticate("caregiver@dearly.demo", "demo123")
        e_id = elderly["id"]

        alert_id = trigger_sos_alert(
            elderly_user_id=e_id,
            triggered_by_user_id=e_id,
            message="Test SOS triggered",
        )
        self.assertIsNotNone(alert_id)

        active = get_active_emergency_alerts(e_id)
        matching = [a for a in active if a["id"] == alert_id]
        self.assertEqual(len(matching), 1)

        acknowledge_alert(alert_id, e_id, caregiver["id"])
        active_after = get_active_emergency_alerts(e_id)
        matching_after = [a for a in active_after if a["id"] == alert_id]
        self.assertEqual(len(matching_after), 0)

    def test_ai_daily_summary(self):
        elderly = authenticate("elderly@dearly.demo", "demo123")
        summary = generate_daily_care_summary(elderly["name"], elderly["id"])
        self.assertIn("Daily Care Briefing", summary)
        self.assertIn("Safety & Clinical Disclaimer", summary)

if __name__ == "__main__":
    unittest.main()
