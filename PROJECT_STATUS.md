# Dearly — Project Status

**Current Phase:** Phase 4 (Smart Medication Reminder & Alert System)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 4 implements a complete, reliable, and accessible **Smart Medication Reminder & Alert System** for Dearly (*Care that stays close.*). Built upon Phase 3 medication schedules and dose tracking, this module delivers:
1. Deterministic reminder status evaluation (`upcoming`, `due_now`, `overdue`, `completed`, `skipped`).
2. Configurable grace-period calculations (default 15 minutes, configurable per user from 5 to 60 minutes).
3. Dedicated **Notification Center** with read/unread tracking, filter by type (`due_now`, `overdue`, `escalation`, `completed`), and ward isolation.
4. Duplicate-proof caregiver escalation for overdue doses past grace periods, notifying authorized caregivers with `editor` permission in the care circle.
5. Strict separation between caregiver escalation acknowledgement and dose confirmation (acknowledging an escalation records caregiver oversight without falsely marking the dose as taken).
6. User preference controls for grace period, notification toggles, and 12h/24h time display.
7. 100% test coverage across a mandatory 17-scenario automated test suite.

---

## 2. Completed in Phase 4

### A. Upcoming & Active Reminders
- Schedule-driven reminders calculated directly from active medication regimens and dose logs.
- Status categorization:
  - `upcoming`: Scheduled datetime is in the future.
  - `due_now`: Scheduled time has arrived and current time is within `[schedule_time, schedule_time + grace_period]`.
  - `overdue`: Current time has passed `schedule_time + grace_period` without dose recorded as taken or skipped.
  - `completed`: Dose has been explicitly marked as taken.
  - `skipped`: Dose has been explicitly marked as skipped.
- Time display formatted in accordance with user's preferred format (`12h` or `24h`).
- Start and end date validation: excluded doses outside active date windows.

### B. In-App Notification Center
- Accessible view located at `Reminders & Alerts` in main navigation.
- Live unread notification badge in navigation menu (`[N new]`).
- Notifications stream tab with multi-filter capabilities:
  - Filter by alert category (`All`, `Due Now`, `Overdue`, `Caregiver Escalation`, `Completed`).
  - Filter by elderly ward (for caregivers/family members managing multiple seniors).
  - Unread-only filter.
- Actions:
  - Mark individual notification as read.
  - One-click Mark all as read.
  - Filter and badge counters update reactively.

### C. Caregiver Escalation System
- Overdue dose escalation: when a dose remains unrecorded past the configurable grace period, an escalation record and notification are dispatched to all caregivers linked in `care_circle` with `editor` permissions.
- Duplicate prevention: SQLite unique constraint `UNIQUE(medication_id, scheduled_date, scheduled_time, caregiver_user_id)` ensures idempotent synchronization without alert floods.
- Caregiver action panel:
  - Caregivers can view all active escalations with patient name, medication name, dosage, scheduled time, and overdue duration.
  - **Acknowledge Escalation**: Caregivers can acknowledge the alert with optional audit notes.
  - **Explicit Non-Conflation**: Acknowledging an escalation records oversight; it does *not* falsely mark the medication as taken.
  - **One-Click Administration**: Caregivers can directly confirm dose administration or record skip reasons from the escalation card.
  - **Auto-Resolution**: When a dose is recorded as taken, active pending escalations automatically transition to `resolved`.

### D. User Reminder Preferences
- User-level preferences stored in `reminder_settings` table:
  - `grace_period_minutes`: 5 to 60 minutes (default: 15 minutes).
  - `enable_reminders`: In-app reminder notifications toggle.
  - `enable_escalation`: Caregiver overdue escalation toggle.
  - `time_format`: `12h` (AM/PM) vs `24h` military format.
- Interactive settings form with real-time feedback and safe validation.

---

## 3. Database Schema Modifications

