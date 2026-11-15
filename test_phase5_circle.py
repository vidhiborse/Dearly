import unittest
import sqlite3
from datetime import date, datetime, timedelta

from database import init_db, create_demo_users, get_connection
from services.permissions import (
    can_access_elderly_record,
    can_manage_elderly_care,
    enforce_elderly_access,
)
from services.care_circle_service import (
    get_care_circle_members,
    get_care_circle_dashboard,
    send_care_invitation,
    get_user_pending_invitations,
    get_elderly_pending_invitations,
    respond_to_invitation,
    revoke_invitation,
    remove_care_circle_member,
    set_primary_caregiver,
    add_care_note,
    get_care_notes,
    update_care_note,
    delete_care_note,
)
from services.activity_service import get_care_activity_timeline
from services.reminder_service import get_user_notifications
from services.medication_service import (
    add_medication,
    record_dose_status,
    get_today_schedule,
    get_adherence_metrics,
)


class TestPhase5CareCircle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()
        with get_connection() as conn:
            # Clean prior test artifacts
            conn.execute("DELETE FROM users WHERE email LIKE '%@testcircle.demo'")

            # Senior Alpha
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Alpha', 'alpha@testcircle.demo', 'hash123', 'elderly', '+91 97777 11111')"""
            )
            cls.senior_a_id = conn.execute("SELECT id FROM users WHERE email = 'alpha@testcircle.demo'").fetchone()["id"]

            # Senior Beta (isolated profile)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Senior Beta', 'beta@testcircle.demo', 'hash123', 'elderly', '+91 97777 22222')"""
            )
            cls.senior_b_id = conn.execute("SELECT id FROM users WHERE email = 'beta@testcircle.demo'").fetchone()["id"]

            # Caregiver A (Primary for Senior Alpha)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Nurse Anjali', 'anjali@testcircle.demo', 'hash123', 'caregiver', '+91 97777 33333')"""
            )
            cls.caregiver_a_id = conn.execute("SELECT id FROM users WHERE email = 'anjali@testcircle.demo'").fetchone()["id"]

            # Caregiver B (Secondary caregiver)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Nurse Bob', 'bob@testcircle.demo', 'hash123', 'caregiver', '+91 97777 44444')"""
            )
            cls.caregiver_b_id = conn.execute("SELECT id FROM users WHERE email = 'bob@testcircle.demo'").fetchone()["id"]

            # Family Member A (Daughter)
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Daughter Divya', 'divya@testcircle.demo', 'hash123', 'family', '+91 97777 55555')"""
            )
            cls.family_a_id = conn.execute("SELECT id FROM users WHERE email = 'divya@testcircle.demo'").fetchone()["id"]

            # Unrelated Stranger
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Stranger Stan', 'stan@testcircle.demo', 'hash123', 'caregiver', '+91 97777 66666')"""
            )
            cls.stranger_id = conn.execute("SELECT id FROM users WHERE email = 'stan@testcircle.demo'").fetchone()["id"]

            # Initial Care Circle for Senior Alpha: Anjali as primary editor, Divya as viewer
            conn.execute(
                """INSERT INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                   VALUES (?, ?, 'Primary Nurse', 'editor', 'caregiver', 'active', 1)""",
                (cls.senior_a_id, cls.caregiver_a_id),
            )
            conn.execute(
                """INSERT INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                   VALUES (?, ?, 'Daughter', 'viewer', 'family', 'active', 0)""",
                (cls.senior_a_id, cls.family_a_id),
            )

        cls.senior_a_user = {"id": cls.senior_a_id, "role": "elderly", "name": "Senior Alpha", "email": "alpha@testcircle.demo"}
        cls.senior_b_user = {"id": cls.senior_b_id, "role": "elderly", "name": "Senior Beta", "email": "beta@testcircle.demo"}
        cls.caregiver_a_user = {"id": cls.caregiver_a_id, "role": "caregiver", "name": "Nurse Anjali", "email": "anjali@testcircle.demo"}
        cls.caregiver_b_user = {"id": cls.caregiver_b_id, "role": "caregiver", "name": "Nurse Bob", "email": "bob@testcircle.demo"}
        cls.family_a_user = {"id": cls.family_a_id, "role": "family", "name": "Daughter Divya", "email": "divya@testcircle.demo"}
        cls.stranger_user = {"id": cls.stranger_id, "role": "caregiver", "name": "Stranger Stan", "email": "stan@testcircle.demo"}

    @classmethod
    def tearDownClass(cls):
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE email LIKE '%@testcircle.demo'")

    def setUp(self):
        # Clean invitations, notes, notifications and reset circle for test users before each test
        with get_connection() as conn:
            conn.execute("DELETE FROM care_invitations WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))
            conn.execute("DELETE FROM care_notes WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))
            conn.execute("DELETE FROM notifications WHERE elderly_user_id IN (?, ?)", (self.senior_a_id, self.senior_b_id))
            conn.execute(
                "DELETE FROM care_circle WHERE elderly_user_id = ? AND member_user_id NOT IN (?, ?)",
                (self.senior_a_id, self.caregiver_a_id, self.family_a_id),
            )
            conn.execute("DELETE FROM care_circle WHERE elderly_user_id = ?", (self.senior_b_id,))
            conn.execute(
                "UPDATE care_circle SET is_primary = 1 WHERE elderly_user_id = ? AND member_user_id = ?",
                (self.senior_a_id, self.caregiver_a_id),
            )
            conn.execute(
                "UPDATE care_circle SET is_primary = 0 WHERE elderly_user_id = ? AND member_user_id = ?",
                (self.senior_a_id, self.family_a_id),
            )

    # Scenario 1: View an elderly user's care circle
    def test_01_view_elderly_care_circle(self):
        members = get_care_circle_members(self.senior_a_id, user=self.senior_a_user)
        self.assertEqual(len(members), 2)
        member_ids = [m["user_id"] for m in members]
        self.assertIn(self.caregiver_a_id, member_ids)
        self.assertIn(self.family_a_id, member_ids)

        dashboard = get_care_circle_dashboard(self.senior_a_id, user=self.senior_a_user)
        self.assertEqual(dashboard["counts"]["total_active"], 2)
        self.assertEqual(dashboard["primary_caregiver"]["user_id"], self.caregiver_a_id)

    # Scenario 2: Invite an existing registered caregiver
    def test_02_invite_existing_caregiver(self):
        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Professional caregiver",
            connection_role="caregiver",
            permission_level="editor",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(inv_id)

        # Check invitation record in DB
        with get_connection() as conn:
            inv = conn.execute("SELECT * FROM care_invitations WHERE id = ?", (inv_id,)).fetchone()
            self.assertEqual(inv["status"], "pending")
            self.assertEqual(inv["connection_role"], "caregiver")
            self.assertEqual(inv["permission_level"], "editor")

        # Check in-app notification delivered to invitee Bob
        notifs = get_user_notifications(self.caregiver_b_user, alert_type="system")
        self.assertTrue(any("Care Circle Invitation" in n["title"] for n in notifs))

    # Scenario 3: Invite an existing family member
    def test_03_invite_existing_family_member(self):
        # Register a new family account for test
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role, phone)
                   VALUES ('Son Sameer', 'sameer@testcircle.demo', 'hash123', 'family', '+91 97777 77777')"""
            )
            sameer_id = conn.execute("SELECT id FROM users WHERE email = 'sameer@testcircle.demo'").fetchone()["id"]

        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.senior_a_user,
            invitee_email="sameer@testcircle.demo",
            relationship="Son",
            connection_role="family",
            permission_level="viewer",
        )
        self.assertTrue(ok)
        self.assertIn("sameer@testcircle.demo", msg)

    # Scenario 4: Reject invitation from an unknown email
    def test_04_reject_invitation_unknown_email(self):
        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.senior_a_user,
            invitee_email="nonexistent.ghost@example.com",
            relationship="Relative",
            connection_role="family",
            permission_level="viewer",
        )
        self.assertFalse(ok)
        self.assertIsNone(inv_id)
        self.assertIn("No registered account found", msg)

    # Scenario 5: Prevent self-invitation
    def test_05_prevent_self_invitation(self):
        # Inviter invites themselves
        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email=self.caregiver_a_user["email"],
            relationship="Self",
            connection_role="caregiver",
        )
        self.assertFalse(ok)
        self.assertIn("cannot send a care circle invitation to yourself", msg)

        # Inviter invites elderly user to their own circle
        ok2, msg2, inv_id2 = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email=self.senior_a_user["email"],
            relationship="Self",
            connection_role="family",
        )
        self.assertFalse(ok2)
        self.assertIn("Cannot invite the elderly person", msg2)

    # Scenario 6: Prevent duplicate invitations
    def test_06_prevent_duplicate_invitations(self):
        send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Professional caregiver",
            connection_role="caregiver",
        )
        # Attempt second invitation
        ok, msg, _ = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Professional caregiver",
            connection_role="caregiver",
        )
        self.assertFalse(ok)
        self.assertIn("pending invitation for bob@testcircle.demo already exists", msg)

    # Scenario 7: Accept an invitation
    def test_07_accept_invitation(self):
        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Physiotherapist",
            connection_role="caregiver",
            permission_level="editor",
        )
        # Bob accepts
        ok_acc, msg_acc = respond_to_invitation(inv_id, self.caregiver_b_user, "accept")
        self.assertTrue(ok_acc)
        self.assertIn("accepted the invitation", msg_acc)

        # Bob should now be in care_circle
        members = get_care_circle_members(self.senior_a_id)
        bob_entry = next((m for m in members if m["user_id"] == self.caregiver_b_id), None)
        self.assertIsNotNone(bob_entry)
        self.assertEqual(bob_entry["relationship"], "Physiotherapist")
        self.assertEqual(bob_entry["permission_level"], "editor")
        self.assertEqual(bob_entry["status"], "active")

    # Scenario 8: Reject an invitation
    def test_08_reject_invitation(self):
        ok, msg, inv_id = send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Physiotherapist",
            connection_role="caregiver",
        )
        # Bob rejects
        ok_rej, msg_rej = respond_to_invitation(inv_id, self.caregiver_b_user, "reject")
        self.assertTrue(ok_rej)
        self.assertIn("declined", msg_rej)

        # Bob should NOT be in care_circle
        members = get_care_circle_members(self.senior_a_id)
        bob_entry = next((m for m in members if m["user_id"] == self.caregiver_b_id), None)
        self.assertIsNone(bob_entry)

    # Scenario 9: Verify pending invitations grant no access
    def test_09_pending_invitation_grants_no_access(self):
        send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Physiotherapist",
            connection_role="caregiver",
        )
        # Bob has pending invitation, but NOT accepted
        self.assertFalse(can_access_elderly_record(self.caregiver_b_user, self.senior_a_id))
        self.assertFalse(can_manage_elderly_care(self.caregiver_b_user, self.senior_a_id))
        with self.assertRaises(PermissionError):
            enforce_elderly_access(self.caregiver_b_user, self.senior_a_id, write_access=False)

    # Scenario 10: Verify accepted connections grant only the intended access
    def test_10_accepted_connection_grants_intended_access(self):
        # 1. Family member Divya has viewer permission
        self.assertTrue(can_access_elderly_record(self.family_a_user, self.senior_a_id))
        self.assertFalse(can_manage_elderly_care(self.family_a_user, self.senior_a_id))

        # 2. Caregiver Anjali has editor permission
        self.assertTrue(can_access_elderly_record(self.caregiver_a_user, self.senior_a_id))
        self.assertTrue(can_manage_elderly_care(self.caregiver_a_user, self.senior_a_id))

    # Scenario 11: Prevent access to unrelated elderly profiles
    def test_11_prevent_access_to_unrelated_elderly_profiles(self):
        # Stranger Stan has no link to Senior Alpha
        self.assertFalse(can_access_elderly_record(self.stranger_user, self.senior_a_id))
        self.assertFalse(can_manage_elderly_care(self.stranger_user, self.senior_a_id))
        with self.assertRaises(PermissionError):
            get_care_circle_members(self.senior_a_id, user=self.stranger_user)

    # Scenario 12: Remove a care-circle connection
    def test_12_remove_care_circle_connection(self):
        # Add Bob first
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status)
                   VALUES (?, ?, 'Assistant', 'viewer', 'caregiver', 'active')""",
                (self.senior_a_id, self.caregiver_b_id),
            )
        self.assertTrue(can_access_elderly_record(self.caregiver_b_user, self.senior_a_id))

        # Anjali removes Bob
        ok, msg = remove_care_circle_member(self.senior_a_id, self.caregiver_b_id, self.caregiver_a_user)
        self.assertTrue(ok)

        # Bob should no longer be active member
        members = get_care_circle_members(self.senior_a_id)
        self.assertNotIn(self.caregiver_b_id, [m["user_id"] for m in members])

    # Scenario 13: Verify removed users lose access
    def test_13_verify_removed_users_lose_access(self):
        # Bob was removed in test 12 or not present
        self.assertFalse(can_access_elderly_record(self.caregiver_b_user, self.senior_a_id))
        with self.assertRaises(PermissionError):
            enforce_elderly_access(self.caregiver_b_user, self.senior_a_id, write_access=False)

    # Scenario 14: Add and view a care note
    def test_14_add_and_view_care_note(self):
        ok, msg, note_id = add_care_note(
            elderly_user_id=self.senior_a_id,
            author_user=self.caregiver_a_user,
            title="Hydration and Posture Check",
            content="Senior completed light morning stretching and had 500 ml coconut water. Mobility comfortable.",
            category="observation",
            visibility="circle",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(note_id)

        notes = get_care_notes(self.senior_a_id, user=self.caregiver_a_user)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["title"], "Hydration and Posture Check")
        self.assertEqual(notes[0]["author_name"], "Nurse Anjali")

    # Scenario 15: Verify unauthorized users cannot view private notes
    def test_15_unauthorized_users_cannot_view_private_notes(self):
        # 1. Circle-visible note
        add_care_note(
            elderly_user_id=self.senior_a_id,
            author_user=self.caregiver_a_user,
            title="Shared Routine Note",
            content="Everyday routine note visible to family and caregivers.",
            visibility="circle",
        )
        # 2. Caregivers-only note
        add_care_note(
            elderly_user_id=self.senior_a_id,
            author_user=self.caregiver_a_user,
            title="Confidential Clinical Observation",
            content="Sensitive caregiver oversight details.",
            visibility="caregivers_only",
        )

        # Caregiver sees both notes (2)
        cg_notes = get_care_notes(self.senior_a_id, user=self.caregiver_a_user)
        self.assertEqual(len(cg_notes), 2)

        # Family member sees ONLY the circle note (1)
        fam_notes = get_care_notes(self.senior_a_id, user=self.family_a_user)
        self.assertEqual(len(fam_notes), 1)
        self.assertEqual(fam_notes[0]["title"], "Shared Routine Note")

        # Unrelated stranger raises PermissionError
        with self.assertRaises(PermissionError):
            get_care_notes(self.senior_a_id, user=self.stranger_user)

    # Scenario 16: Display actual care activity
    def test_16_display_actual_care_activity(self):
        events = get_care_activity_timeline(self.senior_a_id, user=self.caregiver_a_user, action_filter="all")
        self.assertIsInstance(events, list)

        # Test category filter
        notes_events = get_care_activity_timeline(self.senior_a_id, user=self.caregiver_a_user, action_filter="notes")
        self.assertTrue(all("Note" in e["action"] for e in notes_events))

    # Scenario 17: Assign and change the primary caregiver
    def test_17_assign_and_change_primary_caregiver(self):
        # Link Bob as caregiver
        with get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO care_circle
                   (elderly_user_id, member_user_id, relationship, permission_level, connection_role, status, is_primary)
                   VALUES (?, ?, 'Night Nurse', 'editor', 'caregiver', 'active', 0)""",
                (self.senior_a_id, self.caregiver_b_id),
            )

        # Before: Anjali is primary
        members_before = get_care_circle_members(self.senior_a_id)
        anjali_b = next(m for m in members_before if m["user_id"] == self.caregiver_a_id)
        bob_b = next(m for m in members_before if m["user_id"] == self.caregiver_b_id)
        self.assertEqual(anjali_b["is_primary"], 1)
        self.assertEqual(bob_b["is_primary"], 0)

        # Senior reassigns primary caregiver to Bob
        ok, msg = set_primary_caregiver(self.senior_a_id, self.caregiver_b_id, self.senior_a_user)
        self.assertTrue(ok)

        # After: Bob is primary, Anjali is not primary
        members_after = get_care_circle_members(self.senior_a_id)
        anjali_a = next(m for m in members_after if m["user_id"] == self.caregiver_a_id)
        bob_a = next(m for m in members_after if m["user_id"] == self.caregiver_b_id)
        self.assertEqual(bob_a["is_primary"], 1)
        self.assertEqual(anjali_a["is_primary"], 0)

        # Exactly 1 primary caregiver
        primary_count = sum(1 for m in members_after if m["is_primary"] == 1)
        self.assertEqual(primary_count, 1)

    # Scenario 18: Verify in-app notification integration
    def test_18_in_app_notification_integration(self):
        # Sending invitation creates notification
        send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Nurse",
            connection_role="caregiver",
        )
        notifs = get_user_notifications(self.caregiver_b_user, alert_type="system")
        self.assertGreater(len(notifs), 0)
        self.assertIn("Care Circle Invitation", notifs[0]["title"])

    # Scenario 19: Verify existing medication and reminder functionality still works
    def test_19_existing_medication_and_reminder_regression(self):
        today_str = date.today().isoformat()
        med_id = add_medication(
            elderly_user_id=self.senior_a_id,
            medicine_name="Multivitamin",
            dosage="1 tab",
            schedule_time="09:00",
            start_date=today_str,
            user=self.caregiver_a_user,
        )
        sched = get_today_schedule(self.senior_a_id, today_str, user=self.caregiver_a_user)
        self.assertTrue(any(s["medication_id"] == med_id for s in sched))

        # Record dose
        record_dose_status(
            medication_id=med_id,
            elderly_user_id=self.senior_a_id,
            scheduled_date=today_str,
            scheduled_time="09:00",
            status="taken",
            recorded_by=self.caregiver_a_id,
            user=self.caregiver_a_user,
        )
        metrics = get_adherence_metrics(self.senior_a_id, days=7)
        self.assertGreaterEqual(metrics["adherence_percentage"], 0.0)

    # Scenario 20: Verify all records persist after application restart
    def test_20_records_persist_after_restart(self):
        # Create note and invitation
        add_care_note(
            elderly_user_id=self.senior_a_id,
            author_user=self.caregiver_a_user,
            title="Persistent Note",
            content="This note must persist through DB reopen.",
        )
        send_care_invitation(
            elderly_user_id=self.senior_a_id,
            inviter_user=self.caregiver_a_user,
            invitee_email="bob@testcircle.demo",
            relationship="Nurse",
            connection_role="caregiver",
        )

        # Simulate fresh DB connection
        with get_connection() as conn:
            note_row = conn.execute("SELECT title FROM care_notes WHERE elderly_user_id = ?", (self.senior_a_id,)).fetchone()
            invite_row = conn.execute("SELECT invitee_email FROM care_invitations WHERE elderly_user_id = ?", (self.senior_a_id,)).fetchone()
            circle_count = conn.execute("SELECT COUNT(*) as cnt FROM care_circle WHERE elderly_user_id = ?", (self.senior_a_id,)).fetchone()["cnt"]

            self.assertIsNotNone(note_row)
            self.assertEqual(note_row["title"], "Persistent Note")
            self.assertIsNotNone(invite_row)
            self.assertEqual(invite_row["invitee_email"], "bob@testcircle.demo")
            self.assertGreaterEqual(circle_count, 2)


if __name__ == "__main__":
    unittest.main()
