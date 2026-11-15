# Dearly — Project Status

**Current Phase:** Phase 2 (Authentication & User Management)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 2 introduces a complete, secure, role-enforced **Authentication and User Management module** for Dearly (*Care that stays close.*). The system provides multi-role registration, bcrypt password hashing with automatic salt generation, role-based access control (RBAC) enforced both in the UI and data layer, profile editing, and session lifecycle management.

---

## 2. Completed in Phase 2

### A. Multi-Role User Registration
- Implemented registration for all three roles: `elderly`, `caregiver`, and `family` in [services/user_service.py](file:///d:/Dearly/services/user_service.py).
- Strict input validation:
  - Full name (minimum 2 characters, trimmed).
  - Email format validation via regex.
  - Case-insensitive duplicate email detection.
  - Phone validation (minimum 7 digits).
  - Password strength validation (minimum 6 characters).
  - Password and confirmation matching.
  - Role validation restricted to `('elderly', 'caregiver', 'family')`.
- Auto-initialization of `elderly_profiles` row upon elderly registration.

### B. Secure Login & Password Hashing
- Integrated `bcrypt` (work factor 12) for all new registrations and password verifications.
- Zero plaintext passwords stored or logged.
- Backward compatibility fallback for legacy prototype SHA-256 hashes in [database.py](file:///d:/Dearly/database.py).
- Public login screen confidentiality: no plaintext passwords exposed in public UI elements.
- Clean session persistence in Streamlit session state (`user`, `selected_ward_id`, `current_page`).
- Complete logout functionality that purges session attributes and re-routes to unauthenticated view.

### C. Backend Role-Based Access Control (RBAC)
- Implemented dedicated authorization guard in [services/permissions.py](file:///d:/Dearly/services/permissions.py):
  - **Elderly Users**: Can only view and update their own care record and personal profile.
  - **Caregivers**: Can only access elderly records explicitly linked to them via `care_circle` with `editor` permissions.
  - **Family Members**: Can only view care information for elderly relatives linked via `care_circle` with read-only (`viewer`) rights.
  - **Cross-Patient Isolation**: Unrelated users are rejected at both UI routing and backend data access levels.

### D. User Profile Management
- Created dedicated profile view in [views/profile_view.py](file:///d:/Dearly/views/profile_view.py) accessible from all role shells via `"My Profile"`.
- Allows viewing email and system-assigned role (read-only).
- Allows updating full name and phone number with instant session state reflection and SQLite persistence.
- Prevents role escalation or alteration through user profile editing.

### E. Database Enhancements
- Added `updated_at` column migration to `users` table.
- Parameterized all SQL statements to eliminate injection risks.
- Maintained idempotent database initialization (`init_db()`).

---

## 3. Test Evidence

Executed 15-case Phase 2 test suite in [test_phase2_auth.py](file:///d:/Dearly/test_phase2_auth.py) and 8-case regression suite in [test_app.py](file:///d:/Dearly/test_app.py):

| Test ID | Case Description | Result |
|---|---|---|
| `test_01` | Register a new elderly user with auto profile initialization | PASSED |
| `test_02` | Register a new caregiver user | PASSED |
| `test_03` | Register a new family member user | PASSED |
| `test_04` | Reject duplicate email registration | PASSED |
| `test_05` | Reject invalid email formats | PASSED |
| `test_06` | Reject mismatched passwords | PASSED |
| `test_07` | Successfully log in with valid credentials | PASSED |
| `test_08` | Reject incorrect passwords | PASSED |
| `test_09` | Prevent access without authentication | PASSED |
| `test_10` | Verify role-based page whitelist access | PASSED |
| `test_11` | Verify users cannot access unrelated elderly profiles | PASSED |
| `test_12` | Update and save personal profile in SQLite | PASSED |
| `test_13` | Log out and verify session state is cleared | PASSED |
| `test_14` | Verify protected pages cannot be accessed after logout | PASSED |
| `test_15` | Restart application and verify accounts persist | PASSED |

**Total Suite Result:** 23 tests executed, 23 passed, 0 failed.

---

## 4. Known Limitations & Pending Features

- **Email Verification**: Email confirmations are simulated in local prototypes without an active SMTP gateway.
- **Password Reset Flow**: Self-service forgot-password token dispatch scheduled for future cloud deployment phase.
- **Strict Scope Adherence**: Medication management, real-time push reminders, doctor appointments, and AI assistant modules remain scheduled for subsequent phases.