Database file: [data/dearly.db](file:///d:/Dearly/data/dearly.db)
Added tables and indexes in [database.py](file:///d:/Dearly/database.py):

### Table: `notifications`
```sql
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    elderly_user_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL,  -- 'due_now', 'overdue', 'escalation', 'completed'
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    medication_id INTEGER,
    scheduled_date TEXT,
    scheduled_time TEXT,
    is_read INTEGER DEFAULT 0,
    read_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (medication_id) REFERENCES medications(id) ON DELETE SET NULL,
    UNIQUE(user_id, medication_id, scheduled_date, scheduled_time, alert_type)
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_elderly ON notifications(elderly_user_id);
```

### Table: `caregiver_escalations`
```sql
CREATE TABLE IF NOT EXISTS caregiver_escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medication_id INTEGER NOT NULL,
    elderly_user_id INTEGER NOT NULL,
    caregiver_user_id INTEGER NOT NULL,
    scheduled_date TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'acknowledged', 'resolved'
    escalated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_acknowledged INTEGER DEFAULT 0,
    acknowledged_at TEXT,
    acknowledged_by INTEGER,
    FOREIGN KEY (medication_id) REFERENCES medications(id) ON DELETE CASCADE,
    FOREIGN KEY (elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (caregiver_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (acknowledged_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(medication_id, scheduled_date, scheduled_time, caregiver_user_id)
);
CREATE INDEX IF NOT EXISTS idx_escalations_caregiver ON caregiver_escalations(caregiver_user_id, status);
```

### Table: `reminder_settings`
```sql
CREATE TABLE IF NOT EXISTS reminder_settings (
    user_id INTEGER PRIMARY KEY,
    grace_period_minutes INTEGER DEFAULT 15,
    enable_reminders INTEGER DEFAULT 1,
    enable_escalation INTEGER DEFAULT 1,
    time_format TEXT DEFAULT '12h',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 4. Test Evidence

Executed 17-scenario Phase 4 test suite in [test_phase4_reminders.py](file:///d:/Dearly/test_phase4_reminders.py) and full regression suite across all 57 tests:
```powershell
python -m unittest test_phase2_auth.py test_app.py test_phase3_meds.py test_phase4_reminders.py
.........................................................
Ran 57 tests in 7.722s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | Upcoming reminder generation (future scheduled time) | Passed |
| `test_02` | Due-now reminder generation & in-app notification | Passed |
| `test_03` | Overdue detection past grace period & caregiver escalation dispatch | Passed |
| `test_04` | Completed dose status updates reminder to completed | Passed |
| `test_05` | Skipped dose status updates reminder to skipped | Passed |
| `test_06` | Boundary grace-period calculation (before, exact, inside, past window) | Passed |
| `test_07` | Medication start and end date handling (excludes future/expired) | Passed |
| `test_08` | Duplicate reminder prevention via SQLite UNIQUE constraint | Passed |
| `test_09` | Duplicate caregiver escalation prevention across multiple syncs | Passed |
| `test_10` | Caregiver acknowledgement recorded without marking dose as taken | Passed |
| `test_11` | Notification read/unread status decrement & mark all read | Passed |
| `test_12` | Notification persistence after database restart | Passed |
| `test_13` | Role-based access control (elderly self, editor caregiver, viewer family, unrelated blocked) | Passed |
| `test_14` | Multi-profile elderly isolation (no cross-senior data leakage) | Passed |
| `test_15` | Timezone and midnight date-boundary transition handling | Passed |
| `test_16` | Idempotent reminder generation on repeated application refresh | Passed |
| `test_17` | Existing Phase 3 medication management & adherence regression | Passed |

---

## 5. Files Created & Modified in Phase 4

### Created:
1. **[services/reminder_service.py](file:///d:/Dearly/services/reminder_service.py)**: Reminder status calculator, synchronization engine, notification manager, escalation tracker, user preferences.
2. **[views/notification_view.py](file:///d:/Dearly/views/notification_view.py)**: Accessible Notification Center view with 4 tabs (Active Reminders, Notifications Stream, Caregiver Escalations, Reminder Settings).
3. **[test_phase4_reminders.py](file:///d:/Dearly/test_phase4_reminders.py)**: Mandatory 17-scenario automated test suite.

### Modified:
1. **[database.py](file:///d:/Dearly/database.py)**: Schema migrations for `notifications`, `caregiver_escalations`, and `reminder_settings`.
2. **[services/medication_service.py](file:///d:/Dearly/services/medication_service.py)**: Auto-resolution hook resolving caregiver escalations when dose status transitions to taken.
3. **[services/permissions.py](file:///d:/Dearly/services/permissions.py)**: Added `Reminders & Alerts` route to allowed pages for all authenticated roles.
4. **[app.py](file:///d:/Dearly/app.py)**: Integrated dynamic notification count badge in navigation radio, auto-sync hook on page load, and router connection to `notification_view`.
5. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 4 status report.
6. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
7. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation steps for Notification Center.
8. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture and test instructions.

---

## 6. Known Limitations & Strict Scope

- **In-App Notifications Only**: Real-time SMS, WhatsApp, and Web Push notifications are deferred until subsequent infrastructure integration.
- **No AI Prescribing**: Dearly is an intelligent coordination platform, not an autonomous medical diagnostic or prescribing engine.
- **Safety Protocol**: Overdue alerts explicitly advise patients and caregivers to consult before taking delayed medications; never double up.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [x] Phase 4: Smart Medication Reminder & Alert System
- [ ] Phase 5: Doctor Appointment Scheduling & Coordination
- [ ] Phase 6: Health Vitals & Clinical Readings (BP, Glucose, SpO2)
- [ ] Phase 7: Care Circle Escalations & Demo SOS Workflow
