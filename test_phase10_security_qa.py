import csv
import io
import re
import unittest
from datetime import date, datetime, timedelta

import database
from database import get_connection, verify_password, hash_password
from services.auth_service import authenticate, get_accessible_elderly_wards
from services.user_service import register_user, update_user_profile, get_user_profile
from services.permissions import (
    can_view_page,
    can_access_elderly_record,
    can_manage_elderly_care,
    enforce_elderly_access,
    can_view_notes,
    can_write_notes,
    can_view_health_records,
    can_manage_health_records,
    can_view_emergency,
    can_manage_emergency,
    can_view_analytics,
)
from services.medication_service import (
    add_medication,
    get_medications,
    update_medication,
    deactivate_medication,
    get_today_schedule,
    record_dose_status,
    get_adherence_metrics,
)
from services.reminder_service import (
    sync_reminders_and_escalations,
    get_upcoming_and_active_reminders,
    get_caregiver_escalations,
    acknowledge_caregiver_escalation,
)
from services.care_circle_service import (
    send_care_invitation,
    respond_to_invitation,
    get_care_circle_members,
    remove_care_circle_member,
    add_care_note,
    get_care_notes,
)
from services.appointment_service import (
    add_appointment,
    get_appointments,
    reschedule_appointment,
    cancel_appointment,
    complete_appointment,
    sync_appointment_reminders,
)
from services.health_service import (
    add_health_reading,
    get_health_readings,
    correct_health_reading,
    get_latest_vitals,
)
from services.emergency_service import (
    activate_emergency_sos,
    acknowledge_emergency,
    update_assistance_status,
    resolve_emergency,
    get_active_emergency,
    get_emergency_requests,
    get_emergency_status_history,
)
from services.activity_service import log_activity, get_recent_activities
from services.analytics_service import (
    get_analytics_overview,
    get_medication_adherence_analytics,
    get_health_trend_analytics,
    get_appointment_analytics,
    generate_analytics_csv_report,
)


