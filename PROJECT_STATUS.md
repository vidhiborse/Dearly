# Dearly — Project Status

**Current Phase:** Phase 5 (Family & Caregiver Circle)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 5 implements a robust, secure, and accessible **Family & Caregiver Circle** module for Dearly (*Care that stays close.*). The system connects elderly individuals with authorized caregivers and family members in a unified care network.

Key capabilities delivered:
1. **Care Circle Dashboard**: Unified overview displaying the elderly person's profile, primary caregiver, authorized caregivers, family members, connection statuses, and pending invitations.
2. **In-App Invitation & Approval Workflow**: Secure workflow allowing authorized users (senior or editor caregiver) to invite existing registered accounts by email. Recipients can accept or reject invitations. Pending invitations grant zero access.
3. **Primary Caregiver Oversight**: Single active primary caregiver designation with safe reassignment controls.
4. **Shared Care Notes**: Everyday routine and observation notes with granular visibility controls (`circle` for family + caregivers; `caregivers_only` for private caregiver observations).
5. **Care Activity Timeline**: Real-time chronological audit trail of all care events, dose status confirmations, relationship changes, and notes with category filtering.
6. **In-App Notification Integration**: Automatic notifications for invitation delivery, acceptance, decline, and connection removal.
7. **100% Test Coverage**: 20 of 20 mandatory Phase 5 test scenarios passing; 77 of 77 total tests passing across all project test suites.

---

## 2. Completed in Phase 5

### A. Care Circle Dashboard
- Dedicated **"Care Circle"** section added to navigation across all three roles (Elderly, Caregiver, Family).
- Live invitation badge counter in navigation (`Care Circle [N new]`).
- Clean multi-column layout separating Primary Caregiver, Authorized Caregivers, and Family Members with relationship tags, permissions, and join dates.
- Server-side RBAC ensures each user only accesses authorized profiles and relationships.

### B. Invitation and Approval Workflow
- Workflow:
  1. Authorized user enters email address of an existing registered user.
  2. System checks account existence in `users`.
  3. Inviter selects relationship (`Son`, `Daughter`, `Spouse`, `Relative`, `Professional caregiver`, `Other`), connection role (`caregiver` or `family`), and permission level (`editor` or `viewer`).
  4. System inserts pending invitation into `care_invitations` and dispatches in-app notification to invitee.
  5. Invitee reviews invitation under their "My Invitations" tab and chooses to accept or decline.
  6. Acceptance activates the member in `care_circle` and alerts the inviter and elderly user.
  7. Rejection marks invitation `rejected` without granting any profile access.
- Strict security validations:
  - Prevents self-invitations.
  - Prevents duplicate pending invitations.
  - Prevents inviting an already active circle member.
  - Rejects unknown email addresses.
  - Revoked or expired invitations grant no access.

### C. Primary Caregiver Designation
- Enforces single primary caregiver rule per elderly profile.
- Reassigning primary status atomically unsets any prior primary designation.
- Primary caregivers automatically hold `editor` permissions.

### D. Shared Care Notes
- Accessible care note logging for everyday observations, hydration, appetite, and mobility checks.
- Non-prescriptive guarantee: care notes are informational logs, never automated prescriptions or diagnoses.
- Privacy & Visibility Controls:
  - `circle`: Visible to both family members and caregivers.
  - `caregivers_only`: Hidden from family members; strictly accessible to caregivers and senior.

### E. Care Activity Timeline
- Complete audit trail querying `activity_logs` joined with actor profiles.
- Category filters: `All Events`, `Medication & Dose Confirmations`, `Reminders & Alerts`, `Care Circle Updates`, `Care Notes`.
- Date range filtering and configurable display limits.

---

## 3. Database Schema Modifications

