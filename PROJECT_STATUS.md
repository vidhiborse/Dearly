# Dearly — Project Status

**Current Phase:** Phase 9 (Analytics & Reports)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 9 implements a comprehensive, accessible, and clinically grounded **Analytics & Reports** module for Dearly (*Care that stays close.*). The system transforms medication doses, health vitals, appointments, and care circle activities into actionable insights for older adults, caregivers, and family members.

Key capabilities delivered:
1. **Analytics & Reports Dashboard**: Dedicated 5-tab interface across all user roles:
   - Senior: Personal adherence insights, vital trends, appointment history, and reports download.
   - Caregiver: Multi-ward recipient selector, date-range filtering, adherence breakdowns, and CSV export.
   - Family Member: Full observability over permitted adherence, appointments, and vitals with read-only safeguards.
2. **Executive Overview KPIs**: Real calculated metrics strictly derived from stored database records:
   - Medication adherence percentage (`(Taken Doses / Total Due Doses) x 100`).
   - Total scheduled doses due vs taken doses.
   - Skipped doses and overdue doses.
   - Upcoming and completed doctor appointments.
   - Total recorded health readings and care log events.
3. **Rigorous Medication Adherence Analytics**:
   - Strictly excludes future scheduled doses from due counts.
   - Deduplicates identical dose entries to prevent double-counting.
   - Handles zero-dose periods safely (returns `has_data = False`, `adherence_percentage = None`) without division errors.
   - Medication-wise breakdown showing adherence % and due/taken counts per prescription.
   - Interactive Plotly stacked daily dose confirmation chart with secondary adherence trend line.
   - Weekly adherence trend aggregation.
4. **Health Trend Analytics**:
   - Full integration with Phase 7 clinical vitals (Blood Pressure, Blood Sugar, Weight, Heart Rate, Oxygen Saturation, Body Temperature).
   - Dynamic measurement type selector and unit selector.
   - **Unit Isolation**: Incompatible measurement units (e.g., `mg/dL` vs `mmol/L`, or `kg` vs `lb`) are separated and never blended numerically.
   - Summary cards displaying minimum, maximum, and average values (systolic/diastolic for Blood Pressure).
   - Informative empty states when insufficient data exists (< 2 measurements).
5. **Doctor Appointment Analytics**:
   - Breakdown of total, upcoming, completed, cancelled, and missed visits.
   - **Strict Rule**: Cancelled appointments are strictly excluded from completed counts.
   - Monthly appointment volume distribution chart.
   - Consultation type distribution chart (e.g., General check-up, Specialist, Follow-up).
6. **Care Activity Analytics**:
   - Categorized activity breakdown (Medication, Reminders & Escalations, Care Circle, Notes, Emergency SOS).
   - Distribution bar chart by care activity category.
   - **Privacy Enforcement**: Restricted caregiver-only notes are sanitized for family viewers.
7. **RFC-4180 Compliant CSV Export**:
   - Comprehensive CSV report download incorporating executive metrics, medication breakdown, appointments, vitals, and activity logs.
   - UTF-8 encoding, clear filenames (`dearly_report_{ward_id}_{start_date}_to_{end_date}.csv`), and clean handling of empty datasets.
   - Zero exposure of sensitive authentication credentials (passwords, salts, tokens).
8. **Clinical Safety & Non-Diagnostic Guardrails**:
   - Prominently displays non-diagnostic medical disclaimer across all analytics views and exports.
   - Zero automated risk scoring, disease diagnosis, or treatment alteration claims.
9. **100% Test Coverage**: 23 of 23 mandatory Phase 9 test scenarios passing; 163 of 163 total tests passing across all project test suites with 0 errors and 0 failures. Zero emojis across all code, tests, and documentation.

---

## 2. Completed in Phase 9

### A. Analytics Navigation & Role Access
- Added `"Analytics & Reports"` to navigation across all user roles:
  - Elderly: Views own reports and personal adherence trends.
  - Caregiver: Selects from linked elderly wards; views detailed breakdowns and exports reports.
  - Family: Observes permitted summaries and health trends with read-only safeguards.
- Enforced server-side permissions: `enforce_elderly_access(user, elderly_user_id, write_access=False)` on every query.

### B. Overview Dashboard
- Executive KPI card grid:
  - Overall Adherence Rate
  - Doses Taken / Due
  - Skipped & Overdue
  - Completed & Upcoming Appointments
- Secondary summary cards explaining adherence calculation standards and data volume counts.

### C. Medication Adherence Analysis
- Formula: `Adherence (%) = (Taken Doses / Total Due Doses) x 100`.
- Daily dose confirmations and adherence % Plotly chart.
- Medication-wise performance table (Medication, Dosage, Total Due, Taken, Skipped, Overdue, Adherence Rate, Status).
- Multi-week adherence trend aggregation table.

### D. Health Trend Analytics
- Multi-vital selector with unit isolation.
- Interactive Plotly chart with shaded reference zones.
- Graceful handling for single-point readings with informative guidance.
- Filterable readings log table with recorded timestamps and actor attribution.

### E. Appointment Analytics
- Metric counters: Total, Completed, Upcoming, Cancelled, Missed.
- Plotly chart for appointments by type (horizontal bar).
- Plotly stacked bar chart for monthly appointment history.
- Status-filtered appointment table.

### F. Care Activity & CSV Export
- Activity volumes by care category Plotly chart.
- Chronological activity stream with category filtering.
- One-click RFC-4180 CSV export download button.

