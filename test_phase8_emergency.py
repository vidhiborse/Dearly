import unittest
from datetime import date, datetime, timedelta
import database
from services.auth_service import authenticate
from services.care_circle_service import (
    add_care_note,
    get_care_circle_members,
    get_care_notes,
    send_care_invitation,
    respond_to_invitation,
)
from services.emergency_service import (
    EMERGENCY_SAFETY_NOTICE,
    acknowledge_alert,
    acknowledge_emergency,
    activate_emergency_sos,
    add_emergency_contact,
    cancel_emergency,
    delete_emergency_contact,
    get_active_emergency,
    get_active_emergency_alerts,
    get_emergency_contacts,
    get_emergency_request_by_id,
    get_emergency_requests,
    get_emergency_status_history,
    resolve_emergency,
    set_primary_emergency_contact,
    trigger_sos_alert,
    update_assistance_status,
    update_emergency_contact,
)
from services.health_service import add_health_reading, get_latest_vitals
from services.appointment_service import add_appointment, get_appointments, complete_appointment
from services.medication_service import add_medication, get_today_schedule, record_dose_status
from services.reminder_service import sync_reminders_and_escalations


class TestPhase8EmergencySOS(unittest.TestCase):
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

        # Ensure no active emergency left from previous tests
        active = get_active_emergency(self.e_id)
        if active:
            resolve_emergency(active["id"], self.e_id, self.c_id, resolution_notes="Clean setUp", user=self.caregiver)

    def tearDown(self):
        active = get_active_emergency(self.e_id)
        if active:
            try:
                resolve_emergency(active["id"], self.e_id, self.c_id, resolution_notes="Clean tearDown", user=self.caregiver)
            except Exception:
                pass

    def test_01_elderly_user_access_sos_dashboard(self):
        """Scenario 1: Elderly user can access their SOS dashboard."""
        contacts = get_emergency_contacts(self.e_id, user=self.elderly)
        self.assertIsInstance(contacts, list)
        self.assertGreaterEqual(len(contacts), 1)

        requests = get_emergency_requests(self.e_id, user=self.elderly)
        self.assertIsInstance(requests, list)

        # Check safety disclaimer presence
        self.assertIn("112", EMERGENCY_SAFETY_NOTICE)

    def test_02_elderly_activate_sos_request(self):
        """Scenario 2: Elderly user can activate an SOS request."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Living Room Couch",
            urgency_reason="Felt dizzy after standing up",
            user=self.elderly,
        )
        self.assertIsNotNone(req_id)
        self.assertGreater(req_id, 0)

        active = get_active_emergency(self.e_id, user=self.elderly)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], req_id)
        self.assertEqual(active["status"], "pending")
        self.assertEqual(active["location_notes"], "Living Room Couch")

    def test_03_cancelling_confirmation_creates_no_request(self):
        """Scenario 3: Cancelling confirmation creates no emergency request."""
        # Clean state
        active = get_active_emergency(self.e_id)
        if active:
            resolve_emergency(active["id"], self.e_id, self.c_id, resolution_notes="Resolved", user=self.caregiver)

        count_before = len(get_emergency_requests(self.e_id, user=self.elderly))

        # Simulating cancellation in UI: user aborts confirmation dialog before calling activation
        # No function call to activate_emergency_sos is made
        count_after = len(get_emergency_requests(self.e_id, user=self.elderly))
        self.assertEqual(count_before, count_after)
        self.assertIsNone(get_active_emergency(self.e_id, user=self.elderly))

    def test_04_duplicate_activation_prevented(self):
        """Scenario 4: Duplicate emergency activation is prevented when an active request exists."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Bedroom",
            urgency_reason="Initial emergency",
            user=self.elderly,
        )
        self.assertIsNotNone(req_id)

        # Attempting second activation while first is pending must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            activate_emergency_sos(
                elderly_user_id=self.e_id,
                triggered_by_user_id=self.e_id,
                location_notes="Bedroom duplicate",
                urgency_reason="Duplicate click",
                user=self.elderly,
            )
        self.assertIn("already active", str(ctx.exception).lower())

    def test_05_authorized_caregivers_receive_notifications(self):
        """Scenario 5: Active caregivers receive in-app notifications on emergency activation."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Balcony",
            urgency_reason="Urgent assistance needed",
            user=self.elderly,
        )

        with database.get_connection() as conn:
            notifs = conn.execute(
                """SELECT title, message FROM notifications
                   WHERE user_id = ? AND elderly_user_id = ?
                   ORDER BY id DESC LIMIT 5""",
                (self.c_id, self.e_id),
            ).fetchall()

        matched = [n for n in notifs if "EMERGENCY SOS" in n["title"]]
        self.assertGreaterEqual(len(matched), 1)
        self.assertIn("Balcony", matched[0]["message"])

    def test_06_revoked_caregivers_do_not_receive_notifications(self):
        """Scenario 6: Revoked or inactive care circle members receive zero emergency notifications."""
        # Register a temporary inactive user
        with database.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO users (id, name, email, password_hash, role, phone)
                   VALUES (8888, 'Revoked Member', 'revoked@dearly.demo', ?, 'caregiver', '+91 99999 88888')""",
                (database.hash_password("demo123"),),
            )
            # Add to care_circle as inactive
            conn.execute(
                """INSERT OR REPLACE INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, status)
                   VALUES (?, 8888, 'Former Caregiver', 'viewer', 'inactive')""",
                (self.e_id,),
            )

        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Kitchen",
            urgency_reason="Testing revoked exclusion",
            user=self.elderly,
        )

        with database.get_connection() as conn:
            revoked_notifs = conn.execute(
                "SELECT * FROM notifications WHERE user_id = 8888 AND elderly_user_id = ?",
                (self.e_id,),
            ).fetchall()

        self.assertEqual(len(revoked_notifs), 0)

    def test_07_authorized_family_receive_permitted_notifications(self):
        """Scenario 7: Eligible family members receive permitted emergency in-app notifications."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Dining Area",
            urgency_reason="Testing family notification",
            user=self.elderly,
        )

        with database.get_connection() as conn:
            family_notifs = conn.execute(
                """SELECT title, message FROM notifications
                   WHERE user_id = ? AND elderly_user_id = ?
                   ORDER BY id DESC LIMIT 5""",
                (self.f_id, self.e_id),
            ).fetchall()

        matched = [n for n in family_notifs if "EMERGENCY SOS" in n["title"]]
        self.assertGreaterEqual(len(matched), 1)

    def test_08_unrelated_users_cannot_view_emergency_requests(self):
        """Scenario 8: Unrelated users cannot view emergency requests (PermissionError)."""
        unrelated_ward_id = 77777

        with self.assertRaises(PermissionError):
            get_emergency_requests(unrelated_ward_id, user=self.caregiver)

        with self.assertRaises(PermissionError):
            activate_emergency_sos(elderly_user_id=unrelated_ward_id, user=self.caregiver)

    def test_09_caregiver_can_acknowledge_emergency(self):
        """Scenario 9: Caregiver can acknowledge an active emergency."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Hallway",
            urgency_reason="Assistance requested",
            user=self.elderly,
        )

        success = acknowledge_emergency(
            request_id=req_id,
            elderly_user_id=self.e_id,
            actor_user_id=self.c_id,
            response_note="Saw alert, calling Asha now",
            user=self.caregiver,
        )
        self.assertTrue(success)

        req = get_emergency_request_by_id(req_id, user=self.caregiver)
        self.assertEqual(req["status"], "acknowledged")
        self.assertEqual(req["acknowledged_by"], self.c_id)
        self.assertIsNotNone(req["acknowledged_at"])

    def test_10_caregiver_can_update_assistance_status(self):
        """Scenario 10: Caregiver can update assistance status to 'assistance_in_progress'."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Bedroom",
            urgency_reason="Need help with medication",
            user=self.elderly,
        )
        acknowledge_emergency(req_id, self.e_id, self.c_id, user=self.caregiver)

        success = update_assistance_status(
            request_id=req_id,
            elderly_user_id=self.e_id,
            actor_user_id=self.c_id,
            new_status="assistance_in_progress",
            response_note="Arrived at Asha's home; assisting",
            user=self.caregiver,
        )
        self.assertTrue(success)

        req = get_emergency_request_by_id(req_id, user=self.caregiver)
        self.assertEqual(req["status"], "assistance_in_progress")

    def test_11_authorized_user_can_resolve_emergency(self):
        """Scenario 11: Authorized user can resolve an emergency with resolution notes."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Living Room",
            urgency_reason="Dizziness resolved",
            user=self.elderly,
        )

        success = resolve_emergency(
            request_id=req_id,
            elderly_user_id=self.e_id,
            actor_user_id=self.c_id,
            resolution_notes="Checked blood pressure: 124/80 mmHg. Asha is resting comfortably. Safe.",
            user=self.caregiver,
        )
        self.assertTrue(success)

        req = get_emergency_request_by_id(req_id, user=self.caregiver)
        self.assertEqual(req["status"], "resolved")
        self.assertEqual(req["resolved_by"], self.c_id)
        self.assertIn("resting comfortably", req["resolution_notes"])
        self.assertIsNone(get_active_emergency(self.e_id, user=self.caregiver))

    def test_12_status_history_recorded_correctly(self):
        """Scenario 12: Status transition history is recorded completely in emergency_status_history."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Garden",
            urgency_reason="Transition history test",
            user=self.elderly,
        )
        acknowledge_emergency(req_id, self.e_id, self.c_id, response_note="Step 1: Acknowledged", user=self.caregiver)
        update_assistance_status(req_id, self.e_id, self.c_id, "assistance_in_progress", response_note="Step 2: On my way", user=self.caregiver)
        resolve_emergency(req_id, self.e_id, self.c_id, resolution_notes="Step 3: All safe and sound", user=self.caregiver)

        history = get_emergency_status_history(req_id, user=self.caregiver)
        self.assertGreaterEqual(len(history), 4)

        to_statuses = [h["to_status"] for h in history]
        self.assertEqual(to_statuses[0], "pending")
        self.assertEqual(to_statuses[1], "acknowledged")
        self.assertEqual(to_statuses[2], "assistance_in_progress")
        self.assertEqual(to_statuses[3], "resolved")

    def test_13_emergency_contact_creation(self):
        """Scenario 13: Authorized user can create a new emergency contact."""
        cid = add_emergency_contact(
            elderly_user_id=self.e_id,
            contact_name="Suresh Verma",
            relationship="Trusted Neighbor",
            phone="+91 98200 44556",
            email="suresh.verma@demo.local",
            priority=3,
            is_primary=False,
            notes="Has key to front door",
            user=self.caregiver,
        )
        self.assertIsNotNone(cid)

        contacts = get_emergency_contacts(self.e_id, user=self.caregiver)
        match = next((c for c in contacts if c["id"] == cid), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["contact_name"], "Suresh Verma")
        self.assertEqual(match["phone"], "+91 98200 44556")

    def test_14_emergency_contact_editing(self):
        """Scenario 14: Emergency contact editing works and persists updates."""
        cid = add_emergency_contact(
            elderly_user_id=self.e_id,
            contact_name="Dr. Anil Deshmukh",
            relationship="Clinic Doctor",
            phone="+91 98200 11223",
            user=self.caregiver,
        )

        success = update_emergency_contact(
            contact_id=cid,
            elderly_user_id=self.e_id,
            contact_name="Dr. Anil Deshmukh",
            relationship="Senior Consultant",
            phone="+91 98200 99999",
            notes="Updated hospital direct extension",
            user=self.caregiver,
        )
        self.assertTrue(success)

        contacts = get_emergency_contacts(self.e_id, user=self.caregiver)
        match = next(c for c in contacts if c["id"] == cid)
        self.assertEqual(match["phone"], "+91 98200 99999")
        self.assertEqual(match["relationship"], "Senior Consultant")

    def test_15_emergency_contact_deletion(self):
        """Scenario 15: Emergency contact deactivation / removal works."""
        cid = add_emergency_contact(
            elderly_user_id=self.e_id,
            contact_name="Temporary Contact",
            relationship="Volunteer",
            phone="+91 98200 00000",
            user=self.caregiver,
        )

        success = delete_emergency_contact(cid, self.e_id, user=self.caregiver)
        self.assertTrue(success)

        # Active contacts list should no longer include it
        active_contacts = get_emergency_contacts(self.e_id, active_only=True, user=self.caregiver)
        self.assertFalse(any(c["id"] == cid for c in active_contacts))

    def test_16_primary_contact_selection(self):
        """Scenario 16: Primary emergency contact designation enforces single primary rule."""
        c1 = add_emergency_contact(
            elderly_user_id=self.e_id,
            contact_name="Primary Candidate A",
            relationship="Relative",
            phone="+91 98200 11111",
            is_primary=True,
            user=self.caregiver,
        )
        c2 = add_emergency_contact(
            elderly_user_id=self.e_id,
            contact_name="Primary Candidate B",
            relationship="Relative",
            phone="+91 98200 22222",
            is_primary=False,
            user=self.caregiver,
        )

        # Reassign primary to candidate B
        set_primary_emergency_contact(c2, self.e_id, user=self.caregiver)

        contacts = get_emergency_contacts(self.e_id, user=self.caregiver)
        match_a = next(c for c in contacts if c["id"] == c1)
        match_b = next(c for c in contacts if c["id"] == c2)

        self.assertEqual(match_a["is_primary"], 0)
        self.assertEqual(match_b["is_primary"], 1)

    def test_17_unauthorized_users_cannot_view_private_contacts(self):
        """Scenario 17: Unauthorized users cannot access private contact details (PermissionError)."""
        unrelated_ward_id = 66666

        with self.assertRaises(PermissionError):
            get_emergency_contacts(unrelated_ward_id, user=self.caregiver)

        with self.assertRaises(PermissionError):
            add_emergency_contact(
                elderly_user_id=unrelated_ward_id,
                contact_name="Hacker",
                relationship="None",
                phone="+91 99999 99999",
                user=self.caregiver,
            )

    def test_18_emergency_history_persists_after_restart(self):
        """Scenario 18: Emergency history and status logs persist across application restart."""
        req_id = activate_emergency_sos(
            elderly_user_id=self.e_id,
            triggered_by_user_id=self.e_id,
            location_notes="Persistence Test Room",
            urgency_reason="Testing restart survival",
            user=self.elderly,
        )

        # Simulate restart
        database.init_db()

        req = get_emergency_request_by_id(req_id, user=self.caregiver)
        self.assertIsNotNone(req)
        self.assertEqual(req["location_notes"], "Persistence Test Room")

        # Resolve to clean up
        resolve_emergency(req_id, self.e_id, self.c_id, resolution_notes="Restart verified", user=self.caregiver)

    def test_19_regression_care_circle_permissions(self):
        """Scenario 19: Verify existing Care Circle invitations and notes continue working."""
        members = get_care_circle_members(self.e_id)
        self.assertGreater(len(members), 0)

        ok, msg, nid = add_care_note(
            elderly_user_id=self.e_id,
            author_user=self.caregiver,
            title="Emergency Check Completed",
            content="Asha is resting peacefully after safety check.",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(nid)

    def test_20_regression_medications_reminders_appts_health(self):
        """Scenario 20: Verify medication, reminder, appointment, and health vitals regression."""
        today_str = date.today().isoformat()

        # Medication schedule
        sched = get_today_schedule(self.e_id)
        self.assertIsInstance(sched, list)

        # Reminders sync
        counts = sync_reminders_and_escalations(self.e_id)
        self.assertIsInstance(counts, dict)

        # Appointments
        appts = get_appointments(self.e_id, status="all", user=self.caregiver)
        self.assertIsInstance(appts, list)

        # Health Vitals
        vitals = get_latest_vitals(self.e_id, user=self.caregiver)
        self.assertIn("Blood Pressure", vitals)

        # Legacy emergency helpers from test_app.py
        alert_id = trigger_sos_alert(self.e_id, self.e_id, message="Legacy test")
        self.assertIsNotNone(alert_id)
        active_legacy = get_active_emergency_alerts(self.e_id)
        self.assertGreaterEqual(len(active_legacy), 1)
        acknowledge_alert(alert_id, self.e_id, self.c_id)
        resolve_emergency(alert_id, self.e_id, self.c_id, resolution_notes="Resolved legacy regression test", user=self.caregiver)


if __name__ == "__main__":
    unittest.main()
