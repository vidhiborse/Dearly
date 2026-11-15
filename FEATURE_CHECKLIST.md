# Dearly — Master Feature Checklist

| Requirement | Implementation File | Status | Verification Evidence |
|---|---|---|---|
| **Phase 1: Foundation & Design** | | | |
| Accessible design system & 18px body scale | `views/common.py`, `DESIGN.md` | Complete | Verified in CSS scale and WCAG AAA compliance. |
| Zero emojis, calm healthcare aesthetic | All views & services | Complete | Verified 0 emoji occurrences across all Python files. |
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
| **Phase 3: Medication Management** | | | |
| Add medication successfully | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_01`). |
| Input validation for required fields | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_02`). |
| Input validation for dates (`end_date >= start_date`) | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_03`). |
| Multi-filter Medication Registry (All, Active, Inactive) | `views/caregiver_view.py` | Complete | Verified in `test_phase3_meds.py` (`test_04`, `test_05`). |
| Edit existing medication details & timestamps | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_06`). |
| Deactivate medication with history preservation | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_07`). |
| Delete medication only with confirmation & audit log | `services/medication_service.py` | Complete | Verified with confirmation checkbox in UI. |
| RBAC: Unauthorized modifications rejected | `services/permissions.py` | Complete | Verified in `test_phase3_meds.py` (`test_08`). |
| Daily schedule grouped into Morning, Afternoon, Evening, Night | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_09`). |
| Record dose status as taken (with actual action time) | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_10`). |
| Record dose status as skipped with clinical notes | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_11`). |
| Prevent duplicate dose logs via SQLite UPSERT | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_12`). |
| Calculate adherence correctly: (Taken / Total Due) * 100 | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_13`). |
| Identify overdue doses using current local time | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_14`). |
| Exclude future scheduled doses from overdue checks | `services/medication_service.py` | Complete | Verified in `test_phase3_meds.py` (`test_15`). |
| In-app overdue notice without extra dose/doubling advice | `views/elderly_view.py`, `views/caregiver_view.py` | Complete | Verified in warning banners with clinical disclaimer. |
| Medication persistence across application restart | `database.py` | Complete | Verified in `test_phase3_meds.py` (`test_16`). |
| Zero regression on authentication & profile updates | `test_app.py`, `test_phase2_auth.py` | Complete | Verified in `test_phase3_meds.py` (`test_17`) and full suite. |
| **Phase 4: Smart Medication Reminders & Alerts** | | | |
| Upcoming reminder generation for future doses | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_01`). |
| Due-now reminder generation within grace window | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_02`). |
| Overdue detection past configurable grace period | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_03`). |
| Completed dose status handling | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_04`). |
| Skipped dose status handling | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_05`). |
| Grace period boundary calculation (5 - 60 min range) | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_06`). |
| Respect medication start and end dates | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_07`). |
| Prevent duplicate notifications via SQLite unique constraint | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_08`). |
| Prevent duplicate caregiver escalations | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_09`). |
| Caregiver acknowledgement without marking dose taken | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_10`). |
| In-app notification center (unread tracking & mark read) | `services/reminder_service.py`, `views/notification_view.py` | Complete | Verified in `test_phase4_reminders.py` (`test_11`). |
| Notification persistence across application restart | `database.py` | Complete | Verified in `test_phase4_reminders.py` (`test_12`). |
| Role-based access control for reminders & escalations | `services/permissions.py`, `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_13`). |
| Cross-profile isolation for multiple elderly wards | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_14`). |
| Timezone and date boundary handling | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_15`). |
| Idempotent reminder generation on page refreshes | `services/reminder_service.py` | Complete | Verified in `test_phase4_reminders.py` (`test_16`). |
| Existing Phase 3 medication management regression | `test_phase3_meds.py`, `test_phase4_reminders.py` | Complete | Verified in `test_phase4_reminders.py` (`test_17`) & 57/57 tests passing. |
| **Phase 5: Family & Caregiver Circle** | | | |
| View care circle members & structured dashboard | `services/care_circle_service.py`, `views/care_circle_view.py` | Complete | Verified in `test_phase5_circle.py` (`test_01`). |
| Invite existing registered caregiver | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_02`). |
| Invite existing registered family member | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_03`). |
| Reject invitation to unknown email address | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_04`). |
| Prevent self-invitation & senior self-invitation | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_05`). |
| Prevent duplicate pending invitations | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_06`). |
| Accept invitation and activate circle connection | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_07`). |
| Reject invitation without granting profile access | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_08`). |
| Pending invitations grant zero access | `services/permissions.py`, `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_09`). |
| Accepted connection grants intended permission (viewer vs editor) | `services/permissions.py` | Complete | Verified in `test_phase5_circle.py` (`test_10`). |
| Prevent access to unrelated elderly profiles | `services/permissions.py` | Complete | Verified in `test_phase5_circle.py` (`test_11`). |
| Remove member from care circle with notification | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_12`). |
| Removed members immediately lose all profile access | `services/permissions.py` | Complete | Verified in `test_phase5_circle.py` (`test_13`). |
| Add and view shared care notes | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_14`). |
| Privacy enforcement: family cannot view private caregiver notes | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_15`). |
| Display actual care activity with category filtering | `services/activity_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_16`). |
| Assign and change single primary caregiver | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_17`). |
| In-app notification integration for circle events | `services/care_circle_service.py` | Complete | Verified in `test_phase5_circle.py` (`test_18`). |
| Existing medication and reminder regression verification | `test_phase3_meds.py`, `test_phase4_reminders.py` | Complete | Verified in `test_phase5_circle.py` (`test_19`). |
| Complete care circle persistence across restart | `database.py` | Complete | Verified in `test_phase5_circle.py` (`test_20`). |
