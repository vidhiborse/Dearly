# Dearly — Project Status

**Current Phase:** Phase 6 (Doctor Appointment Management)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 6 implements a comprehensive, clinically organized, and accessible **Doctor Appointment Management** module for Dearly (*Care that stays close.*). The system empowers seniors, authorized caregivers, and family members to coordinate medical consultations, specialist visits, routine examinations, and follow-ups.

Key capabilities delivered:
1. **Appointment Creation & Clinical Metadata**: Capture patient profile, doctor's name, medical specialization, clinic/hospital, date, time, appointment type, location/address, reason for visit, and pre-visit notes with server-side validation.
2. **Accessible Appointment Dashboard**: Dedicated **"Appointments"** section in primary navigation with clear tabs for Upcoming Visits, Calendar View, Schedule New Visit, and Visit History & Summaries. Prominent highlight for visits scheduled today.
3. **Multi-Criteria Filtering**: Filter visits by appointment status (`all`, `today`, `upcoming`, `completed`, `cancelled`, `missed`), custom date ranges, and doctor/clinic keyword search.
4. **Lifecycle Actions & Clinical Summaries**: Complete appointment lifecycle support: reschedule to new date/time with automated reminder reset, cancel with reason and confirmation, mark completed with post-visit doctor notes/prescriptions, or mark missed.
5. **Deterministic In-App Reminders**: Automated 1-day-before and 1-hour-before in-app alerts dispatched to both the patient and linked care-circle members with duplicate suppression via SQLite unique constraints. Zero reminders sent for completed or cancelled visits.
6. **Role-Based Access Control**: Strict server-side verification: seniors and editor caregivers can schedule, reschedule, edit, and record summaries; family members have comprehensive read-only observation. Cross-patient tampering is blocked.
7. **Interactive Calendar & History**: Chronological calendar-grouped view by date and persistent historical archive of all past consultations.
8. **100% Test Coverage**: 21 of 21 mandatory Phase 6 test scenarios passing; 98 of 98 total tests passing across all project test suites with 0 errors and 0 failures.

---

## 2. Completed in Phase 6

### A. Appointment Creation & Validation
- Added appointment types: `General check-up`, `Follow-up visit`, `Specialist consultation`, `Routine examination`, `Other`.
- Required fields validated: Doctor name (>= 2 chars), Hospital/Clinic name (>= 2 chars), valid calendar date (`YYYY-MM-DD`), and parseable time.
- Prevention of past appointment scheduling (unless explicit historical record).
- Pre-visit notes and reason captured for clinical context.

### B. Appointment Dashboard & Today's Highlight
- Dedicated **"Appointments"** section added to navigation across all three user roles.
- **"Today's Appointments"** alert card at top of dashboard with high-contrast badge and quick actions.
- Action expanders for immediate rescheduling, completion notes, and cancellation.

### C. Lifecycle Management & Post-Visit Summaries
- **Rescheduling**: Validates new date/time, updates record, logs activity, and atomically resets any previous reminders.
- **Completion**: Allows recording post-visit doctor instructions, diagnostic notes, and medication adjustments.
- **Cancellation**: Requires confirmation and records cancellation reason.
- **Audit Logging**: Every action logged to `activity_logs` with actor attribution.

### D. In-App Appointment Reminders
- Dual deterministic reminder windows:
  1. `1_day_before`: Evaluated within 24 hours of scheduled consultation.
  2. `1_hour_before`: Evaluated within 1 hour of consultation.
- Dispatched to senior and all active caregivers in the care circle.
- Suppressed immediately if an appointment is completed or cancelled.
- Prevented duplicate alerts via `appointment_reminders` unique constraints.

### E. Calendar View & Historical Archive
- Date-grouped agenda view showing upcoming visits by date.
- Complete historical record of all completed, cancelled, and missed visits with clinical summaries.

---

## 3. Database Schema Modifications

