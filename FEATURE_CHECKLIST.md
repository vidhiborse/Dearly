# Dearly — Phase 2 Feature Checklist

| Requirement | Implementation File | Status | Verification Evidence |
|---|---|---|---|
| **Phase 1: Foundation & Design** | | | |
| Accessible design system & 18px body scale | `views/common.py`, `DESIGN.md` | Complete | Verified in CSS scale and WCAG AAA compliance. |
| Zero emojis, calm healthcare aesthetic | All views & services | Complete | Verified 0 emoji occurrences in Python codebase. |
| Role navigation shells (Elderly, Caregiver, Family) | `app.py`, `views/` | Complete | Tested across all 3 personas. |
| **Phase 2: Authentication & User Management** | | | |
| User registration for Elderly role | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_01`). |
| User registration for Caregiver role | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_02`). |
| User registration for Family Member role | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_03`). |
| Required field & name length validation | `services/user_service.py` | Complete | Name >= 2 chars, phone >= 7 digits enforced. |
| Strict email format regex validation | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_05`). |
| Duplicate email prevention (case-insensitive) | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_04`). |
| Password & confirmation match validation | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_06`). |
| Bcrypt secure password hashing (work factor 12) | `database.py` | Complete | Stored as `$2b$` salted hash string in SQLite. |
| Zero plaintext passwords in database or logs | `database.py`, `services/` | Complete | Password hashes only; plaintext discarded. |
| Password verification & incorrect password rejection | `database.py`, `services/auth_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_07`, `test_08`). |
| Streamlit session state management | `app.py` | Complete | Stored under `st.session_state.user`. |
| Unauthenticated access prevention | `app.py`, `services/permissions.py` | Complete | Verified in `test_phase2_auth.py` (`test_09`). |
| Working logout button & session cleanup | `app.py` | Complete | Verified in `test_phase2_auth.py` (`test_13`). |
| Protected route lockdown after logout | `app.py`, `services/permissions.py` | Complete | Verified in `test_phase2_auth.py` (`test_14`). |
| Role-based page access whitelist | `services/permissions.py` | Complete | Verified in `test_phase2_auth.py` (`test_10`). |
| Cross-patient profile isolation (backend guard) | `services/permissions.py` | Complete | Verified in `test_phase2_auth.py` (`test_11`). |
| Profile viewing (name, email, role, phone, dates) | `views/profile_view.py` | Complete | Rendered under "My Profile" menu. |
| Profile editing (full name and phone) | `services/user_service.py` | Complete | Verified in `test_phase2_auth.py` (`test_12`). |
| Role immutability during profile editing | `services/user_service.py`, `views/profile_view.py` | Complete | Role input disabled in UI; not updated in SQL. |
| Account persistence across app restarts | `database.py` | Complete | Verified in `test_phase2_auth.py` (`test_15`). |