Database file: [data/dearly.db](file:///d:/Dearly/data/dearly.db)
Added tables, columns, and indexes in [database.py](file:///d:/Dearly/database.py):

### Table: `care_invitations`
```sql
CREATE TABLE IF NOT EXISTS care_invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elderly_user_id INTEGER NOT NULL,
    inviter_user_id INTEGER NOT NULL,
    invitee_email TEXT NOT NULL,
    invitee_user_id INTEGER,
    relationship TEXT NOT NULL,
    connection_role TEXT NOT NULL CHECK(connection_role IN ('caregiver', 'family')),
    permission_level TEXT DEFAULT 'viewer' CHECK(permission_level IN ('editor', 'viewer')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected', 'revoked', 'expired')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    responded_at TEXT,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(inviter_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(invitee_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON care_invitations(invitee_email, status);
CREATE INDEX IF NOT EXISTS idx_invitations_elderly ON care_invitations(elderly_user_id, status);
```

### Table: `care_notes`
```sql
CREATE TABLE IF NOT EXISTS care_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elderly_user_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    visibility TEXT DEFAULT 'circle' CHECK(visibility IN ('circle', 'caregivers_only')),
    is_archived INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_care_notes_elderly ON care_notes(elderly_user_id, is_archived);
```

### Table Migrations on `care_circle`
- Added `connection_role` (`TEXT DEFAULT 'family'`).
- Added `status` (`TEXT DEFAULT 'active'`).
- Added `is_primary` (`INTEGER DEFAULT 0`).
- Added `created_by` (`INTEGER`).
- Added `updated_at` (`TEXT`).

---

## 4. Test Evidence

Executed 20-scenario Phase 5 test suite in [test_phase5_circle.py](file:///d:/Dearly/test_phase5_circle.py) and full regression suite across all 77 tests:
```powershell
python -m unittest test_phase2_auth.py test_app.py test_phase3_meds.py test_phase4_reminders.py test_phase5_circle.py
.............................................................................
Ran 77 tests in 8.478s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | View an elderly user's care circle & dashboard | Passed |
| `test_02` | Invite an existing registered caregiver | Passed |
| `test_03` | Invite an existing registered family member | Passed |
| `test_04` | Reject invitation to an unknown email address | Passed |
| `test_05` | Prevent self-invitation and inviting senior to own circle | Passed |
| `test_06` | Prevent duplicate pending invitations | Passed |
| `test_07` | Accept an invitation and verify care circle entry | Passed |
| `test_08` | Reject an invitation and verify no access is granted | Passed |
| `test_09` | Verify pending invitations grant zero access | Passed |
| `test_10` | Verify accepted connections grant intended permissions (viewer vs editor) | Passed |
| `test_11` | Prevent access to unrelated elderly profiles | Passed |
| `test_12` | Remove a care-circle connection with notification | Passed |
| `test_13` | Verify removed users immediately lose access | Passed |
| `test_14` | Add and view a shared care note | Passed |
| `test_15` | Verify family viewers cannot view private caregiver notes | Passed |
| `test_16` | Display actual care activity with category filters | Passed |
| `test_17` | Assign and change the primary caregiver (single primary rule) | Passed |
| `test_18` | Verify in-app notification integration for care circle events | Passed |
| `test_19` | Verify existing medication and reminder functionality regression | Passed |
| `test_20` | Verify all care circle records persist across app restart | Passed |

---

## 5. Files Created & Modified in Phase 5

### Created:
1. **[views/care_circle_view.py](file:///d:/Dearly/views/care_circle_view.py)**: Dedicated 5-tab Care Circle dashboard (Care Circle Network, Invite Member, My Received Invitations, Shared Care Notes, Care Activity Timeline).
2. **[test_phase5_circle.py](file:///d:/Dearly/test_phase5_circle.py)**: Mandatory 20-scenario automated test suite.

### Modified:
1. **[database.py](file:///d:/Dearly/database.py)**: Added `care_invitations` and `care_notes` tables; added dynamic column migrations on `care_circle`; seeded primary caregiver and sample notes.
2. **[services/care_circle_service.py](file:///d:/Dearly/services/care_circle_service.py)**: Implemented complete invitation lifecycle, primary caregiver management, care notes CRUD with privacy filtering.
3. **[services/activity_service.py](file:///d:/Dearly/services/activity_service.py)**: Enhanced timeline query with category filters and date ranges.
4. **[services/permissions.py](file:///d:/Dearly/services/permissions.py)**: Whitelisted `Care Circle` navigation page and added permission helpers (`can_view_care_circle`, `can_manage_care_circle`, `can_view_notes`, `can_write_notes`).
5. **[views/notification_view.py](file:///d:/Dearly/views/notification_view.py)**: Added Care Circle Updates filter.
6. **[app.py](file:///d:/Dearly/app.py)**: Added `Care Circle` route, navigation badges for pending invitations, and connected `render_care_circle_view`.
7. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 5 status report.
8. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
9. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation steps for Care Circle.
10. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture and test instructions.

---

## 6. Known Limitations & Strict Scope

- **In-App Invitations Only**: All invitations, acceptances, and notifications operate within the application. No external SMTP or SMS service is claimed.
- **No Complex Shift Scheduling**: Shift rota scheduling is intentionally excluded from this phase.
- **No Diagnostic Notes**: Care notes are restricted to observational and routine care context.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [x] Phase 4: Smart Medication Reminder & Alert System
- [x] Phase 5: Family & Caregiver Circle
- [ ] Phase 6: Doctor Appointment Scheduling & Coordination
- [ ] Phase 7: Health Vitals & Clinical Readings (BP, Glucose, SpO2)
- [ ] Phase 8: Emergency SOS Workflow & Verification
