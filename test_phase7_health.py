import csv
import io
import unittest
from datetime import date, datetime, timedelta
import database
from services.activity_service import get_recent_activities
from services.appointment_service import (
    add_appointment,
    complete_appointment,
    get_appointments,
    reschedule_appointment,
    sync_appointment_reminders,
)
from services.auth_service import authenticate
from services.care_circle_service import (
    add_care_note,
    get_care_circle_members,
    get_care_notes,
    send_care_invitation,
)
from services.health_service import (
    SUPPORTED_MEASUREMENTS,
    add_health_measurement,
    add_health_observation,
    add_health_reading,
    correct_health_reading,
    create_health_chart,
    evaluate_reference_range,
    export_health_records_csv,
    get_health_observations,
    get_health_readings,
    get_health_record_audit,
    get_health_summary,
    get_latest_vitals,
    validate_health_measurement,
)
from services.medication_service import (
    add_medication,
    get_today_schedule,
    record_dose_status,
)
from services.reminder_service import sync_reminders_and_escalations


class TestPhase7HealthMonitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.create_demo_users()

    def setUp(self):
        self.elderly = authenticate("elderly@dearly.demo", "demo123")
        self.caregiver = authenticate("caregiver@dearly.demo", "demo123")
        self.family = authenticate("family@dearly.demo", "demo123")
        self.e_id = self.elderly["id"]
        self.c_id = self.caregiver["id"]
        self.f_id = self.family["id"]

    def test_01_record_blood_pressure(self):
        """Scenario 1: Record a valid blood pressure reading."""
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Blood Pressure",
            reading_value="122/82 mmHg",
            recorded_on=date.today().isoformat(),
            recorded_by=self.c_id,
            systolic=122,
            diastolic=82,
            unit="mmHg",
            context="Resting morning seated",
            notes="Standard home monitor",
            user=self.caregiver,
        )
        self.assertIsNotNone(rid)
        self.assertGreater(rid, 0)

        readings = get_health_readings(self.e_id, reading_type="Blood Pressure", limit=50, user=self.caregiver)
        match = next((r for r in readings if r["id"] == rid), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["systolic"], 122)
        self.assertEqual(match["diastolic"], 82)
        self.assertEqual(match["unit"], "mmHg")

    def test_02_record_blood_sugar(self):
        """Scenario 2: Record a valid blood sugar reading with context and unit."""
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Blood Sugar",
            reading_value="105 mg/dL",
            recorded_on=date.today().isoformat(),
            recorded_by=self.e_id,
            numeric_value=105.0,
            unit="mg/dL",
            context="fasting",
            notes="Morning before breakfast",
            user=self.elderly,
        )
        self.assertIsNotNone(rid)

        readings = get_health_readings(self.e_id, reading_type="Blood Sugar", limit=5, user=self.elderly)
        match = next((r for r in readings if r["id"] == rid), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["numeric_value"], 105.0)
        self.assertEqual(match["unit"], "mg/dL")
        self.assertEqual(match["context"], "fasting")

    def test_03_record_weight(self):
        """Scenario 3: Record a weight measurement."""
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Weight",
            reading_value="64.8 kg",
            recorded_on=date.today().isoformat(),
            recorded_by=self.c_id,
            numeric_value=64.8,
            unit="kg",
            context="Morning pre-breakfast",
            notes="Weekly weigh-in",
            user=self.caregiver,
        )
        self.assertIsNotNone(rid)

        readings = get_health_readings(self.e_id, reading_type="Weight", limit=5, user=self.caregiver)
        match = next((r for r in readings if r["id"] == rid), None)
        self.assertIsNotNone(match)
        self.assertAlmostEqual(match["numeric_value"], 64.8, places=1)
        self.assertEqual(match["unit"], "kg")

    def test_04_record_heart_rate_and_other_measurements(self):
        """Scenario 4: Record heart rate, SpO2, and body temperature."""
        hr_id = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Heart Rate",
            reading_value="76 bpm",
            recorded_on=date.today().isoformat(),
            numeric_value=76.0,
            unit="bpm",
            notes="Resting pulse",
            user=self.caregiver,
        )
        self.assertIsNotNone(hr_id)

        spo2_id = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Oxygen Saturation (SpO2)",
            reading_value="99 %",
            recorded_on=date.today().isoformat(),
            numeric_value=99.0,
            unit="%",
            notes="Pulse oximeter on index finger",
            user=self.caregiver,
        )
        self.assertIsNotNone(spo2_id)

        temp_id = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Body Temperature",
            reading_value="36.8 °C",
            recorded_on=date.today().isoformat(),
            numeric_value=36.8,
            unit="°C",
            notes="Oral digital thermometer",
            user=self.caregiver,
        )
        self.assertIsNotNone(temp_id)

    def test_05_reject_invalid_measurement_formats(self):
        """Scenario 5: Reject invalid formats (negative, non-numeric, diastolic >= systolic)."""
        # Non-numeric blood sugar
        with self.assertRaises(ValueError):
            validate_health_measurement("Blood Sugar", reading_value="invalid_abc", unit="mg/dL")

        # Negative heart rate
        with self.assertRaises(ValueError):
            validate_health_measurement("Heart Rate", reading_value="-50", unit="bpm")

        # Diastolic greater than systolic
        with self.assertRaises(ValueError):
            validate_health_measurement("Blood Pressure", reading_value="80/120 mmHg", systolic=80, diastolic=120)

        # SpO2 greater than 100%
        with self.assertRaises(ValueError):
            validate_health_measurement("Oxygen Saturation (SpO2)", reading_value="105", numeric_value=105.0)

    def test_06_validate_units(self):
        """Scenario 6: Validate units and reject invalid units for measurement types."""
        # Valid units
        res_kg = validate_health_measurement("Weight", reading_value="65", numeric_value=65.0, unit="kg")
        self.assertEqual(res_kg["unit"], "kg")

        res_lb = validate_health_measurement("Weight", reading_value="143", numeric_value=143.0, unit="lb")
        self.assertEqual(res_lb["unit"], "lb")

        # Invalid unit for weight
        with self.assertRaises(ValueError):
            validate_health_measurement("Weight", reading_value="65", numeric_value=65.0, unit="liters")

        # Invalid unit for BP
        with self.assertRaises(ValueError):
            validate_health_measurement("Blood Pressure", reading_value="120/80", systolic=120, diastolic=80, unit="psi")

    def test_07_record_health_observations(self):
        """Scenario 7: Record qualitative health observations with categories."""
        obs_id = add_health_observation(
            elderly_user_id=self.e_id,
            observation_text="Asha reported feeling energetic and took a 20-minute morning garden walk.",
            recorded_by=self.c_id,
            category="mobility",
            recorded_on=date.today().isoformat(),
            user=self.caregiver,
        )
        self.assertIsNotNone(obs_id)

        obs_list = get_health_observations(self.e_id, category="mobility", user=self.caregiver)
        match = next((o for o in obs_list if o["id"] == obs_id), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["category"], "mobility")
        self.assertIn("morning garden walk", match["observation_text"])

    def test_08_display_latest_readings(self):
        """Scenario 8: Display latest vitals for each measurement type."""
        vitals = get_latest_vitals(self.e_id, user=self.caregiver)
        self.assertIn("Blood Pressure", vitals)
        self.assertIn("Blood Sugar", vitals)
        self.assertIn("Heart Rate", vitals)
        self.assertIn("Oxygen Saturation (SpO2)", vitals)
        self.assertIn("Weight", vitals)

        bp = vitals["Blood Pressure"]
        self.assertIsNotNone(bp)
        self.assertIn("mmHg", bp["reading_value"])
        self.assertIn("status_label", bp)

    def test_09_display_chronological_history(self):
        """Scenario 9: Display chronological history in descending date/time order."""
        history = get_health_readings(self.e_id, limit=30, user=self.caregiver)
        self.assertGreater(len(history), 1)

        dates = [r["recorded_on"] for r in history]
        # Dates should be in non-ascending order (newest first)
        for i in range(len(dates) - 1):
            self.assertGreaterEqual(dates[i], dates[i + 1])

    def test_10_filter_records_by_type_and_date(self):
        """Scenario 10: Filter records by measurement type and date range."""
        today_str = date.today().isoformat()
        bp_today = get_health_readings(
            self.e_id,
            reading_type="Blood Pressure",
            start_date=today_str,
            end_date=today_str,
            user=self.caregiver,
        )
        self.assertIsInstance(bp_today, list)
        for r in bp_today:
            self.assertEqual(r["reading_type"], "Blood Pressure")
            self.assertEqual(r["recorded_on"], today_str)

    def test_11_display_charts_using_actual_data(self):
        """Scenario 11: Generate Plotly charts using real database measurements."""
        readings = get_health_readings(self.e_id, limit=100, user=self.caregiver)

        # BP chart
        fig_bp = create_health_chart(readings, "Blood Pressure")
        self.assertIsNotNone(fig_bp)
        self.assertIn("Blood Pressure", fig_bp.layout.title.text)

        # Blood Sugar chart
        fig_sugar = create_health_chart(readings, "Blood Sugar")
        self.assertIsNotNone(fig_sugar)

        # Weight chart
        fig_weight = create_health_chart(readings, "Weight")
        # May be None if fewer than 1 point, otherwise valid figure
        if fig_weight:
            self.assertIn("Weight", fig_weight.layout.title.text)

    def test_12_handle_insufficient_chart_data(self):
        """Scenario 12: Handle insufficient chart data gracefully."""
        # Empty readings list returns None
        fig_empty = create_health_chart([], "Blood Pressure")
        self.assertIsNone(fig_empty)

        # Unmatched measurement type returns None
        fig_none = create_health_chart([{"reading_type": "Other", "reading_value": "10", "recorded_on": "2026-11-15"}], "Blood Pressure")
        self.assertIsNone(fig_none)

    def test_13_correct_health_record_with_audit_history(self):
        """Scenario 13: Correct a health record while preserving full audit history."""
        # Create a reading with a deliberate typo
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Blood Pressure",
            reading_value="190/80 mmHg",
            recorded_on=date.today().isoformat(),
            recorded_by=self.c_id,
            systolic=190,
            diastolic=80,
            unit="mmHg",
            notes="Initial entry with typo",
            user=self.caregiver,
        )

        # Correct the reading
        success = correct_health_reading(
            reading_id=rid,
            elderly_user_id=self.e_id,
            new_value="120/80 mmHg",
            reason="Corrected typo: systolic was 120, not 190",
            changed_by=self.c_id,
            systolic=120,
            diastolic=80,
            unit="mmHg",
            user=self.caregiver,
        )
        self.assertTrue(success)

        # Verify updated record
        updated = get_health_readings(self.e_id, limit=50, user=self.caregiver)
        match = next(r for r in updated if r["id"] == rid)
        self.assertEqual(match["systolic"], 120)
        self.assertEqual(match["is_corrected"], 1)
        self.assertIn("Corrected typo", match["correction_notes"])

        # Verify audit history
        audit_trail = get_health_record_audit(reading_id=rid, user=self.caregiver)
        self.assertGreaterEqual(len(audit_trail), 1)
        latest_audit = audit_trail[0]
        self.assertEqual(latest_audit["old_reading_value"], "190/80 mmHg")
        self.assertEqual(latest_audit["new_reading_value"], "120/80 mmHg")
        self.assertIn("Corrected typo", latest_audit["reason_for_change"])

    def test_14_export_records_to_csv(self):
        """Scenario 14: Export filtered health records to CSV with valid format."""
        csv_str = export_health_records_csv(self.e_id, user=self.caregiver)
        self.assertIsInstance(csv_str, str)
        self.assertIn("Record ID", csv_str)
        self.assertIn("Measurement Type", csv_str)
        self.assertIn("Reading Value", csv_str)

        # Parse CSV to verify RFC compliance
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        self.assertGreater(len(rows), 1)  # Header + at least 1 row
        self.assertEqual(rows[0][0], "Record ID")

    def test_15_verify_caregiver_permissions(self):
        """Scenario 15: Authorized editor caregiver can record and correct readings."""
        # Rahul Patil is linked with 'editor' permissions
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Heart Rate",
            reading_value="74 bpm",
            recorded_on=date.today().isoformat(),
            numeric_value=74.0,
            unit="bpm",
            user=self.caregiver,
        )
        self.assertIsNotNone(rid)

    def test_16_verify_family_member_permissions(self):
        """Scenario 16: Family members have read-only access; write operations are rejected."""
        # Family can view readings
        readings = get_health_readings(self.e_id, limit=5, user=self.family)
        self.assertIsInstance(readings, list)

        # Family cannot add readings (PermissionError)
        with self.assertRaises(PermissionError):
            add_health_reading(
                elderly_user_id=self.e_id,
                reading_type="Blood Pressure",
                reading_value="120/80 mmHg",
                systolic=120,
                diastolic=80,
                user=self.family,
            )

        # Family cannot correct readings (PermissionError)
        readings = get_health_readings(self.e_id, limit=1, user=self.family)
        if readings:
            target_id = readings[0]["id"]
            with self.assertRaises(PermissionError):
                correct_health_reading(
                    reading_id=target_id,
                    elderly_user_id=self.e_id,
                    new_value="122/80 mmHg",
                    reason="Unauthorized attempt",
                    user=self.family,
                )

    def test_17_prevent_access_to_unrelated_elderly_profiles(self):
        """Scenario 17: Prevent access to unrelated elderly profiles (cross-ward protection)."""
        unrelated_ward_id = 99999

        with self.assertRaises(PermissionError):
            get_health_readings(unrelated_ward_id, user=self.caregiver)

        with self.assertRaises(PermissionError):
            add_health_reading(
                elderly_user_id=unrelated_ward_id,
                reading_type="Weight",
                reading_value="60 kg",
                user=self.caregiver,
            )

    def test_18_verify_persistence_across_restart(self):
        """Scenario 18: Verify health records and audit trails persist across database re-initialization."""
        test_val = "123/79 mmHg"
        rid = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Blood Pressure",
            reading_value=test_val,
            systolic=123,
            diastolic=79,
            unit="mmHg",
            recorded_on=date.today().isoformat(),
            user=self.caregiver,
        )

        # Simulate restart by calling init_db again
        database.init_db()

        readings = get_health_readings(self.e_id, limit=20, user=self.caregiver)
        match = next((r for r in readings if r["id"] == rid), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["reading_value"], test_val)

    def test_19_regression_medication_functionality(self):
        """Scenario 19: Verify existing medication management features continue working."""
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Health Test Med",
            dosage="1 tab",
            frequency="Once daily",
            schedule_time="09:00",
            start_date=today_str,
            user=self.caregiver,
        )
        self.assertIsNotNone(med_id)

        sched = get_today_schedule(self.e_id)
        self.assertTrue(any(s["medication_id"] == med_id for s in sched))

        # Record dose taken
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.e_id,
            scheduled_date=today_str,
            scheduled_time="09:00",
            status="taken",
            recorded_by=self.c_id,
        )

    def test_20_regression_reminder_functionality(self):
        """Scenario 20: Verify existing reminder and escalation engine continues working."""
        counts = sync_reminders_and_escalations(self.e_id)
        self.assertIsInstance(counts, dict)
        self.assertIn("escalated", counts)
        self.assertIn("completed", counts)

    def test_21_regression_care_circle_functionality(self):
        """Scenario 21: Verify Care Circle membership and care notes remain functional."""
        members = get_care_circle_members(self.e_id)
        self.assertGreater(len(members), 0)

        # Add a shared care note
        ok, msg, nid = add_care_note(
            elderly_user_id=self.e_id,
            author_user=self.caregiver,
            title="Routine Morning Note",
            content="Asha had regular breakfast and took morning medications.",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(nid)

        notes = get_care_notes(self.e_id, user=self.caregiver)
        self.assertTrue(any(n["id"] == nid for n in notes))

    def test_22_regression_appointment_functionality(self):
        """Scenario 22: Verify appointment scheduling, rescheduling, and reminders remain functional."""
        today = date.today()
        appt_d = (today + timedelta(days=5)).isoformat()
        aid = add_appointment(
            elderly_user_id=self.e_id,
            doctor_name="Dr. Health Specialist",
            hospital="Care City Clinic",
            appointment_date=appt_d,
            appointment_time="10:00 AM",
            appointment_type="Specialist consultation",
            reason="Cardiology review",
            user=self.caregiver,
        )
        self.assertIsNotNone(aid)

        # Reschedule visit
        new_d = (today + timedelta(days=7)).isoformat()
        reschedule_appointment(aid, self.e_id, new_d, "11:30 AM", "Rescheduled per doctor request", user=self.caregiver)

        appts = get_appointments(self.e_id, status="all", user=self.caregiver)
        match = next(a for a in appts if a["id"] == aid)
        self.assertEqual(match["appointment_date"], new_d)

        # Mark completed with post-visit notes
        complete_appointment(aid, self.e_id, post_visit_notes="All vitals normal; renew prescription.", user=self.caregiver)
        completed_match = next(a for a in get_appointments(self.e_id, status="completed", user=self.caregiver) if a["id"] == aid)
        self.assertEqual(completed_match["status"], "completed")


if __name__ == "__main__":
    unittest.main()
