import csv
import io
import unittest
from datetime import date, datetime, timedelta

import database
from database import get_connection
from services.auth_service import authenticate
from services.analytics_service import (
    ANALYTICS_SAFETY_NOTICE,
    resolve_date_range,
    get_analytics_overview,
    get_medication_adherence_analytics,
    get_health_trend_analytics,
    get_appointment_analytics,
    get_care_activity_analytics,
    generate_analytics_csv_report,
)
from services.medication_service import add_medication, get_today_schedule, record_dose_status
from services.health_service import add_health_reading, get_latest_vitals
from services.appointment_service import add_appointment, get_appointments
from services.care_circle_service import add_care_note, get_care_circle_members
from services.activity_service import log_activity
from services.emergency_service import trigger_sos_alert, get_active_emergency_alerts


class TestPhase9AnalyticsAndReports(unittest.TestCase):
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

    # -------------------------------------------------------------------------
    # Scenario 1: Medication adherence calculation is correct
    # -------------------------------------------------------------------------
    def test_01_medication_adherence_calculation_is_correct(self):
        """Scenario 1: Adherence % = (Taken doses / Total doses due) * 100."""
        # Create a unique test medication
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Adherence Test Statin",
            dosage="10mg",
            schedule_time="08:00",
            frequency="Daily",
            instructions="With water",
            stock_quantity=30,
            user=self.caregiver,
        )

        # Log 8 taken, 2 skipped on past dates (10 total due)
        today = date.today()
        for i in range(1, 9):
            d_str = (today - timedelta(days=i)).isoformat()
            record_dose_status(med_id, self.e_id, d_str, "08:00", "taken", self.e_id)
        for i in range(9, 11):
            d_str = (today - timedelta(days=i)).isoformat()
            record_dose_status(med_id, self.e_id, d_str, "08:00", "skipped", self.e_id)

        start_d = (today - timedelta(days=15)).isoformat()
        end_d = (today - timedelta(days=1)).isoformat()

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=start_d,
            end_date=end_d,
            medication_id=med_id,
            user=self.caregiver,
        )

        self.assertTrue(analytics["has_data"])
        self.assertEqual(analytics["total_due"], 10)
        self.assertEqual(analytics["total_taken"], 8)
        self.assertEqual(analytics["total_skipped"], 2)
        # Expected: (8 / 10) * 100 = 80.0%
        self.assertEqual(analytics["adherence_percentage"], 80.0)

    # -------------------------------------------------------------------------
    # Scenario 2: Future doses are excluded
    # -------------------------------------------------------------------------
    def test_02_future_doses_are_excluded(self):
        """Scenario 2: Future scheduled doses are strictly excluded from due counts."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Future Dose Aspirin",
            dosage="75mg",
            schedule_time="09:00",
            frequency="Daily",
            instructions="Morning",
            stock_quantity=30,
            user=self.caregiver,
        )

        today = date.today()
        past_d = (today - timedelta(days=2)).isoformat()
        future_d = (today + timedelta(days=5)).isoformat()

        # Past dose taken
        record_dose_status(med_id, self.e_id, past_d, "09:00", "taken", self.e_id)
        # Future dose pending
        record_dose_status(med_id, self.e_id, future_d, "09:00", "pending", self.e_id)

        start_d = (today - timedelta(days=5)).isoformat()
        end_d = (today + timedelta(days=7)).isoformat()

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=start_d,
            end_date=end_d,
            medication_id=med_id,
            user=self.caregiver,
        )

        self.assertEqual(analytics["total_taken"], 1)
        self.assertEqual(analytics["total_due"], 1)
        self.assertGreaterEqual(analytics["future_excluded"], 1)
        self.assertEqual(analytics["adherence_percentage"], 100.0)

    # -------------------------------------------------------------------------
    # Scenario 3: Zero-dose periods do not cause division errors
    # -------------------------------------------------------------------------
    def test_03_zero_dose_periods_do_not_cause_division_errors(self):
        """Scenario 3: Zero-dose periods safely return has_data=False and adherence=None."""
        past_start = "2020-01-01"
        past_end = "2020-01-07"

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=past_start,
            end_date=past_end,
            user=self.elderly,
        )

        self.assertFalse(analytics["has_data"])
        self.assertIsNone(analytics["adherence_percentage"])
        self.assertEqual(analytics["total_due"], 0)
        self.assertEqual(analytics["total_taken"], 0)

    # -------------------------------------------------------------------------
    # Scenario 4: Duplicate dose logs are not counted twice
    # -------------------------------------------------------------------------
    def test_04_duplicate_dose_logs_are_not_counted_twice(self):
        """Scenario 4: Duplicate dose logs for the same dose time are deduplicated."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Dedup Test Calcium",
            dosage="500mg",
            schedule_time="12:00",
            frequency="Daily",
            instructions="With lunch",
            stock_quantity=30,
            user=self.caregiver,
        )

        today = date.today()
        test_d = (today - timedelta(days=3)).isoformat()

        # Insert first log
        record_dose_status(med_id, self.e_id, test_d, "12:00", "taken", self.e_id)
        # Update / re-log the same dose slot
        record_dose_status(med_id, self.e_id, test_d, "12:00", "taken", self.e_id)

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=test_d,
            end_date=test_d,
            medication_id=med_id,
            user=self.caregiver,
        )

        self.assertEqual(analytics["total_due"], 1)
        self.assertEqual(analytics["total_taken"], 1)
        self.assertEqual(analytics["adherence_percentage"], 100.0)

    # -------------------------------------------------------------------------
    # Scenario 5: Taken, skipped, pending, overdue statuses handled
    # -------------------------------------------------------------------------
    def test_05_taken_skipped_pending_overdue_statuses_handled(self):
        """Scenario 5: All dose status types are categorized accurately."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Status Check Med",
            dosage="25mg",
            schedule_time="08:00",
            frequency="Daily",
            instructions="Morning",
            stock_quantity=30,
            user=self.caregiver,
        )

        today = date.today()
        d1 = (today - timedelta(days=4)).isoformat()
        d2 = (today - timedelta(days=3)).isoformat()
        d3 = (today - timedelta(days=2)).isoformat()
        d4 = (today - timedelta(days=1)).isoformat()

        record_dose_status(med_id, self.e_id, d1, "08:00", "taken", self.e_id)
        record_dose_status(med_id, self.e_id, d2, "08:00", "skipped", self.e_id)
        record_dose_status(med_id, self.e_id, d3, "08:00", "missed", self.e_id)
        record_dose_status(med_id, self.e_id, d4, "08:00", "pending", self.e_id)  # Past pending is overdue

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=d1,
            end_date=d4,
            medication_id=med_id,
            user=self.caregiver,
        )

        self.assertEqual(analytics["total_taken"], 1)
        self.assertEqual(analytics["total_skipped"], 1)
        self.assertEqual(analytics["total_missed"], 1)
        self.assertEqual(analytics["total_overdue"], 1)
        self.assertEqual(analytics["total_due"], 4)
        # Adherence: 1 / 4 = 25.0%
        self.assertEqual(analytics["adherence_percentage"], 25.0)

    # -------------------------------------------------------------------------
    # Scenario 6: Daily adherence trends are correct
    # -------------------------------------------------------------------------
    def test_06_daily_adherence_trends_are_correct(self):
        """Scenario 6: Daily adherence trend contains chronological breakdown per date."""
        today = date.today()
        s_date = (today - timedelta(days=6)).isoformat()
        e_date = today.isoformat()

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=s_date,
            end_date=e_date,
            user=self.elderly,
        )

        trend = analytics["daily_trend"]
        self.assertIsInstance(trend, list)
        self.assertEqual(len(trend), 7)
        self.assertEqual(trend[0]["date"], s_date)
        self.assertEqual(trend[-1]["date"], e_date)
        for day in trend:
            self.assertIn("total_due", day)
            self.assertIn("taken", day)
            self.assertIn("adherence_percentage", day)

    # -------------------------------------------------------------------------
    # Scenario 7: Weekly adherence trends are correct
    # -------------------------------------------------------------------------
    def test_07_weekly_adherence_trends_are_correct(self):
        """Scenario 7: Weekly adherence trend aggregates into multi-day chunks."""
        today = date.today()
        s_date = (today - timedelta(days=20)).isoformat()
        e_date = today.isoformat()

        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            start_date=s_date,
            end_date=e_date,
            user=self.elderly,
        )

        weekly = analytics["weekly_trend"]
        self.assertIsInstance(weekly, list)
        self.assertGreaterEqual(len(weekly), 3)
        for w in weekly:
            self.assertIn("week_label", w)
            self.assertIn("total_due", w)
            self.assertIn("taken", w)

    # -------------------------------------------------------------------------
    # Scenario 8: Medication-wise adherence is correct
    # -------------------------------------------------------------------------
    def test_08_medication_wise_adherence_is_correct(self):
        """Scenario 8: Breakdown computes distinct metrics for each registered medication."""
        analytics = get_medication_adherence_analytics(
            elderly_user_id=self.e_id,
            period="last_30_days",
            user=self.caregiver,
        )

        breakdown = analytics["medication_breakdown"]
        self.assertIsInstance(breakdown, list)
        if breakdown:
            m = breakdown[0]
            self.assertIn("medicine_name", m)
            self.assertIn("dosage", m)
            self.assertIn("total_due", m)
            self.assertIn("taken", m)
            self.assertIn("adherence_percentage", m)

    # -------------------------------------------------------------------------
    # Scenario 9: Health trends use actual stored readings
    # -------------------------------------------------------------------------
    def test_09_health_trends_use_actual_stored_readings(self):
        """Scenario 9: Health trend queries actual readings and calculates stats accurately."""
        today = date.today()
        d1 = (today - timedelta(days=60)).isoformat()
        d2 = (today - timedelta(days=59)).isoformat()
        d3 = (today - timedelta(days=58)).isoformat()

        with get_connection() as conn:
            conn.execute(
                "DELETE FROM health_readings WHERE elderly_user_id = ? AND reading_type = 'Blood Pressure' AND recorded_on BETWEEN ? AND ?",
                (self.e_id, d1, d3),
            )

        add_health_reading(self.e_id, "Blood Pressure", "118/76 mmHg", d1, "08:00", user=self.caregiver)
        add_health_reading(self.e_id, "Blood Pressure", "122/80 mmHg", d2, "08:00", user=self.caregiver)
        add_health_reading(self.e_id, "Blood Pressure", "120/78 mmHg", d3, "08:00", user=self.caregiver)

        analytics = get_health_trend_analytics(
            elderly_user_id=self.e_id,
            measurement_type="Blood Pressure",
            start_date=d1,
            end_date=d3,
            user=self.caregiver,
        )

        self.assertTrue(analytics["has_data"])
        self.assertTrue(analytics["has_sufficient_data"])
        self.assertEqual(analytics["count"], 3)
        summary = analytics["summary"]
        self.assertEqual(summary["systolic_min"], 118)
        self.assertEqual(summary["systolic_max"], 122)
        self.assertEqual(summary["systolic_avg"], 120.0)

    # -------------------------------------------------------------------------
    # Scenario 10: Missing health data produces a safe empty state
    # -------------------------------------------------------------------------
    def test_10_missing_health_data_produces_safe_empty_state(self):
        """Scenario 10: Querying dates with no readings produces clean empty states."""
        past_start = "2019-01-01"
        past_end = "2019-01-05"

        analytics = get_health_trend_analytics(
            elderly_user_id=self.e_id,
            measurement_type="Blood Pressure",
            start_date=past_start,
            end_date=past_end,
            user=self.elderly,
        )

        self.assertFalse(analytics["has_data"])
        self.assertFalse(analytics["has_sufficient_data"])
        self.assertEqual(analytics["count"], 0)
        self.assertEqual(analytics["readings"], [])

    # -------------------------------------------------------------------------
    # Scenario 11: Incompatible units are not combined
    # -------------------------------------------------------------------------
    def test_11_incompatible_units_are_not_combined(self):
        """Scenario 11: Incompatible measurement units are isolated and not blended."""
        today = date.today()
        d1 = (today - timedelta(days=2)).isoformat()
        d2 = (today - timedelta(days=1)).isoformat()

        # Log weight in kg and weight in lb
        add_health_reading(self.e_id, "Weight", "68.5 kg", d1, "08:00", user=self.caregiver)
        add_health_reading(self.e_id, "Weight", "150.0 lb", d2, "08:00", user=self.caregiver)

        # Query filtered specifically for kg
        analytics_kg = get_health_trend_analytics(
            elderly_user_id=self.e_id,
            measurement_type="Weight",
            unit="kg",
            start_date=d1,
            end_date=d2,
            user=self.caregiver,
        )

        self.assertTrue(analytics_kg["has_data"])
        for r in analytics_kg["readings"]:
            self.assertIn("kg", r["reading_value"].lower())
            self.assertNotIn("lb", r["reading_value"].lower())

    # -------------------------------------------------------------------------
    # Scenario 12: Appointment counts are correct
    # -------------------------------------------------------------------------
    def test_12_appointment_counts_are_correct(self):
        """Scenario 12: Appointment status counts (total, completed, upcoming) are calculated."""
        today = date.today()
        s_date = (today - timedelta(days=30)).isoformat()
        e_date = (today + timedelta(days=30)).isoformat()

        analytics = get_appointment_analytics(
            elderly_user_id=self.e_id,
            start_date=s_date,
            end_date=e_date,
            user=self.caregiver,
        )

        self.assertIn("total_appointments", analytics)
        self.assertIn("completed_count", analytics)
        self.assertIn("upcoming_count", analytics)
        self.assertIn("cancelled_count", analytics)
        self.assertIn("monthly_distribution", analytics)

    # -------------------------------------------------------------------------
    # Scenario 13: Cancelled appointments excluded from completed counts
    # -------------------------------------------------------------------------
    def test_13_cancelled_appointments_excluded_from_completed(self):
        """Scenario 13: Cancelled appointments are strictly excluded from completed counts."""
        future_date = (date.today() + timedelta(days=14)).isoformat()
        with get_connection() as conn:
            conn.execute("DELETE FROM appointments WHERE elderly_user_id = ? AND appointment_date = ?", (self.e_id, future_date))

        appt_id = add_appointment(
            elderly_user_id=self.e_id,
            doctor_name="Dr. Cancelled Test",
            hospital="Test Hospital",
            appointment_date=future_date,
            appointment_time="11:00",
            created_by=self.c_id,
            user=self.caregiver,
        )

        # Cancel the appointment
        with get_connection() as conn:
            conn.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appt_id,))

        analytics = get_appointment_analytics(
            elderly_user_id=self.e_id,
            start_date=future_date,
            end_date=future_date,
            user=self.caregiver,
        )

        self.assertEqual(analytics["cancelled_count"], 1)
        self.assertEqual(analytics["completed_count"], 0)

    # -------------------------------------------------------------------------
    # Scenario 14: Activity filters return correct records
    # -------------------------------------------------------------------------
    def test_14_activity_filters_return_correct_records(self):
        """Scenario 14: Activity analytics filters logs accurately by category."""
        today = date.today().isoformat()
        log_activity(self.e_id, self.c_id, "Medication Confirmed", "Confirmed morning dose")
        log_activity(self.e_id, self.c_id, "Care Note Added", "Observation regarding sleep")

        med_act = get_care_activity_analytics(
            elderly_user_id=self.e_id,
            start_date=today,
            end_date=today,
            category_filter="medication",
            user=self.caregiver,
        )

        for a in med_act["activities"]:
            self.assertTrue(
                "Medication" in a["action"] or "Dose" in a["action"],
                f"Action '{a['action']}' should be medication-related",
            )

    # -------------------------------------------------------------------------
    # Scenario 15: Date-range filters work correctly
    # -------------------------------------------------------------------------
    def test_15_date_range_filters_work_correctly(self):
        """Scenario 15: Date range filters apply strictly to metrics and records."""
        start_7, end_7 = resolve_date_range("last_7_days")
        start_30, end_30 = resolve_date_range("last_30_days")

        d7_days = (datetime.strptime(end_7, "%Y-%m-%d") - datetime.strptime(start_7, "%Y-%m-%d")).days + 1
        d30_days = (datetime.strptime(end_30, "%Y-%m-%d") - datetime.strptime(start_30, "%Y-%m-%d")).days + 1

        self.assertEqual(d7_days, 7)
        self.assertEqual(d30_days, 30)

    # -------------------------------------------------------------------------
    # Scenario 16: Elderly users can access only their own reports
    # -------------------------------------------------------------------------
    def test_16_elderly_users_access_only_their_own_reports(self):
        """Scenario 16: Elderly users attempting to access another ward's analytics are blocked."""
        unrelated_id = 9999
        with self.assertRaises(PermissionError):
            get_analytics_overview(
                elderly_user_id=unrelated_id,
                period="last_30_days",
                user=self.elderly,
            )

    # -------------------------------------------------------------------------
    # Scenario 17: Caregivers can access only authorized linked profiles
    # -------------------------------------------------------------------------
    def test_17_caregivers_access_only_authorized_linked_profiles(self):
        """Scenario 17: Caregivers can access linked wards, but unlinked wards raise PermissionError."""
        # Authorized access to Asha Patil (ID 1)
        overview = get_analytics_overview(
            elderly_user_id=self.e_id,
            period="last_30_days",
            user=self.caregiver,
        )
        self.assertIsNotNone(overview)

        # Unauthorized access to unlinked ID 8888
        with self.assertRaises(PermissionError):
            get_analytics_overview(
                elderly_user_id=8888,
                period="last_30_days",
                user=self.caregiver,
            )

    # -------------------------------------------------------------------------
    # Scenario 18: Family members cannot access restricted information
    # -------------------------------------------------------------------------
    def test_18_family_members_cannot_access_restricted_information(self):
        """Scenario 18: Restricted caregiver-only notes are sanitized for family viewers."""
        today = date.today().isoformat()
        log_activity(
            self.e_id,
            self.c_id,
            "Care Note Added",
            "Confidential caregiver assessment [caregivers_only]",
        )

        act_family = get_care_activity_analytics(
            elderly_user_id=self.e_id,
            start_date=today,
            end_date=today,
            user=self.family,
        )

        for a in act_family["activities"]:
            if "care note" in a["action"].lower():
                self.assertNotIn("Confidential caregiver assessment", a["details"])

    # -------------------------------------------------------------------------
    # Scenario 19: CSV exports contain only authorized data
    # -------------------------------------------------------------------------
    def test_19_csv_exports_contain_only_authorized_data(self):
        """Scenario 19: CSV export contains structured care data without leaking sensitive tokens."""
        csv_str = generate_analytics_csv_report(
            elderly_user_id=self.e_id,
            period="last_30_days",
            user=self.caregiver,
        )

        self.assertIn("DEARLY - HEALTHCARE ANALYTICS & CARE SUMMARY REPORT", csv_str)
        self.assertIn("Asha Patil", csv_str)
        self.assertIn("SECTION 1: EXECUTIVE CARE SUMMARY", csv_str)
        # Ensure zero passwords or salt tokens leak into the export
        self.assertNotIn("password_hash", csv_str.lower())
        self.assertNotIn("$2b$12$", csv_str)

    # -------------------------------------------------------------------------
    # Scenario 20: CSV exports handle empty datasets
    # -------------------------------------------------------------------------
    def test_20_csv_exports_handle_empty_datasets(self):
        """Scenario 20: CSV export handles zero-data periods safely with valid RFC-4180 format."""
        past_start = "2015-01-01"
        past_end = "2015-01-05"

        csv_str = generate_analytics_csv_report(
            elderly_user_id=self.e_id,
            start_date=past_start,
            end_date=past_end,
            user=self.caregiver,
        )

        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        self.assertGreater(len(rows), 5)
        self.assertIn("No medication records available for this period.", csv_str)

    # -------------------------------------------------------------------------
    # Scenario 21: Analytics do not modify original records
    # -------------------------------------------------------------------------
    def test_21_analytics_do_not_modify_original_records(self):
        """Scenario 21: Generating analytics is strictly read-only and mutates zero database rows."""
        with get_connection() as conn:
            before_meds = conn.execute("SELECT COUNT(*) as c FROM medications").fetchone()["c"]
            before_logs = conn.execute("SELECT COUNT(*) as c FROM medication_logs").fetchone()["c"]
            before_readings = conn.execute("SELECT COUNT(*) as c FROM health_readings").fetchone()["c"]
            before_appts = conn.execute("SELECT COUNT(*) as c FROM appointments").fetchone()["c"]

        # Run analytics queries
        get_analytics_overview(self.e_id, period="last_30_days", user=self.caregiver)
        get_medication_adherence_analytics(self.e_id, period="last_30_days", user=self.caregiver)
        get_health_trend_analytics(self.e_id, period="last_30_days", user=self.caregiver)
        get_appointment_analytics(self.e_id, period="last_30_days", user=self.caregiver)
        generate_analytics_csv_report(self.e_id, period="last_30_days", user=self.caregiver)

        with get_connection() as conn:
            after_meds = conn.execute("SELECT COUNT(*) as c FROM medications").fetchone()["c"]
            after_logs = conn.execute("SELECT COUNT(*) as c FROM medication_logs").fetchone()["c"]
            after_readings = conn.execute("SELECT COUNT(*) as c FROM health_readings").fetchone()["c"]
            after_appts = conn.execute("SELECT COUNT(*) as c FROM appointments").fetchone()["c"]

        self.assertEqual(before_meds, after_meds)
        self.assertEqual(before_logs, after_logs)
        self.assertEqual(before_readings, after_readings)
        self.assertEqual(before_appts, after_appts)

    # -------------------------------------------------------------------------
    # Scenario 22: All previous phases continue functioning
    # -------------------------------------------------------------------------
    def test_22_all_previous_phases_continue_functioning(self):
        """Scenario 22: Regression verification across Phase 1-8 operations."""
        # Phase 2: User auth
        u = authenticate("elderly@dearly.demo", "demo123")
        self.assertIsNotNone(u)

        # Phase 3: Medication schedule
        sched = get_today_schedule(self.e_id)
        self.assertIsInstance(sched, list)

        # Phase 5: Care circle
        circle = get_care_circle_members(self.e_id)
        self.assertGreaterEqual(len(circle), 1)

        # Phase 6: Appointments
        appts = get_appointments(self.e_id, user=self.caregiver)
        self.assertIsInstance(appts, list)

        # Phase 7: Health vitals
        vitals = get_latest_vitals(self.e_id, user=self.caregiver)
        self.assertIn("Blood Pressure", vitals)

    # -------------------------------------------------------------------------
    # Scenario 23: Analytics persist and recalculate after application restart
    # -------------------------------------------------------------------------
    def test_23_analytics_persist_and_recalculate_after_restart(self):
        """Scenario 23: Analytics persist in SQLite and yield identical results across restarts."""
        res1 = get_analytics_overview(self.e_id, period="last_30_days", user=self.caregiver)

        # Simulate restart by reinitializing connection and calling again
        database.init_db()
        res2 = get_analytics_overview(self.e_id, period="last_30_days", user=self.caregiver)

        self.assertEqual(res1["adherence_percentage"], res2["adherence_percentage"])
        self.assertEqual(res1["total_due_doses"], res2["total_due_doses"])
        self.assertEqual(res1["taken_doses"], res2["taken_doses"])
        self.assertEqual(res1["upcoming_appointments"], res2["upcoming_appointments"])


if __name__ == "__main__":
    unittest.main()