Database file: [data/dearly.db](file:///d:/Dearly/data/dearly.db)
Added tables, columns, and indexes in [database.py](file:///d:/Dearly/database.py):

### Table: `appointments` (Migrated)
```sql
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elderly_user_id INTEGER NOT NULL,
    doctor_name TEXT NOT NULL,
    specialization TEXT DEFAULT '',
    hospital TEXT NOT NULL,
    appointment_date TEXT NOT NULL,
    appointment_time TEXT NOT NULL,
    appointment_type TEXT DEFAULT 'General check-up',
    location TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    purpose TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    post_visit_notes TEXT DEFAULT '',
    status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'completed', 'cancelled', 'missed')),
    reminder_sent INTEGER DEFAULT 0,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(updated_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_appointments_elderly ON appointments(elderly_user_id, appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(elderly_user_id, status);
```

### Table: `appointment_reminders`
```sql
CREATE TABLE IF NOT EXISTS appointment_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL,
    elderly_user_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL CHECK(reminder_type IN ('1_day_before', '1_hour_before')),
    scheduled_for TEXT NOT NULL,
    is_sent INTEGER DEFAULT 0,
    sent_at TEXT,
    FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(appointment_id, user_id, reminder_type)
);
CREATE INDEX IF NOT EXISTS idx_appt_reminders_user ON appointment_reminders(user_id, is_sent);
CREATE INDEX IF NOT EXISTS idx_appt_reminders_appt ON appointment_reminders(appointment_id);
```

---

## 4. Test Evidence

Executed 21-scenario Phase 6 test suite in [test_phase6_appts.py](file:///d:/Dearly/test_phase6_appts.py) and full regression suite across all 98 tests:
```powershell
python -m unittest test_app.py test_phase2_auth.py test_phase3_meds.py test_phase4_reminders.py test_phase5_circle.py test_phase6_appts.py
..................................................................................................
Ran 98 tests in 36.263s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | Create appointment with all required fields | Passed |
| `test_02` | Validate doctor name length (min 2 chars) | Passed |
| `test_03` | Validate hospital / clinic name (min 2 chars) | Passed |
| `test_04` | Validate appointment date format (YYYY-MM-DD) | Passed |
| `test_05` | Prevent past appointment date creation | Passed |
| `test_06` | Validate appointment time format | Passed |
| `test_07` | Support all appointment types | Passed |
| `test_08` | Retrieve appointments by elderly user id | Passed |
| `test_09` | Filter appointments by status (upcoming vs completed) | Passed |
| `test_10` | Filter appointments by date range | Passed |
| `test_11` | Filter appointments by doctor keyword search | Passed |
| `test_12` | Retrieve single appointment details with creator metadata | Passed |
| `test_13` | Edit appointment details & verify persistence | Passed |
| `test_14` | Reschedule appointment to future date and time | Passed |
| `test_15` | Cancel appointment with confirmation and reason | Passed |
| `test_16` | Mark appointment completed with post-visit notes | Passed |
| `test_17` | Generate 1-day-before and 1-hour-before in-app reminders | Passed |
| `test_18` | Prevent duplicate appointment reminders via unique constraints | Passed |
| `test_19` | Zero reminders generated for cancelled or completed appointments | Passed |
| `test_20` | Family members have read-only access and cannot edit appointments | Passed |
| `test_21` | Calendar view groups appointments by date and displays past history | Passed |

---

## 5. Files Created & Modified in Phase 6

### Created:
1. **[views/appointment_view.py](file:///d:/Dearly/views/appointment_view.py)**: Dedicated 4-tab Doctor Appointments dashboard (Upcoming Visits, Calendar & Date View, Schedule New Visit, Visit History & Summaries).
2. **[test_phase6_appts.py](file:///d:/Dearly/test_phase6_appts.py)**: Mandatory 21-scenario automated test suite.

### Modified:
1. **[database.py](file:///d:/Dearly/database.py)**: Migrated `appointments` schema to support `status` check, `specialization`, `appointment_type`, `location`, `reason`, `post_visit_notes`, `created_by`, `updated_by`, `updated_at`; added `appointment_reminders` table and indexes.
2. **[services/appointment_service.py](file:///d:/Dearly/services/appointment_service.py)**: Comprehensive appointment service with validation, CRUD, reschedule, cancel, complete, calendar grouping, history, legacy wrappers, and dual reminder generation.
3. **[app.py](file:///d:/Dearly/app.py)**: Connected `render_appointment_view`, routed `"Appointments"` page across all roles, and hooked `sync_appointment_reminders()` on application load.
4. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 6 status report.
5. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
6. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation steps for Doctor Appointments.
7. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture and test instructions.

---

## 6. Known Limitations & Strict Scope

- **In-App Alerts Only**: Appointment reminders and reschedule notices operate within the application. No external SMS/WhatsApp/push delivery is claimed.
- **No Direct Telemedicine / Video Streams**: In-person clinic and hospital visits are tracked; external video call integration is intentionally out of scope.
- **Non-Diagnostic**: Doctor summaries and visit notes are user-recorded logs of physician visits, not automated AI diagnostic decisions.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [x] Phase 4: Smart Medication Reminder & Alert System
- [x] Phase 5: Family & Caregiver Circle
- [x] Phase 6: Doctor Appointment Scheduling & Coordination
- [ ] Phase 7: Health Vitals & Clinical Readings (BP, Glucose, SpO2)
- [ ] Phase 8: Emergency SOS Workflow & Verification