---

## 3. Database & Performance Considerations

- **Zero Duplication**: All analytics are derived directly from existing relational tables (`medications`, `medication_logs`, `health_readings`, `appointments`, `activity_logs`, `users`).
- **Read-Only Invariance**: Generating analytics mutates zero records in the database.
- **Efficient Indexing**: Leverages existing compound indexes:
  - `idx_med_logs_scheduled` on `medication_logs(medication_id, scheduled_date)`
  - `idx_health_readings_elderly` on `health_readings(elderly_user_id, recorded_on)`
  - `idx_appointments_elderly` on `appointments(elderly_user_id, appointment_date)`
  - `idx_care_circle_elderly` on `care_circle(elderly_user_id, member_user_id)`
- **Parameterized SQL**: All date range filters and profile IDs are bound via parameters.

---

## 4. Test Evidence

Executed 23-scenario Phase 9 test suite in [test_phase9_analytics.py](file:///d:/Dearly/test_phase9_analytics.py) and full regression suite across all 163 tests:
```powershell
python -m unittest test_app.py test_phase2_auth.py test_phase3_meds.py test_phase4_reminders.py test_phase5_circle.py test_phase6_appts.py test_phase7_health.py test_phase8_emergency.py test_phase9_analytics.py
...................................................................................................................................................................
Ran 163 tests in 25.440s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | Medication adherence calculation is correct (`(Taken / Total Due) * 100`) | Passed |
| `test_02` | Future scheduled doses are strictly excluded from due counts | Passed |
| `test_03` | Zero-dose periods safely return `has_data=False` without division errors | Passed |
| `test_04` | Duplicate dose logs for the same slot are deduplicated | Passed |
| `test_05` | Taken, skipped, missed, and overdue statuses are categorized accurately | Passed |
| `test_06` | Daily adherence trend contains chronological breakdown per date | Passed |
| `test_07` | Weekly adherence trend aggregates into multi-day chunks | Passed |
| `test_08` | Medication-wise breakdown computes distinct metrics per prescription | Passed |
| `test_09` | Health trend queries actual readings and calculates stats accurately | Passed |
| `test_10` | Querying dates with no readings produces clean empty states | Passed |
| `test_11` | Incompatible measurement units are isolated and not blended | Passed |
| `test_12` | Appointment status counts are calculated correctly | Passed |
| `test_13` | Cancelled appointments are strictly excluded from completed counts | Passed |
| `test_14` | Activity analytics filters logs accurately by category | Passed |
| `test_15` | Date range filters apply strictly to metrics and records | Passed |
| `test_16` | Elderly users attempting to access another ward are blocked | Passed |
| `test_17` | Caregivers can access linked wards, but unlinked wards raise `PermissionError` | Passed |
| `test_18` | Restricted caregiver-only notes are sanitized for family viewers | Passed |
| `test_19` | CSV export contains structured care data without leaking sensitive tokens | Passed |
| `test_20` | CSV export handles zero-data periods safely with valid RFC-4180 format | Passed |
| `test_21` | Generating analytics is strictly read-only and mutates zero database rows | Passed |
| `test_22` | Full regression verification across Phase 1-8 operations | Passed |
| `test_23` | Analytics persist in SQLite and yield identical results across restarts | Passed |

---

## 5. Files Created & Modified in Phase 9

### Created:
1. **[services/analytics_service.py](file:///d:/Dearly/services/analytics_service.py)**: Decoupled analytics service (date resolution, KPI metrics, adherence breakdown, health trends, appointments, activity analytics, CSV report generator).
2. **[views/analytics_view.py](file:///d:/Dearly/views/analytics_view.py)**: Dedicated 5-tab Analytics & Reports Streamlit view (Overview, Adherence, Health Trends, Appointments, Care Activity & Export).
3. **[test_phase9_analytics.py](file:///d:/Dearly/test_phase9_analytics.py)**: Mandatory 23-scenario automated test suite.

### Modified:
1. **[services/permissions.py](file:///d:/Dearly/services/permissions.py)**: Added `"Analytics & Reports"` to `allowed_pages` across all roles; implemented `can_view_analytics()`.
2. **[app.py](file:///d:/Dearly/app.py)**: Added `"Analytics & Reports"` to role navigation shells; routed to `render_analytics_view(user)`.
3. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 9 status report.
4. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
5. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation steps for Analytics & Reports.
6. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture and test instructions.

---

## 6. Known Limitations & Strict Scope

- **Non-Diagnostic**: Analytics and trends are strictly informational for routine tracking and care coordination. Dearly never provides disease diagnoses, automated risk assessments, or clinical treatment advice.
- **No Predictive AI Models**: Adherence trends reflect actual historical data; predictive regression modeling is intentionally excluded.
- **No External Hospital Integration**: Reports operate within the application and can be exported as standard CSV files.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [x] Phase 4: Smart Medication Reminder & Alert System
- [x] Phase 5: Family & Caregiver Circle
- [x] Phase 6: Doctor Appointment Scheduling & Coordination
- [x] Phase 7: Health Vitals & Clinical Readings (BP, Glucose, SpO2)
- [x] Phase 8: Emergency SOS Workflow & Verification
- [x] Phase 9: Analytics & Reports
- [ ] Phase 10: AI Care Assistant & Daily Briefings (Pending Approval)
