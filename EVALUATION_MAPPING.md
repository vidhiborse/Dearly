# Dearly — Evaluation Mapping & Jury Guide

This document maps hackathon evaluation criteria to the Dearly codebase, implementation architecture, and user workflows.

---

## 1. Quick Evaluator Verification Guide

### Launching the Application
```powershell
streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.

### Pre-Configured Test Accounts (Password: `demo123`)
| Role | Name | Email | Primary Testing Goal |
|---|---|---|---|
| **Elderly** | Asha Patil (74) | `elderly@dearly.demo` | High-accessibility, large-button routine, emergency SOS |
| **Caregiver** | Rahul Patil (Son) | `caregiver@dearly.demo` | Multi-ward switcher, adherence tracking, medication CRUD |
| **Family** | Neha Patil (Daughter) | `family@dearly.demo` | Peace-of-mind dashboard, adherence trends, read-only medicines |

*Note: You can switch roles instantly at any time using the "Switch Role for Evaluation" buttons located in the left sidebar.*

### Testing Medication Management (Phase 3)
1. **Caregiver Perspective (`caregiver@dearly.demo`)**:
   - Go to **"Medication Monitoring"**.
   - Notice the 3 functional tabs: **"Daily Schedule"**, **"Medications Registry"**, and **"Add Medication"**.
   - **Daily Schedule Tab**: See today's doses grouped into *Morning*, *Afternoon*, *Evening*, and *Night*. Click **"Mark Taken"**, **"Mark Missed"**, or **"Skip"** to see instant status update and inventory decrement.
   - **Medications Registry Tab**: Filter by *All*, *Active*, or *Inactive*. Expand any medication to edit dosage, frequency, or schedule, or deactivate/reactivate. Test delete confirmation checkbox.
   - **Add Medication Tab**: Prescribe a new medication with validation for time format and dates.
   - Check the **"Overview"** dashboard to see the active **Overdue Medication Notice** banner if any scheduled time has passed.
2. **Elderly Perspective (`elderly@dearly.demo`)**:
   - Go to **"Home"**: Note the gentle overdue banner if past due, and today's schedule grouped by time of day.
   - Go to **"My Medicines"**: Large 20px readable controls. Click **"Mark as Taken"** or **"Skip this dose"**; click **"Undo / Reset"** if taken.
3. **Family Perspective (`family@dearly.demo`)**:
   - Go to **"Medicines"**: Review 7-day adherence rate (strictly excluding future doses), schedule grouped by period, and read-only prescription registry.

---

## 2. Evaluation Criteria Mapping

### Criterion 1: Product Design & Healthcare Usability
- **Design System Documentation**: [DESIGN.md](file:///d:/Dearly/DESIGN.md) documents color tokens, typography scales, spacing grids, and anti-patterns.
- **Visual Contrast & Tone**: Calm palette `#234B70`, `#FFFFFF`, `#F5F8FC` with zero neon gimmicks, zero emojis, and WCAG AAA contrast ratios.
- **Elderly-First Accessibility**:
  - Body text is scaled to 18px; important dosage instructions are 20px–22px.
  - Generous touch targets (`min-height: 48px`).
  - Answer within 5 seconds: Home dashboard clearly shows today's next dose, upcoming appointment, caregiver phone, and emergency alert.

### Criterion 2: Authentication, Security & RBAC (Phase 2)
- **User Registration**: Implemented in [services/user_service.py](file:///d:/Dearly/services/user_service.py) with validation for required fields, email format regex, duplicate detection, and password confirmation.
- **Bcrypt Password Hashing**: Implemented in [database.py](file:///d:/Dearly/database.py) using `bcrypt` (work factor 12) with salt generation.
- **Role-Based Access Control (RBAC)**: Backend verification in [services/permissions.py](file:///d:/Dearly/services/permissions.py) prevents cross-patient record tampering or role escalation.
- **Profile Management**: Implemented in [views/profile_view.py](file:///d:/Dearly/views/profile_view.py) allowing users to view account attributes and update their contact name and phone number with immediate SQLite persistence.
- **Session Lifecycle**: Protected routes and session cleanup on logout in [app.py](file:///d:/Dearly/app.py).

### Criterion 3: Medication Management & Dose Tracking (Phase 3)
- **Medication CRUD**: Full support in [services/medication_service.py](file:///d:/Dearly/services/medication_service.py) for adding, editing, deactivating, and deleting medications with input validation.
- **Time-Period Grouped Schedule**: Clean categorization into Morning (05:00-11:59), Afternoon (12:00-16:59), Evening (17:00-20:59), and Night (21:00-04:59).
- **Duplicate-Proof Dose Logging**: SQLite `ON CONFLICT(medication_id, scheduled_date, scheduled_time) DO UPDATE` ensures zero duplicated logs while recording `actual_action_time`.
- **Clinically Accurate Adherence**: Formula strictly excludes future scheduled doses to avoid artificial inflation or deflation. Clear empty states for unstarted regimens.
- **Safe Overdue Alerts**: In-app overdue warnings showing patient name, medication, and scheduled time with explicit guidance NEVER to double doses.
- **Audit Preservation**: Deactivating or deleting preserves prior medication administration logs.

### Criterion 4: Role-Based Application Shell & Navigation
- **Elderly Navigation**: `Home`, `My Medicines`, `Appointments`, `My Health`, `Emergency Contacts`, `My Profile`.
- **Caregiver Navigation**: `Overview`, `Elderly Profiles`, `Medication Monitoring`, `Appointments`, `Health Records`, `Activity History`, `My Profile`.
- **Family Navigation**: `Overview`, `Care Updates`, `Medicines`, `Appointments`, `Health Summary`, `My Profile`.

### Criterion 5: Automated Testing & Verification
- **Test Suites**:
  - `test_phase3_meds.py`: 17 mandatory Phase 3 tests covering CRUD, date validation, period grouping, adherence mathematics, overdue exclusion, and persistence.
  - `test_phase2_auth.py`: 15 authentication & RBAC unit tests.
  - `test_app.py`: 8 end-to-end integration tests.
  - Total: **40 passing automated tests**.
