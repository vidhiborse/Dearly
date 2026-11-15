# Dearly — Project Status

**Current Phase:** Phase 3 (Medication Management & Dose Tracking)  
**Status:** Completed & Verified  
**Date:** November 15, 2026  
**Repository:** [github.com/vidhiborse/Dearly](https://github.com/vidhiborse/Dearly)

---

## 1. Executive Summary

Phase 3 implements a complete, clinically sound, and accessible **Medication Management & Dose Tracking module** for Dearly (*Care that stays close.*). The system provides full medication CRUD for caregivers, multi-filter medication lists, day-period schedule grouping (Morning, Afternoon, Evening, Night), duplicate-proof dose status logging (`taken`, `skipped`, `pending`, `missed`), mathematical adherence metric computation strictly excluding future doses, in-app overdue dose warnings without doubling advice, and strict backend RBAC guards.

---

## 2. Completed in Phase 3

### A. Medication CRUD & Input Validation
- Implemented comprehensive input validation in [services/medication_service.py](file:///d:/Dearly/services/medication_service.py):
  - Required fields: `medicine_name`, `dosage`, `medication_type`, `frequency`, `schedule_time`, `start_date`.
  - 24-hour time validation regex (`^([01]\d|2[0-3]):([0-5]\d)$`).
  - Strict calendar date format verification (`YYYY-MM-DD`).
  - Chronological validation: rejects `end_date < start_date`.
  - Non-prescriptive guarantee: no automated drug recommendations or dosage suggestions.
- **Add Medication**: Authorized caregivers can prescribe new regimens for linked elderly wards.
- **Edit Medication**: Full details update modal/expander with pre-populated values and timestamping.
- **Deactivate Medication**: Safely deactivates medications (`active = 0`) while safeguarding all historical logs.
- **Delete Medication**: Requires explicit user confirmation checkbox; preserves historical dose logs in SQLite audit trail.

### B. Filterable Medication Registry
- Multi-state filter in [views/caregiver_view.py](file:///d:/Dearly/views/caregiver_view.py) and [views/family_view.py](file:///d:/Dearly/views/family_view.py):
  - `All Medications`
  - `Active Medications`
  - `Inactive Medications`
- Comprehensive card displays: Medication name, dosage, type (Tablet, Capsule, Syrup, etc.), scheduled time, frequency, meal timing, start/end dates, patient instructions, prescribing doctor, and stock count.

### C. Daily Schedule Grouped by Time Periods
- Dynamic period grouping standard in [services/medication_service.py](file:///d:/Dearly/services/medication_service.py):
  - **Morning**: 05:00 – 11:59
  - **Afternoon**: 12:00 – 16:59
  - **Evening**: 17:00 – 20:59
  - **Night**: 21:00 – 04:59
- Excludes medications outside active start/end date windows.
- Accessible schedule rendering across Elderly, Caregiver, and Family views.

### D. Dose Status Tracking & Duplicate Prevention
- Supports statuses: `taken`, `skipped`, `pending`, `missed`.
- Captures: `medication_id`, `elderly_user_id`, `scheduled_date`, `scheduled_time`, `actual_action_time`, `status`, `recorded_by`, and `notes`.
- Duplicate prevention: SQLite `UNIQUE(medication_id, scheduled_date, scheduled_time)` with `ON CONFLICT DO UPDATE` upsert pattern.
- Self-logging: Elderly individuals can confirm their own doses with large touch targets.
- Authorized caregiver logging: Caregivers can log doses for linked wards.
- Read-only protection: Family members cannot record or modify doses.
- Automatic inventory decrement on confirmation and restoration on reset.

### E. Adherence Summary & Analytics
- Calculation standard:
  $$\text{Adherence Rate} = \left(\frac{\text{Taken Doses}}{\text{Total Due Doses}}\right) \times 100$$
- Strict exclusion: Doses scheduled in the future (future dates, or today's doses after current local time) are strictly excluded from Total Due.
- Zero-misleading empty states: If Total Due is 0, displays a reassuring empty state rather than a false 0% or 100%.

### F. Overdue Dose In-App Identification
- Identifies active doses scheduled for today where `schedule_time < current_local_time` and status is not taken or skipped.
- Renders high-contrast alert banner showing medication name, scheduled time, and elderly person's name.
- Strict safety disclaimer: explicitly instructs users never to take extra medicines or double up doses.
- No external notification claims (SMS/WhatsApp deferred to later phases).

---

## 3. Database Schema Modifications

Database file: [data/dearly.db](file:///d:/Dearly/data/dearly.db)
Idempotent migrations in [database.py](file:///d:/Dearly/database.py):
- `medications`: Added `medication_type` (`TEXT DEFAULT 'Tablet'`), `prescribing_doctor` (`TEXT`), `notes` (`TEXT`), `updated_at` (`TEXT`).
- `medication_logs`: Added `actual_action_time` (`TEXT`).

---

## 4. Test Evidence

Executed 17-scenario Phase 3 test suite in [test_phase3_meds.py](file:///d:/Dearly/test_phase3_meds.py) and full regression suite across all 40 tests:
```powershell
python -m unittest test_phase2_auth.py test_app.py test_phase3_meds.py
........................................
Ran 40 tests in 5.946s — OK
```

| Test Case | Scenario Tested | Result |
|---|---|---|
| `test_01` | Add medication successfully | Passed |
| `test_02` | Reject missing required fields | Passed |
| `test_03` | Reject invalid dates & chronological inversion | Passed |
| `test_04` | Display active medications filter | Passed |
| `test_05` | Display inactive medications filter | Passed |
| `test_06` | Edit existing medication details & timestamps | Passed |
| `test_07` | Deactivate medication while preserving past logs | Passed |
| `test_08` | Prevent unauthorized medication modifications (RBAC) | Passed |
| `test_09` | Display correct daily schedule grouped by period | Passed |
| `test_10` | Mark dose as taken with actual action time | Passed |
| `test_11` | Mark dose as skipped with notes | Passed |
| `test_12` | Prevent duplicate dose records via SQLite UPSERT | Passed |
| `test_13` | Calculate adherence correctly: (Taken / Total Due) * 100 | Passed |
| `test_14` | Identify overdue doses using current local time | Passed |
| `test_15` | Exclude future scheduled doses from overdue check | Passed |
| `test_16` | Verify medication records persist after process restart | Passed |
| `test_17` | Verify existing authentication & profile regression | Passed |

---

## 5. Files Created & Modified in Phase 3

### Created:
1. **[test_phase3_meds.py](file:///d:/Dearly/test_phase3_meds.py)**: Mandatory 17-scenario automated test suite.

### Modified:
1. **[database.py](file:///d:/Dearly/database.py)**: Schema enhancements and dynamic column migrations for medications and medication logs.
2. **[services/medication_service.py](file:///d:/Dearly/services/medication_service.py)**: Input validation, CRUD, period grouping, UPSERT dose tracking, adherence calculation, and overdue detection.
3. **[services/permissions.py](file:///d:/Dearly/services/permissions.py)**: Robust ID type conversion and write access guards.
4. **[views/caregiver_view.py](file:///d:/Dearly/views/caregiver_view.py)**: Overview overdue banner, 3-tab Medication Monitoring (Daily Schedule, Medications Registry with All/Active/Inactive filters & Edit modals, Add Medication form).
5. **[views/elderly_view.py](file:///d:/Dearly/views/elderly_view.py)**: Overdue dose patient notice, time-of-day grouped schedule on Home and My Medicines, large touch target action buttons.
6. **[views/family_view.py](file:///d:/Dearly/views/family_view.py)**: 7-day adherence metrics (excluding future doses), grouped schedule, and read-only prescription registry.
7. **[PROJECT_STATUS.md](file:///d:/Dearly/PROJECT_STATUS.md)**: Updated Phase 3 status report.
8. **[FEATURE_CHECKLIST.md](file:///d:/Dearly/FEATURE_CHECKLIST.md)**: Verified requirement checklist.
9. **[EVALUATION_MAPPING.md](file:///d:/Dearly/EVALUATION_MAPPING.md)**: Added jury evaluation flow for Medication Management.
10. **[README.md](file:///d:/Dearly/README.md)**: Updated architecture diagrams and test instructions.

---

## 6. Known Limitations & Strict Scope

- **No Push / SMS / WhatsApp Reminders**: In-app notifications only, as mandated for Phase 3.
- **No AI Prescribing**: Dearly is a coordination tool, not an automated prescribing system.
- **No Hard Deletion of Historical Data**: Discontinued medications are preserved in the clinical log.

---

## 7. Roadmap & Next Phase

- [x] Phase 1: Professional UI/UX Foundation & Accessible Role Shell
- [x] Phase 2: Authentication, Multi-Role Registration & RBAC
- [x] Phase 3: Medication Management, Dose Tracking & Adherence
- [ ] Phase 4: Doctor Appointment Scheduling & Coordination
- [ ] Phase 5: Health Vitals & Clinical Readings (BP, Glucose, SpO2)
- [ ] Phase 6: Care Circle Escalations & Demo SOS Workflow
