# Dearly — Project Status

**Current Phase:** Phase 7 (Health Monitoring & Health Records)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 7 implements a robust, clinically organized, and accessible **Health Monitoring and Health Records** module for Dearly (*Care that stays close.*). The system empowers seniors, authorized caregivers, and family members to record, review, and visualize health information over time.

Key capabilities delivered:
1. **Health Records Dashboard**: Dedicated 5-tab interface (Health Summary & Latest Vitals, Health Trends & Charts, Record History & Audit, Record New Measurement, Wellbeing Observations) with explicit medical disclaimers and helpful empty states.
2. **Comprehensive Measurements Support**: Full clinical support for:
   - **Blood Pressure**: Systolic & Diastolic (`mmHg`), context, and reference range comparison.
   - **Blood Sugar**: Numeric value, unit (`mg/dL` or `mmol/L`), context (`fasting`, `before_meal`, `after_meal`, `random`).
   - **Weight**: Numeric value, unit (`kg` or `lb`), context.
   - **Heart Rate**: Numeric value (`bpm`).
   - **Oxygen Saturation (SpO2)**: Numeric value (`%`).
   - **Body Temperature**: Numeric value, unit (`°C` or `°F`).
3. **Clinical Boundary Validation**: Strict validation rejecting physically impossible values (non-numeric, negative values, diastolic >= systolic), while allowing legitimate edge readings with neutral clinical notices.
4. **Informational Reference Ranges**: Neutral evaluation labels (`Within standard reference range`, `Outside standard reference range`) with standard disclaimers advising users to consult a doctor. Strictly non-diagnostic; zero overall risk scores or treatment alterations.
5. **Plotly Health Trends**: Interactive, high-contrast trend charts for Systolic/Diastolic BP, Blood Sugar, Weight, Heart Rate, and SpO2 with target reference zones and informative handling for single readings.
6. **Immutable Audit Trail for Record Corrections**: Authorized users can correct miskeyed readings while preserving previous values, actor ID, and correction reason in `health_record_audit`.
7. **Care Circle Role-Based Access Control**: Seniors and editor caregivers can log and correct readings; family members have full read-only observability. Cross-patient tampering is blocked.
8. **Doctor Appointment Integration**: Allows linking health readings and post-visit observations directly to scheduled doctor consultations.
9. **CSV Export**: Permission-checked, RFC-compliant CSV export for patient records.
10. **100% Test Coverage**: 22 of 22 mandatory Phase 7 test scenarios passing; 120 of 120 total tests passing across all project test suites with 0 errors and 0 failures.

---

## 2. Completed in Phase 7

### A. Health Record Dashboard
- Dedicated section across all user roles:
  - Elderly: "My Health" / "Health Records"
  - Caregiver: "Health Records"
  - Family: "Health Summary" / "Health Records"
- Multi-column vital cards showing latest values, units, context, timestamps, and reference status badges.
- Informational guide expander detailing standard adult clinical reference guidelines.

### B. Health Measurements & Form Validation
- Standard measurement types supported: Blood Pressure, Blood Sugar, Weight, Heart Rate, Oxygen Saturation (SpO2), Body Temperature.
- Validates formats, positive numbers, and units.
- Non-diagnostic neutral warning dispatched when readings exceed reference thresholds.

### C. Health Trends & Plotly Visualizations
- Separate charts with chronological x-axis, units, and reference bands.
- Informational notice when insufficient history (< 2 readings) is available.
- Zero fabrication of data points.

### D. Qualitative Wellbeing Observations
- Categorized observation logging (`general`, `energy_sleep`, `appetite_diet`, `mobility`, `mood_wellbeing`, `post_visit`).
- Chronological observation feed with actor attribution and date/time stamps.

### E. Record Correction with Audit Trail
- Non-destructive updates: original values saved to `health_record_audit` before record modification.
- UI expander displaying audit history for any corrected measurement.

### F. CSV Health Export
- Generates structured CSV with headers: Record ID, Patient Name, Date, Time, Measurement Type, Reading Value, Unit, Context, Recorded By, Status / Range, Notes, Corrected, Correction Reason.

---

## 3. Database Schema Modifications

