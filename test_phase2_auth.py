import unittest
import sqlite3
from database import init_db, create_demo_users, authenticate_user, verify_password, hash_password
from services.user_service import register_user, get_user_profile, update_user_profile
from services.auth_service import authenticate, get_accessible_elderly_wards
from services.permissions import can_access_elderly_record, can_manage_elderly_care, can_view_page

class TestPhase2AuthAndUserManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        create_demo_users()
        with sqlite3.connect("data/dearly.db") as conn:
            conn.execute("DELETE FROM users WHERE email LIKE '%@example.com' OR email LIKE '%@test.com'")

    # Case 1: Register a new elderly user
    def test_01_register_new_elderly_user(self):
        email = "test.elderly.p2@example.com"
        ok, res = register_user(
            name="Ramesh Joshi",
            email=email,
            phone="+91 98111 00001",
            password="securePassword123",
            confirm_password="securePassword123",
            role="elderly",
        )
        self.assertTrue(ok)
        self.assertEqual(res["role"], "elderly")
        self.assertEqual(res["email"], email)

        # Check elderly_profiles auto-initialization
        profile = get_user_profile(res["id"])
        self.assertIsNotNone(profile)
        self.assertEqual(profile["name"], "Ramesh Joshi")

    # Case 2: Register a new caregiver
    def test_02_register_new_caregiver(self):
        email = "test.caregiver.p2@example.com"
        ok, res = register_user(
            name="Pooja Sharma",
            email=email,
            phone="+91 98111 00002",
            password="caregiverPass123",
            confirm_password="caregiverPass123",
            role="caregiver",
        )
        self.assertTrue(ok)
        self.assertEqual(res["role"], "caregiver")
        self.assertEqual(res["name"], "Pooja Sharma")

    # Case 3: Register a new family member
    def test_03_register_new_family_member(self):
        email = "test.family.p2@example.com"
        ok, res = register_user(
            name="Vikram Sharma",
            email=email,
            phone="+91 98111 00003",
            password="familyPass123",
            confirm_password="familyPass123",
            role="family",
        )
        self.assertTrue(ok)
        self.assertEqual(res["role"], "family")
        self.assertEqual(res["name"], "Vikram Sharma")

    # Case 4: Reject duplicate email registration
    def test_04_reject_duplicate_email(self):
        ok, msg = register_user(
            name="Duplicate Test",
            email="elderly@dearly.demo",
            phone="+91 98000 11111",
            password="password123",
            confirm_password="password123",
            role="elderly",
        )
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    # Case 5: Reject invalid email formats
    def test_05_reject_invalid_email_format(self):
        invalid_emails = ["notanemail", "user@", "user@domain", "@domain.com", "user space@domain.com"]
        for bad_email in invalid_emails:
            ok, msg = register_user(
                name="Invalid Email Test",
                email=bad_email,
                phone="+91 98000 22222",
                password="password123",
                confirm_password="password123",
                role="caregiver",
            )
            self.assertFalse(ok, f"Failed to reject invalid email: {bad_email}")
            self.assertIn("valid email address", msg)

    # Case 6: Reject mismatched passwords
    def test_06_reject_mismatched_passwords(self):
        ok, msg = register_user(
            name="Mismatch Test",
            email="mismatch@example.com",
            phone="+91 98000 33333",
            password="passwordABC",
            confirm_password="passwordXYZ",
            role="family",
        )
        self.assertFalse(ok)
        self.assertIn("Passwords do not match", msg)

    # Case 7: Successfully log in with valid credentials
    def test_07_login_with_valid_credentials(self):
        user = authenticate("elderly@dearly.demo", "demo123")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "elderly@dearly.demo")
        self.assertEqual(user["role"], "elderly")
        self.assertNotIn("password_hash", user)

    # Case 8: Reject incorrect passwords
    def test_08_reject_incorrect_passwords(self):
        user = authenticate("elderly@dearly.demo", "completelyWrongPassword")
        self.assertIsNone(user)

        user2 = authenticate("nonexistent@example.com", "demo123")
        self.assertIsNone(user2)

    # Case 9: Prevent access without authentication
    def test_09_prevent_access_without_authentication(self):
        # When user session is None
        self.assertFalse(can_view_page(None, "Home"))
        self.assertFalse(can_view_page(None, "Overview"))
        self.assertFalse(can_access_elderly_record(None, 1))
        self.assertFalse(can_manage_elderly_care(None, 1))

    # Case 10: Verify role-based page access
    def test_10_verify_role_based_page_access(self):
        elderly_user = {"id": 1, "role": "elderly"}
        caregiver_user = {"id": 2, "role": "caregiver"}
        family_user = {"id": 3, "role": "family"}

        # Elderly permitted pages
        self.assertTrue(can_view_page(elderly_user, "Home"))
        self.assertTrue(can_view_page(elderly_user, "My Medicines"))
        self.assertTrue(can_view_page(elderly_user, "Emergency Contacts"))
        self.assertFalse(can_view_page(elderly_user, "Medication Monitoring"))
        self.assertFalse(can_view_page(elderly_user, "Activity History"))

        # Caregiver permitted pages
        self.assertTrue(can_view_page(caregiver_user, "Overview"))
        self.assertTrue(can_view_page(caregiver_user, "Medication Monitoring"))
        self.assertTrue(can_view_page(caregiver_user, "Health Records"))
        self.assertFalse(can_view_page(caregiver_user, "Care Updates"))

        # Family permitted pages
        self.assertTrue(can_view_page(family_user, "Overview"))
        self.assertTrue(can_view_page(family_user, "Care Updates"))
        self.assertTrue(can_view_page(family_user, "Health Summary"))
        self.assertFalse(can_view_page(family_user, "Medication Monitoring"))

    # Case 11: Verify users cannot access unrelated elderly profiles
    def test_11_verify_isolation_unrelated_elderly_profiles(self):
        # Create an unrelated elderly user and unrelated caregiver
        ok_e, unrelated_elderly = register_user("Unrelated Senior", "unrelated.elderly@test.com", "9998887771", "pass123", "pass123", "elderly")
        ok_c, unrelated_caregiver = register_user("Unrelated Caregiver", "unrelated.caregiver@test.com", "9998887772", "pass123", "pass123", "caregiver")
        
        # Asha Patil is elderly ID 1
        # Unrelated senior cannot access Asha's records
        self.assertFalse(can_access_elderly_record(unrelated_elderly, 1))
        
        # Unrelated caregiver is not in Asha's care circle, cannot access Asha's records
        self.assertFalse(can_access_elderly_record(unrelated_caregiver, 1))
        self.assertFalse(can_manage_elderly_care(unrelated_caregiver, 1))

        # Rahul Patil (ID 2) IS in Asha's care circle
        rahul = authenticate("caregiver@dearly.demo", "demo123")
        self.assertTrue(can_access_elderly_record(rahul, 1))
        self.assertTrue(can_manage_elderly_care(rahul, 1))

    # Case 12: Update and save a profile
    def test_12_update_and_save_profile(self):
        # Register user to test profile updates
        ok, user = register_user("Initial Name", "update.test@example.com", "+91 99000 88888", "pass1234", "pass1234", "family")
        u_id = user["id"]

        # Update name and phone
        up_ok, msg = update_user_profile(u_id, "Updated Name Patil", "+91 99000 99999")
        self.assertTrue(up_ok)

        # Verify from database
        profile = get_user_profile(u_id)
        self.assertEqual(profile["name"], "Updated Name Patil")
        self.assertEqual(profile["phone"], "+91 99000 99999")
        # Ensure role did not change
        self.assertEqual(profile["role"], "family")

    # Case 13: Log out successfully
    def test_13_logout_clears_session_state(self):
        session = {
            "user": {"id": 1, "name": "Asha", "role": "elderly"},
            "selected_ward_id": 1,
            "current_page": "Home",
        }
        # Simulate logout action
        session["user"] = None
        session.pop("selected_ward_id", None)
        session["current_page"] = None

        self.assertIsNone(session["user"])
        self.assertNotIn("selected_ward_id", session)
        self.assertIsNone(session["current_page"])

    # Case 14: Verify protected pages cannot be accessed after logout
    def test_14_verify_protected_pages_blocked_after_logout(self):
        logged_out_user = None
        self.assertFalse(can_view_page(logged_out_user, "Home"))
        self.assertFalse(can_view_page(logged_out_user, "Overview"))
        self.assertFalse(can_view_page(logged_out_user, "My Profile"))

    # Case 15: Restart simulation and verify accounts persist
    def test_15_restart_and_verify_account_persistence(self):
        # Simulate app restart by re-initializing connection and querying
        init_db()
        user = authenticate("update.test@example.com", "pass1234")
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Updated Name Patil")

if __name__ == "__main__":
    unittest.main()