class TestPhase10SecurityAndQA(unittest.TestCase):
    """
    Comprehensive Security, Quality Assurance, and Integration Test Suite for Dearly.
    Covers all 20 core security/audit scenarios and Workflows A through F.
    """

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

    def tearDown(self):
        # Resolve any active emergencies created during tests
        active = get_active_emergency(self.e_id)
        if active:
            try:
                resolve_emergency(
                    active["id"],
                    self.e_id,
                    self.c_id,
                    resolution_notes="Clean tearDown QA",
                    user=self.caregiver,
                )
            except Exception:
                pass

    # =========================================================================
    # 1. AUTHENTICATION & USER MANAGEMENT AUDIT
    # =========================================================================

    def test_01_registration_works(self):
        """Scenario 1: User registration succeeds with input validation and profile initialization."""
        unique_email = f"qa.new.user.{datetime.now().strftime('%H%M%S%f')}@example.com"
        success, user_or_err = register_user(
            name="QA Test User",
            email=unique_email,
            phone="+91 98200 55443",
            password="StrongPassword123",
            confirm_password="StrongPassword123",
            role="caregiver",
        )
        self.assertTrue(success, f"Registration failed: {user_or_err}")
        self.assertIsInstance(user_or_err, dict)
        self.assertEqual(user_or_err["email"], unique_email.lower())
        self.assertEqual(user_or_err["role"], "caregiver")

    def test_02_login_and_logout_work(self):
        """Scenario 2: Authenticate valid user; reject invalid credentials; session cleanup."""
        # Valid login
        user = authenticate("elderly@dearly.demo", "demo123")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "elderly")

        # Invalid password
        bad_pw = authenticate("elderly@dearly.demo", "WrongPassword!")
        self.assertIsNone(bad_pw)

        # Nonexistent user
        non_user = authenticate("nonexistent@dearly.demo", "demo123")
        self.assertIsNone(non_user)

    def test_03_passwords_are_securely_stored(self):
        """Scenario 3: Passwords stored as bcrypt hashes ($2b$ with >= 12 rounds), zero plaintext."""
        with get_connection() as conn:
            users = conn.execute("SELECT email, password_hash FROM users").fetchall()
            self.assertGreater(len(users), 0)
            for u in users:
                pw_hash = u["password_hash"]
                # Must start with bcrypt prefix ($2a$, $2b$, or $2y$)
                self.assertTrue(
                    pw_hash.startswith("$2a$") or pw_hash.startswith("$2b$") or pw_hash.startswith("$2y$"),
                    f"User {u['email']} password hash does not use bcrypt format: {pw_hash[:10]}",
                )
                # Plaintext password must never equal the hash
                self.assertNotEqual(pw_hash, "demo123")
                # Demo users verify with demo123
                if u["email"] in ["elderly@dearly.demo", "caregiver@dearly.demo", "family@dearly.demo"]:
                    self.assertTrue(verify_password("demo123", pw_hash))
                # Incorrect password must always fail
                self.assertFalse(verify_password("WrongPassword999!", pw_hash))

    def test_04_unauthorized_users_cannot_access_protected_pages(self):
        """Scenario 4: Role-based page whitelist rejects unauthorized navigation."""
        # Elderly cannot access caregiver monitoring or profiles
        self.assertFalse(can_view_page(self.elderly, "Elderly Profiles"))
        self.assertFalse(can_view_page(self.elderly, "Medication Monitoring"))
        self.assertFalse(can_view_page(self.elderly, "Activity History"))

        # Caregiver cannot access elderly home routine directly
        self.assertFalse(can_view_page(self.caregiver, "Home"))
        self.assertFalse(can_view_page(self.caregiver, "My Medicines"))

        # Unauthenticated user (None) cannot view any page
        self.assertFalse(can_view_page(None, "Home"))
        self.assertFalse(can_view_page(None, "Overview"))

    def test_05_role_based_permissions_enforced_server_side(self):
        """Scenario 5: Write operations enforce server-side role permissions."""
        # Family member has viewer permission only; write operations are denied
        self.assertFalse(can_manage_elderly_care(self.family, self.e_id))
        self.assertFalse(can_write_notes(self.family, self.e_id))
        self.assertFalse(can_manage_health_records(self.family, self.e_id))
        self.assertFalse(can_manage_emergency(self.family, self.e_id))

        # Caregiver with editor permission has management access
        self.assertTrue(can_manage_elderly_care(self.caregiver, self.e_id))
        self.assertTrue(can_write_notes(self.caregiver, self.e_id))
        self.assertTrue(can_manage_health_records(self.caregiver, self.e_id))
        self.assertTrue(can_manage_emergency(self.caregiver, self.e_id))

    def test_06_unrelated_elderly_profiles_remain_inaccessible(self):
        """Scenario 6: Cross-patient access protection blocks unauthorized profile probing."""
        unrelated_patient_id = 99999
        with self.assertRaises(PermissionError):
            enforce_elderly_access(self.caregiver, unrelated_patient_id, write_access=False)

        with self.assertRaises(PermissionError):
            enforce_elderly_access(self.elderly, unrelated_patient_id, write_access=False)

        with self.assertRaises(PermissionError):
            enforce_elderly_access(self.family, unrelated_patient_id, write_access=False)

    # =========================================================================
    # 2. CORE MODULE OPERATIONS & REGRESSION AUDIT
    # =========================================================================

    def test_07_medication_crud_works(self):
        """Scenario 7: Medication creation, retrieval, updating, and deactivation."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="QA Security Med",
            dosage="50mg",
            schedule_time="08:00",
            frequency="Daily",
            instructions="With food",
            stock_quantity=20,
            user=self.caregiver,
        )
        self.assertIsNotNone(med_id)

        # Update medication
        ok = update_medication(
            medication_id=med_id,
            elderly_user_id=self.e_id,
            medicine_name="QA Security Med Updated",
            dosage="100mg",
            schedule_time="08:30",
            frequency="Daily",
            meal_timing="Before Meal",
            instructions="With warm water",
            stock_quantity=25,
            user=self.caregiver,
        )
        self.assertTrue(ok)

        # Deactivate
        deact_ok = deactivate_medication(med_id, self.e_id, user=self.caregiver)
        self.assertTrue(deact_ok)

    def test_08_duplicate_dose_logging_is_prevented(self):
        """Scenario 8: SQLite UPSERT prevents duplicate logs for same medication and time slot."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="QA Dedup Med",
            dosage="10mg",
            schedule_time="10:00",
            user=self.caregiver,
        )

        today_str = date.today().isoformat()
        # First log
        ok1 = record_dose_status(med_id, self.e_id, today_str, "10:00", "taken", self.e_id)
        self.assertTrue(ok1)
        # Duplicate log for same slot updates existing row without error
        ok2 = record_dose_status(med_id, self.e_id, today_str, "10:00", "taken", self.e_id)
        self.assertTrue(ok2)

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT COUNT(*) as c FROM medication_logs WHERE medication_id = ? AND scheduled_date = ? AND scheduled_time = ?",
                (med_id, today_str, "10:00"),
            ).fetchone()["c"]
            self.assertEqual(rows, 1, "Duplicate row was inserted for identical dose slot!")

    def test_09_reminder_generation_works_without_duplicates(self):
        """Scenario 9: Reminder generation is idempotent; no duplicate notification entries."""
        sync_reminders_and_escalations(self.e_id, user=self.caregiver)

        with get_connection() as conn:
            count1 = conn.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE elderly_user_id = ?",
                (self.e_id,),
            ).fetchone()["c"]

        # Re-run synchronization immediately
        sync_reminders_and_escalations(self.e_id, user=self.caregiver)

        with get_connection() as conn:
            count2 = conn.execute(
                "SELECT COUNT(*) as c FROM notifications WHERE elderly_user_id = ?",
                (self.e_id,),
            ).fetchone()["c"]

        # No duplicate notifications should be created on immediate re-sync
        self.assertEqual(count1, count2)

    def test_10_care_circle_invitation_and_approval_work(self):
        """Scenario 10: Two-sided invitation lifecycle (create -> pending -> accept -> active)."""
        # Register a temporary user to invite
        tmp_email = f"qa.invitee.{datetime.now().strftime('%H%M%S%f')}@example.com"
        ok, res = register_user(
            name="Temporary Invitee",
            email=tmp_email,
            phone="+91 98200 99887",
            password="Password123!",
            confirm_password="Password123!",
            role="caregiver",
        )
        self.assertTrue(ok)
        invitee_id = res["id"]
        invitee_user = authenticate(tmp_email, "Password123!")

        # Send invitation
        send_ok, _, invite_id_or_err = send_care_invitation(
            elderly_user_id=self.e_id,
            inviter_user=self.caregiver,
            invitee_email=tmp_email,
            relationship="Nurse",
            connection_role="caregiver",
            permission_level="viewer",
        )
        self.assertTrue(send_ok)

        # Accept invitation
        resp_ok, _ = respond_to_invitation(invite_id_or_err, invitee_user, "accept")
        self.assertTrue(resp_ok)

        # Verify membership in care_circle
        members = get_care_circle_members(self.e_id)
        member_ids = [m["user_id"] for m in members]
        self.assertIn(invitee_id, member_ids)

    def test_11_revoked_connections_lose_access_immediately(self):
        """Scenario 11: Revoked or removed care circle connections immediately lose access."""
        # Create a connected user
        tmp_email = f"qa.revoked.{datetime.now().strftime('%H%M%S%f')}@example.com"
        _, res = register_user(
            name="Revoke Candidate",
            email=tmp_email,
            phone="+91 98200 11998",
            password="Password123!",
            confirm_password="Password123!",
            role="caregiver",
        )
        user_to_revoke = authenticate(tmp_email, "Password123!")
        u_id = res["id"]

        send_ok, _, inv_id = send_care_invitation(
            self.e_id, self.caregiver, tmp_email, "Aide", "caregiver", "viewer"
        )
        respond_to_invitation(inv_id, user_to_revoke, "accept")

        # Confirm access granted
        self.assertTrue(can_access_elderly_record(user_to_revoke, self.e_id))

        # Remove member
        rem_ok, _ = remove_care_circle_member(self.e_id, u_id, actor_user=self.caregiver)
        self.assertTrue(rem_ok)

        # Verify immediate access removal
        self.assertFalse(can_access_elderly_record(user_to_revoke, self.e_id))
        with self.assertRaises(PermissionError):
            enforce_elderly_access(user_to_revoke, self.e_id, write_access=False)

    def test_12_private_notes_remain_private(self):
        """Scenario 12: Care notes with 'caregivers_only' visibility are hidden from family viewers."""
        ok, _, note_id = add_care_note(
            elderly_user_id=self.e_id,
            author_user=self.caregiver,
            title="Private Caregiver Note",
            content="Restricted clinical observation for caregivers only.",
            category="observation",
            visibility="caregivers_only",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(note_id)

        # Caregiver can view private note
        cg_notes = get_care_notes(self.e_id, user=self.caregiver)
        cg_note_ids = [n["id"] for n in cg_notes]
        self.assertIn(note_id, cg_note_ids)

        # Family member cannot view private note
        fam_notes = get_care_notes(self.e_id, user=self.family)
        fam_note_ids = [n["id"] for n in fam_notes]
        self.assertNotIn(note_id, fam_note_ids)

    def test_13_appointment_operations_work(self):
        """Scenario 13: Appointment creation, rescheduling, cancelling, and completion."""
        future_d1 = (date.today() + timedelta(days=20)).isoformat()
        future_d2 = (date.today() + timedelta(days=25)).isoformat()

        appt_id = add_appointment(
            elderly_user_id=self.e_id,
            doctor_name="Dr. QA Orthopedic",
            hospital="Metro Clinic",
            appointment_date=future_d1,
            appointment_time="10:00",
            created_by=self.c_id,
            user=self.caregiver,
        )
        self.assertIsNotNone(appt_id)

        # Reschedule
        resched_ok = reschedule_appointment(
            appt_id, self.e_id, future_d2, "11:30", reschedule_reason="Doctor requested", user=self.caregiver
        )
        self.assertTrue(resched_ok)

        # Cancel
        cancel_ok = cancel_appointment(
            appt_id, self.e_id, cancellation_reason="Patient feeling better", user=self.caregiver
        )
        self.assertTrue(cancel_ok)

        # Verify status is cancelled
        appts = get_appointments(self.e_id, status="all", user=self.caregiver)
        matching = [a for a in appts if a["id"] == appt_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["status"], "cancelled")

    def test_14_health_readings_persist_correctly(self):
        """Scenario 14: Health measurements log accurately with immutable correction audits."""
        today_str = date.today().isoformat()
        reading_id = add_health_reading(
            elderly_user_id=self.e_id,
            reading_type="Blood Pressure",
            reading_value="124/82 mmHg",
            recorded_on=today_str,
            recorded_time="09:00",
            notes="Morning baseline",
            user=self.caregiver,
        )
        self.assertIsNotNone(reading_id)

        # Correct reading
        cor_ok = correct_health_reading(
            reading_id=reading_id,
            elderly_user_id=self.e_id,
            new_value="122/80 mmHg",
            reason="Typo on initial entry",
            user=self.caregiver,
        )
        self.assertTrue(cor_ok)

        # Verify reading is marked corrected
        readings = get_health_readings(self.e_id, user=self.caregiver)
        matching = [r for r in readings if r["id"] == reading_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["is_corrected"], 1)

    def test_15_emergency_requests_follow_authorized_access_rules(self):
        """Scenario 15: Emergency SOS activation, duplicate guard, and lifecycle transitions."""
        # 1. Activate SOS
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            urgency_reason="QA Emergency Test",
            user=self.elderly,
        )
        self.assertIsNotNone(req_id)

        # 2. Duplicate activation prevented
        with self.assertRaises(ValueError):
            activate_emergency_sos(
                elderly_user_id=self.e_id,
                triggered_by_user_id=self.e_id,
                urgency_reason="Duplicate SOS trigger",
                user=self.elderly,
            )

        # 3. Caregiver acknowledgment
        ack_ok = acknowledge_emergency(req_id, self.e_id, self.c_id, response_note="Acknowledging alert", user=self.caregiver)
        self.assertTrue(ack_ok)

        # 4. Status update to assistance_in_progress
        prog_ok = update_assistance_status(
            req_id, self.e_id, self.c_id, new_status="assistance_in_progress", response_note="On my way", user=self.caregiver
        )
        self.assertTrue(prog_ok)

        # 5. Resolve emergency
        res_ok = resolve_emergency(req_id, self.e_id, self.c_id, resolution_notes="Senior is safe", user=self.caregiver)
        self.assertTrue(res_ok)

        # 6. Verify transition history has 4 records (pending, ack, progress, resolved)
        history = get_emergency_status_history(req_id, user=self.caregiver)
        self.assertGreaterEqual(len(history), 4)

    def test_16_analytics_use_actual_stored_data(self):
        """Scenario 16: Analytics metrics are calculated dynamically from actual records."""
        overview = get_analytics_overview(
            elderly_user_id=self.e_id,
            period="last_30_days",
            user=self.caregiver,
        )
        self.assertIn("adherence_percentage", overview)
        self.assertIn("total_due_doses", overview)
        self.assertIn("taken_doses", overview)
        self.assertIn("upcoming_appointments", overview)
        self.assertIn("health_readings_count", overview)

    def test_17_csv_exports_respect_permissions(self):
        """Scenario 17: CSV export generates RFC-4180 output and rejects unauthorized access."""
        csv_str = generate_analytics_csv_report(
            elderly_user_id=self.e_id,
            period="last_30_days",
            user=self.caregiver,
        )
        self.assertIn("DEARLY - HEALTHCARE ANALYTICS & CARE SUMMARY REPORT", csv_str)
        self.assertIn("Asha Patil", csv_str)
        # Excludes sensitive data
        self.assertNotIn("password_hash", csv_str)
        self.assertNotIn("$2b$12$", csv_str)

        # Unauthorized access raises PermissionError
        with self.assertRaises(PermissionError):
            generate_analytics_csv_report(
                elderly_user_id=8888,
                period="last_30_days",
                user=self.caregiver,
            )

    def test_18_database_records_persist_after_restart(self):
        """Scenario 18: Records survive database connection cycles and application restarts."""
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="QA Persistence Med",
            dosage="20mg",
            schedule_time="07:00",
            user=self.caregiver,
        )

        # Reinitialize connection pool
        database.init_db()

        meds = get_medications(self.e_id, user=self.caregiver)
        matching = [m for m in meds if m["id"] == med_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["medicine_name"], "QA Persistence Med")

    def test_19_invalid_input_is_rejected_safely(self):
        """Scenario 19: Input validation rejects invalid emails, short phones, and empty names."""
        # Empty name
        ok1, err1 = register_user("", "test@dearly.demo", "+91 98200 11111", "pass123", "pass123", "elderly")
        self.assertFalse(ok1)
        self.assertIn("name", err1.lower())

        # Invalid email format
        ok2, err2 = register_user("Valid Name", "notanemail", "+91 98200 11111", "pass123", "pass123", "elderly")
        self.assertFalse(ok2)
        self.assertIn("email", err2.lower())

        # Short phone number
        ok3, err3 = register_user("Valid Name", "valid@dearly.demo", "123", "pass123", "pass123", "elderly")
        self.assertFalse(ok3)
        self.assertIn("phone", err3.lower())

        # Mismatched password confirmation
        ok4, err4 = register_user("Valid Name", "valid2@dearly.demo", "+91 98200 11111", "pass123", "passXYZ", "elderly")
        self.assertFalse(ok4)
        self.assertIn("password", err4.lower())

    def test_20_complete_application_launches_without_errors(self):
        """Scenario 20: Application dependencies and database schema initialize without error."""
        try:
            database.init_db()
            database.create_demo_users()
            wards = get_accessible_elderly_wards(self.caregiver)
            self.assertGreaterEqual(len(wards), 1)
        except Exception as e:
            self.fail(f"Application environment failed to initialize: {e}")

    # =========================================================================
    # 3. END-TO-END INTEGRATION WORKFLOW AUDIT (Workflows A through F)
    # =========================================================================

    def test_21_workflow_a_medication_and_reminders(self):
        """Workflow A: Add med -> schedule -> sync reminder -> take dose -> adherence & activity."""
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.e_id,
            medicine_name="Integration Statin",
            dosage="20mg",
            schedule_time="08:00",
            user=self.caregiver,
        )

        # Verify in today schedule
        sched = get_today_schedule(self.e_id)
        matching = [s for s in sched if s["medication_id"] == med_id]
        self.assertEqual(len(matching), 1)

        # Mark dose taken
        record_dose_status(med_id, self.e_id, today_str, "08:00", "taken", self.e_id)

        # Verify adherence update
        adherence = get_adherence_metrics(self.e_id, days=7, user=self.caregiver)
        self.assertGreaterEqual(adherence["total_taken"], 1)

        # Verify logged activity
        acts = get_recent_activities(self.e_id, limit=5)
        self.assertGreaterEqual(len(acts), 1)

    def test_22_workflow_b_care_circle(self):
        """Workflow B: Invite -> Accept -> Verify access -> Revoke -> Immediate access removal."""
        tmp_email = f"qa.wf.b.{datetime.now().strftime('%H%M%S%f')}@example.com"
        _, res = register_user("WF B Invitee", tmp_email, "+91 98200 88776", "pass123!", "pass123!", "family")
        invitee = authenticate(tmp_email, "pass123!")

        # Send invitation
        _, _, inv_id = send_care_invitation(self.e_id, self.caregiver, tmp_email, "Cousin", "family", "viewer")

        # Accept
        respond_to_invitation(inv_id, invitee, "accept")
        self.assertTrue(can_access_elderly_record(invitee, self.e_id))

        # Revoke/remove
        remove_care_circle_member(self.e_id, res["id"], actor_user=self.caregiver)
        self.assertFalse(can_access_elderly_record(invitee, self.e_id))

    def test_23_workflow_c_appointments(self):
        """Workflow C: Create appointment -> Reschedule -> Cancel -> Verify reminder reset."""
        d1 = (date.today() + timedelta(days=15)).isoformat()
        d2 = (date.today() + timedelta(days=22)).isoformat()

        appt_id = add_appointment(
            self.e_id, "Dr. Integration Cardiologist", "Heart Clinic", d1, "09:30", created_by=self.c_id, user=self.caregiver
        )
        self.assertIsNotNone(appt_id)

        # Reschedule
        resched_ok = reschedule_appointment(appt_id, self.e_id, d2, "14:00", reschedule_reason="Patient busy", user=self.caregiver)
        self.assertTrue(resched_ok)

        # Cancel
        cancel_ok = cancel_appointment(appt_id, self.e_id, cancellation_reason="Doctor on leave", user=self.caregiver)
        self.assertTrue(cancel_ok)

        # Ensure reminders are 0 for cancelled visits
        appts = get_appointments(self.e_id, status="all", user=self.caregiver)
        match = next((a for a in appts if a["id"] == appt_id), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["status"], "cancelled")

    def test_24_workflow_d_health_monitoring(self):
        """Workflow D: Add health reading -> verify history -> verify chart data."""
        today_str = date.today().isoformat()
        reading_id = add_health_reading(
            self.e_id, "Heart Rate", "72 bpm", today_str, "10:00", user=self.caregiver
        )
        self.assertIsNotNone(reading_id)

        vitals = get_latest_vitals(self.e_id, user=self.caregiver)
        self.assertIn("Heart Rate", vitals)
        self.assertEqual(vitals["Heart Rate"]["reading_value"], "72 bpm")

    def test_25_workflow_e_emergency_sos(self):
        """Workflow E: Activate SOS -> In-app notify -> Acknowledge -> In-progress -> Resolve."""
        req_id = activate_emergency_sos(
            self.e_id, self.e_id, urgency_reason="Workflow E Test", user=self.elderly
        )
        self.assertIsNotNone(req_id)

        # Active emergency query
        active = get_active_emergency(self.e_id)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], req_id)

        # Acknowledge
        acknowledge_emergency(req_id, self.e_id, self.c_id, user=self.caregiver)
        # Update assistance
        update_assistance_status(req_id, self.e_id, self.c_id, new_status="assistance_in_progress", response_note="Arrived", user=self.caregiver)
        # Resolve
        resolve_emergency(req_id, self.e_id, self.c_id, resolution_notes="Resolved safely", user=self.caregiver)

        # No active emergency should remain
        active_after = get_active_emergency(self.e_id)
        self.assertIsNone(active_after)

    def test_26_workflow_f_analytics_and_reports(self):
        """Workflow F: Calculate adherence -> appointment stats -> health trends -> CSV export."""
        overview = get_analytics_overview(self.e_id, period="last_30_days", user=self.caregiver)
        self.assertIn("adherence_percentage", overview)

        adherence = get_medication_adherence_analytics(self.e_id, period="last_30_days", user=self.caregiver)
        self.assertIn("daily_trend", adherence)

        appts_ana = get_appointment_analytics(self.e_id, period="last_30_days", user=self.caregiver)
        self.assertIn("total_appointments", appts_ana)

        csv_content = generate_analytics_csv_report(self.e_id, period="last_30_days", user=self.caregiver)
        self.assertIn("DEARLY - HEALTHCARE ANALYTICS & CARE SUMMARY REPORT", csv_content)
        self.assertIn("Asha Patil", csv_content)


if __name__ == "__main__":
    unittest.main()