Database file: [data/dearly.db](file:///d:/Dearly/data/dearly.db)
Added tables, columns, and indexes in [database.py](file:///d:/Dearly/database.py):

### Table: `health_readings` (Migrated & Enhanced)
- Added `systolic INTEGER`
- Added `diastolic INTEGER`
- Added `numeric_value REAL`
- Added `unit TEXT DEFAULT ''`
- Added `context TEXT DEFAULT ''`
- Added `recorded_time TEXT DEFAULT ''`
- Added `recorded_by INTEGER`
- Added `appointment_id INTEGER`
- Added `is_corrected INTEGER DEFAULT 0`
- Added `corrected_at TEXT`
- Added `corrected_by INTEGER`
- Added `correction_notes TEXT`
- Added `updated_at TEXT`
- Index: `idx_health_readings_elderly` on `(elderly_user_id, recorded_on)`

### Table: `health_observations`
```sql
CREATE TABLE IF NOT EXISTS health_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elderly_user_id INTEGER NOT NULL,
    observation_text TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    recorded_on TEXT NOT NULL,
    recorded_time TEXT DEFAULT '',
    appointment_id INTEGER,
    recorded_by INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
    FOREIGN KEY(recorded_by) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_health_obs_elderly ON health_observations(elderly_user_id, recorded_on);
```

### Table: `health_record_audit`
```sql
CREATE TABLE IF NOT EXISTS health_record_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_id INTEGER NOT NULL,
    elderly_user_id INTEGER NOT NULL,
    changed_by INTEGER NOT NULL,
    old_reading_type TEXT,
    old_reading_value TEXT,
    old_unit TEXT,
    new_reading_type TEXT,
    new_reading_value TEXT,
    new_unit TEXT,
    reason_for_change TEXT NOT NULL,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(reading_id) REFERENCES health_readings(id) ON DELETE CASCADE,
    FOREIGN KEY(elderly_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(changed_by) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_health_audit_reading ON health_record_audit(reading_id);
```

---

## 4. Test Evidence

Executed 22-scenario Phase 7 test suite in [test_phase7_health.py](file:///d:/Dearly/test_phase7_health.py) and full regression suite across all 120 tests:
```powershell
python -m unittest test_app.py test_phase2_auth.py test_phase3_meds.py test_phase4_reminders.py test_phase5_circle.py test_phase6_appts.py test_phase7_health.py
........................................................................................................................
Ran 120 tests in 49.023s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | Record a valid blood pressure reading | Passed |
| `test_02` | Record a valid blood sugar reading with context and unit | Passed |
| `test_03` | Record a weight measurement | Passed |
| `test_04` | Record heart rate, SpO2, and body temperature | Passed |
| `test_05` | Reject invalid measurement formats (negative, non-numeric, diastolic >= systolic) | Passed |
| `test_06` | Validate units and reject invalid units for measurement types | Passed |
| `test_07` | Record qualitative health observations with categories | Passed |
| `test_08` | Display latest vitals for each measurement type | Passed |
| `test_09` | Display chronological history in descending date/time order | Passed |
| `test_10` | Filter records by measurement type and date range | Passed |
| `test_11` | Generate Plotly charts using real database measurements | Passed |
| `test_12` | Handle insufficient chart data gracefully | Passed |
| `test_13` | Correct a health record while preserving full audit history | Passed |
| `test_14` | Export filtered health records to CSV with valid format | Passed |
| `test_15` | Authorized editor caregiver can record and correct readings | Passed |
| `test_16` | Family members have read-only access; write operations are rejected | Passed |
| `test_17` | Prevent access to unrelated elderly profiles (cross-ward protection) | Passed |
| `test_18` | Verify health records and audit trails persist across database restart | Passed |
| `test_19` | Verify existing medication management features continue working | Passed |
| `test_20` | Verify existing reminder and escalation engine continues working | Passed |
| `test_21` | Verify Care Circle membership and care notes remain functional | Passed |
| `test_22` | Verify appointment scheduling, rescheduling, and reminders remain functional | Passed |

---

## 5. Files Created & Modified in Phase 7

### Created:
1. **[views/health_view.py](file:///d:/Dearly/views/health_view.py)**: Dedicated 5-tab Health Records & Monitoring view (Summary & Latest Vitals, Trends & Charts, Record History & Audit, Log Measurement, Wellbeing Observations).
2. **[test_phase7_health.py](file:///d:/Dearly/test_phase7_health.py)**: Mandatory 22-scenario automated test suite.

### Modified:
1. **[database.py](file:///d:/Dearly/database.py)**: Added `health_observations` and `health_record_audit` tables; added column migrations and backfill for `health_readings`.
2. **[services/health_service.py](file:///d:/Dearly/services/health_service.py)**: Implemented complete health measurement CRUD, clinical boundary validation, informational reference range evaluation, audit tracking, Plotly trend generation, and CSV export.
3. **[services/permissions.py](file:///d:/Dearly/services/permissions.py)**: Added `can_view_health_records` and `can_manage_health_records` RBAC helpers.
4. **[app.py](file:///d:/Dearly/app.py)**: Connected `render_health_view` to routes (`"Health Records"`, `"My Health"`, `"Health Summary"`).
5. **[views/caregiver_view.py](file:///d:/Dearly/views/caregiver_view.py)**: Delegated Health Records to `render_health_view`.
6. **[views/elderly_view.py](file:///d:/Dearly/views/elderly_view.py)**: Delegated My Health to `render_health_view`.
7. **[views/family_view.py](file:///d:/Dearly/views/family_view.py)**: Delegated Health Summary to `render_health_view`.
8. **[views/appointment_view.py](file:///d:/Dearly/views/appointment_view.py)**: Integrated health vitals review and post-visit observation logging.
9. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 7 status report.
10. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
11. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation steps for Health Monitoring.
12. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture and test instructions.

---

## 6. Known Limitations & Strict Scope

- **Non-Diagnostic**: Health readings and reference ranges are strictly for personal tracking and care coordination. Dearly never provides medical diagnoses, automated dosage changes, or treatment advice.
- **No Wearable APIs**: In-person digital thermometer, blood pressure cuff, and pulse oximeter readings are recorded manually; Bluetooth / proprietary wearable streams are out of scope.
- **No Automated External Transmission**: Health records are not automatically transmitted to doctors or external hospital networks.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [x] Phase 4: Smart Medication Reminder & Alert System
- [x] Phase 5: Family & Caregiver Circle
- [x] Phase 6: Doctor Appointment Scheduling & Coordination
- [x] Phase 7: Health Vitals & Clinical Readings (Blood Pressure, Glucose, SpO2, Heart Rate)
- [ ] Phase 8: Emergency SOS Workflow & Verification

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

