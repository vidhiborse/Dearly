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
| **Elderly** | Asha Patil (74) | `elderly@dearly.demo` | High-accessibility, large-button routine, care circle invitations |
| **Caregiver** | Rahul Patil (Son) | `caregiver@dearly.demo` | Primary caregiver lead, medication CRUD, care notes, escalations |
| **Family** | Neha Patil (Daughter) | `family@dearly.demo` | Peace-of-mind dashboard, adherence trends, shared care notes |

*Note: You can switch roles instantly at any time using the "Switch Role for Evaluation" buttons located in the left sidebar.*

### Testing Medication Management (Phase 3)
1. **Caregiver Perspective (`caregiver@dearly.demo`)**:
   - Go to **"Medication Monitoring"**.
   - Notice the 3 functional tabs: **"Daily Schedule"**, **"Medications Registry"**, and **"Add Medication"**.
   - **Daily Schedule Tab**: See today's doses grouped into *Morning*, *Afternoon*, *Evening*, and *Night*. Click **"Mark Taken"**, **"Mark Missed"**, or **"Skip"** to see instant status update and inventory decrement.
   - **Medications Registry Tab**: Filter by *All*, *Active*, or *Inactive*. Expand any medication to edit dosage, frequency, or schedule, or deactivate/reactivate. Test delete confirmation checkbox.
   - **Add Medication Tab**: Prescribe a new medication with validation for time format and dates.
2. **Elderly Perspective (`elderly@dearly.demo`)**:
   - Go to **"Home"**: Note the gentle overdue banner if past due, and today's schedule grouped by time of day.
   - Go to **"My Medicines"**: Large 20px readable controls. Click **"Mark as Taken"** or **"Skip this dose"**; click **"Undo / Reset"** if taken.
3. **Family Perspective (`family@dearly.demo`)**:
   - Go to **"Medicines"**: Review 7-day adherence rate (strictly excluding future doses), schedule grouped by period, and read-only prescription registry.

### Testing Reminders, Alerts & Caregiver Escalation (Phase 4)
1. **Notification Center Navigation**:
   - Log in as any persona. Notice navigation menu item: **"Reminders & Alerts"** (with live unread badge `[N new]`).
2. **Caregiver View (`caregiver@dearly.demo`)**:
   - Click **"Reminders & Alerts"**.
   - **Active Reminders Tab**: Inspect deterministic status badges (`Upcoming`, `Due Now`, `Overdue`, `Completed`).
   - **Caregiver Escalations Tab**: View overdue doses escalated to Rahul. Notice detailed cards showing patient name, scheduled time, dosage, and overdue duration.
   - Click **"Acknowledge Notice"**: Notice acknowledgement timestamp and caregiver name recorded, but note that the medication remains *unconfirmed* (separating awareness from dose intake).
   - Click **"Confirm Dose Taken"**: Instantly transitions dose to `taken`, resolves escalation, and decrements stock.
3. **Elderly View (`elderly@dearly.demo`)**:
   - Click **"Reminders & Alerts"**.
   - **Notifications Stream Tab**: View in-app alerts filtered by *Due Now*, *Overdue*, and *Completed*.
   - Click **"Mark as Read"** or **"Mark All as Read"** to update live counters.
   - **Reminder Settings Tab**: Adjust the grace period slider (e.g., 15 min), toggle in-app alerts, or change time format between 12-hour and 24-hour military display.

### Testing Family & Caregiver Circle (Phase 5)
1. **Care Circle Navigation**:
   - Select **"Care Circle"** from the left navigation sidebar.
   - Notice live invitation counter if any pending invites are awaiting approval (`Care Circle [N new]`).
2. **Care Circle Network Tab**:
   - Inspect the **Designated Primary Caregiver** banner highlighting Rahul Patil as Primary Lead.
   - Inspect the **Authorized Caregivers** and **Family Members** columns.
   - For caregivers/elderly: Test the **"Set as Primary"** button or **"Remove Connection"** expander with confirmation.
3. **Invite Member Tab**:
   - Enter an email of a registered user (or register a test user first).
   - Select relationship (`Son`, `Daughter`, `Spouse`, `Professional caregiver`), role category (`Caregiver` vs `Family`), and permission level (`Editor` vs `Viewer`).
   - Submit invitation. Notice the pending invitation appears immediately under "Dispatched Pending Invitations".
4. **My Invitations Tab**:
   - Switch to the invited user account.
   - Open **"Care Circle"** -> **"My Invitations"**.
   - Inspect the invitation card showing elderly ward name, inviter, relationship, and permission level.
   - Click **"Accept"** to activate the connection, or **"Decline"** to reject without granting profile access.
5. **Shared Care Notes Tab**:
   - Click **"Write a New Care Note"**: Enter a title, select a category (`routine`, `observation`, `diet`), choose visibility (`All Circle Members` vs `Caregivers Only`), and save.
   - Switch to **Family Member (`family@dearly.demo`)**: Verify that notes marked `caregivers_only` are hidden, while `circle` notes are readable.
6. **Care Activity Timeline Tab**:
   - Inspect the chronological audit stream of real events.
   - Filter by event type (`Medication & Dose Confirmations`, `Reminders & Alerts`, `Care Circle Updates`, `Care Notes`).

### Testing Doctor Appointment Management (Phase 6)
1. **Appointments Navigation**:
   - Click **"Appointments"** in the sidebar navigation across any role.
2. **Upcoming Visits Tab**:
   - Notice the prominent **"Today's Appointments"** banner if a visit is scheduled for today.
   - Notice the multi-filter bar: filter by status (`all`, `today`, `upcoming`, `completed`, `cancelled`, `missed`), custom date ranges, and doctor/clinic name.
   - Expand any visit card:
     - See full clinical metadata (doctor specialization, clinic address, visit purpose, pre-visit notes).
     - Test the **"Reschedule Visit"** action: Pick a new future date and time, click Reschedule, and see instant update and reminder reset.
     - Test the **"Mark Completed & Add Visit Summary"** action: Enter doctor instructions and click Mark Completed.
     - Test the **"Cancel Appointment"** action: Provide cancellation reason and confirm.
3. **Schedule New Visit Tab**:
   - As Senior or Caregiver (`elderly@dearly.demo` or `caregiver@dearly.demo`), fill out the accessible scheduling form.
   - Enter Doctor Name (e.g., `Dr. Sarah Jenkins`), Specialization (`Cardiology`), Hospital (`Metro Care Heart Center`), Date, Time, Appointment Type (`Specialist consultation`), Location, and Reason.
   - Submit and verify the visit appears immediately under Upcoming Visits and in the Care Activity timeline.
4. **Calendar & Date View Tab**:
   - Click **"Calendar & Date View"** to inspect appointments grouped by date on an agenda grid.
5. **Visit History & Summaries Tab**:
   - Inspect past, completed, cancelled, and missed visits with doctor instructions and post-visit notes.
6. **Role-Based Permissions**:
   - Switch to **Family Member (`family@dearly.demo`)**: Notice that the appointment schedule is visible for complete peace of mind, but modification and cancellation controls are disabled.

### Testing Health Monitoring & Records (Phase 7)
1. **Health Records Navigation**:
   - Select **"Health Records"** (Caregiver), **"My Health"** (Senior), or **"Health Summary"** (Family) from the sidebar navigation.
2. **Health Summary & Latest Vitals Tab**:
   - Inspect the prominent medical disclaimer notice emphasizing that Dearly is for personal tracking and care coordination, not diagnosis.
   - Inspect the 6-vital card grid: Blood Pressure, Blood Sugar, Heart Rate, Oxygen Saturation (SpO2), Weight, and Body Temperature.
   - Notice the neutral reference range status badge (`Within standard reference range` or `Outside standard reference range`).
   - Open the informational reference range guide expander.
3. **Health Trends & Charts Tab**:
   - Select measurement from dropdown (`Blood Pressure`, `Blood Sugar`, `Weight`, `Heart Rate`, `Oxygen Saturation (SpO2)`).
   - Inspect the interactive Plotly charts with clear shaded reference zones.
   - If only 1 reading exists for a vital, note the informative message stating that at least 2 readings are needed to plot a trend line.
4. **Record History & Audit Tab**:
   - Filter records by measurement type and date range.
   - Click **"Export Filtered Records to CSV"** to download the RFC-compliant dataset.
   - Expand any reading: inspect the immutable audit history.
   - For Senior/Caregiver: Test the **"Correct this Health Record"** form with a correction reason. Notice that the update marks the record as corrected and records original values in the audit table.
5. **Record New Measurement Tab**:
   - Log a new measurement (e.g. Blood Pressure: Systolic `120`, Diastolic `80`; or Fasting Blood Sugar: `100 mg/dL`).
   - Notice option to link reading directly to a scheduled doctor appointment.
6. **Wellbeing Observations Tab**:
   - Log an observation (e.g., sleep quality or mobility note).
   - Review chronological observation feed with category badges and author attribution.
7. **Permission Enforcement**:
   - Switch to **Family Member (`family@dearly.demo`)**: Notice full observability across summaries, trends, history, and CSV export, while recording and correcting controls are disabled.

### Testing Emergency SOS & Contacts (Phase 8)
1. **Emergency SOS Navigation**:
   - Click **"Emergency SOS"** (Caregiver / Family) or **"Emergency SOS"** / **"Emergency Contacts"** (Senior) from the navigation sidebar.
   - If an emergency is open, observe the dynamic red `[ACTIVE ALERT]` badge in the navigation menu and the prominent top alert banner across dashboard views.
2. **Safety Disclaimer & Indian Helplines**:
   - Inspect the prominent safety disclaimer prominently rendered on the SOS activation page:
     > *"Dearly SOS sends in-app alerts to your authorized care circle. It does not guarantee that someone will receive or respond to an alert. For immediate danger or a medical emergency in India, call 112 or your local emergency service directly."*
   - Review the official Indian helpline cards: **112** (National Emergency), **108 / 102** (Ambulance), **100** (Police), and **14567** (Elderline).
3. **Senior SOS Activation Workflow (`elderly@dearly.demo`)**:
   - Click the large high-contrast **"TRIGGER EMERGENCY SOS"** button.
   - Notice the two-step confirmation dialog with optional location/situation notes.
   - Confirm activation: an active emergency card appears immediately with `pending` status, and an in-app notification is dispatched to all active care circle members.
   - Notice that clicking activate again is blocked with a duplicate prevention notice.
4. **Caregiver Response & Status Coordination (`caregiver@dearly.demo`)**:
   - Open **"Emergency SOS"**: notice the active emergency request card showing Asha Patil, trigger timestamp, and notes.
   - Test **"Acknowledge Emergency"**: enter a response note (e.g., "Received alert, checking on mother now") and click Acknowledge. Status updates to `acknowledged`.
   - Test **"Update Assistance Status"**: enter progress note and click Set Assistance In Progress. Status transitions to `assistance_in_progress`.
   - Test **"Resolve Emergency"**: enter resolution notes (e.g., "Visited in person, senior is safe") and confirm. Active alert clears.
5. **Emergency Contacts Directory**:
   - Open the **"Emergency Contacts Directory"** tab.
   - Inspect pre-seeded contacts: Rahul Patil (Primary), Neha Patil, Dr. Sunita Kulkarni.
   - Test adding a contact with validation (phone >= 7 digits).
   - Test **"Set as Primary"**: verify that selecting a contact as primary automatically clears previous primary contacts.
   - Switch to **Family Member (`family@dearly.demo`)**: verify read-only visibility (contact management forms disabled).
6. **Emergency Assistance History**:
   - Open the **"Emergency Assistance History"** tab.
   - Inspect chronological requests and expand any request card to review the full transition audit trail from `emergency_status_history`.

### Testing Analytics & Reports (Phase 9)
1. **Analytics Navigation**:
   - Click **"Analytics & Reports"** from the navigation sidebar across any role.
2. **Ward & Time Period Filtering**:
   - For caregivers/family: Select the care recipient from the dropdown (e.g. `Asha Patil`).
   - Change report time period: `Last 30 Days`, `Last 7 Days`, `Last 90 Days`, or `Custom Range`. Notice that all tabs, charts, and metrics immediately update to match the active window.
3. **Overview Dashboard Tab**:
   - Inspect the executive KPI grid: Overall Adherence %, Doses Taken vs Due, Skipped & Overdue counts, and Appointments Completed.
   - Verify that future scheduled doses are strictly excluded from due counts.
   - Review clinical safety disclaimer stating that analytics are non-diagnostic.
4. **Medication Adherence Tab**:
   - Review the stacked daily dose confirmations bar chart with secondary adherence trend line.
   - Inspect the **Medication-Wise Performance** table showing due, taken, skipped, and overdue metrics per prescription.
   - Inspect the **Weekly Adherence Summary** aggregation.
5. **Health Trends Tab**:
   - Select a vital from the dropdown (e.g., `Blood Pressure`, `Blood Sugar`, `Weight`, `Heart Rate`).
   - If multiple units exist (e.g. `kg` vs `lb`), select the desired unit and verify that incompatible units are strictly separated and not combined.
   - Inspect the summary KPI cards (Systolic/Diastolic for BP; Min/Max/Avg for others) and the interactive Plotly trend line with normal reference bands.
6. **Appointment Analytics Tab**:
   - Inspect the appointment status counters (Completed, Upcoming, Cancelled, Missed). Notice cancelled visits are never counted as completed.
   - Inspect the **Appointments by Type** horizontal bar chart and **Monthly Appointment History** chart.
7. **Care Activity & CSV Export Tab**:
   - Inspect the **Activity Volumes by Care Category** bar chart.
   - Filter activity logs by category (Medication, Reminders, Care Circle, Notes, Emergency SOS).
   - Click **"DOWNLOAD ANALYTICS REPORT (CSV)"**: Inspect the downloaded RFC-4180 CSV file to verify full care summaries, health measurements, and zero exposure of password hashes or tokens.

---

## 2. Evaluation Criteria Mapping

### Criterion 1: Product Design & Healthcare Usability
- **Design System Documentation**: [DESIGN.md](file:///d:/Dearly/DESIGN.md) documents color tokens, typography scales, spacing grids, and anti-patterns.
- **Visual Contrast & Tone**: Calm palette `#234B70`, `#FFFFFF`, `#F5F8FC` with zero neon gimmicks, zero emojis, and WCAG AAA contrast ratios.
- **Elderly-First Accessibility**:
  - Body text is scaled to 18px; important dosage instructions are 20px–22px.
  - Generous touch targets (`min-height: 48px`).
  - High-clarity button styling without distracting nested borders.

### Criterion 2: Authentication, Security & RBAC (Phase 2)
- **User Registration**: Implemented in [services/user_service.py](file:///d:/Dearly/services/user_service.py) with validation for required fields, email format regex, duplicate detection, and password confirmation.
- **Bcrypt Password Hashing**: Implemented in [database.py](file:///d:/Dearly/database.py) using `bcrypt` (work factor 12) with salt generation.
- **Role-Based Access Control (RBAC)**: Backend verification in [services/permissions.py](file:///d:/Dearly/services/permissions.py) prevents cross-patient record tampering or role escalation.
- **Profile Management**: Implemented in [views/profile_view.py](file:///d:/Dearly/views/profile_view.py) allowing users to view account attributes and update contact details with immediate persistence.

### Criterion 3: Medication Management & Dose Tracking (Phase 3)
- **Medication CRUD**: Full support in [services/medication_service.py](file:///d:/Dearly/services/medication_service.py) for adding, editing, deactivating, and deleting medications with input validation.
- **Time-Period Grouped Schedule**: Categorization into Morning (05:00-11:59), Afternoon (12:00-16:59), Evening (17:00-20:59), and Night (21:00-04:59).
- **Duplicate-Proof Dose Logging**: SQLite `ON CONFLICT(medication_id, scheduled_date, scheduled_time) DO UPDATE` ensures zero duplicated logs while recording `actual_action_time`.
- **Clinically Accurate Adherence**: Formula strictly excludes future scheduled doses to avoid artificial inflation or deflation.
- **Safe Overdue Alerts**: In-app overdue warnings showing patient name, medication, and scheduled time with explicit guidance NEVER to double doses.

### Criterion 4: Smart Medication Reminders & Caregiver Escalation (Phase 4)
- **Deterministic Status Logic**: Evaluates `upcoming`, `due_now`, `overdue`, `completed`, and `skipped` using exact schedule and grace window math in [services/reminder_service.py](file:///d:/Dearly/services/reminder_service.py).
- **Configurable Grace Period**: Supports custom grace windows (5 to 60 minutes) stored per-user in SQLite `reminder_settings`.
- **In-App Notification Center**: Dedicated notification management interface in [views/notification_view.py](file:///d:/Dearly/views/notification_view.py) with unread filtering, category filtering, and one-click mark-as-read.
- **Caregiver Escalation System**: When doses are overdue past grace periods, alerts are automatically dispatched to caregivers linked in `care_circle` with `editor` privileges.
- **Strict Clinical Non-Conflation**: Escalation acknowledgement records caregiver oversight without falsifying dose intake logs.

### Criterion 5: Family & Caregiver Circle (Phase 5)
- **Care Circle Network**: Multi-ward coordination connecting seniors, family members, and caregivers in [services/care_circle_service.py](file:///d:/Dearly/services/care_circle_service.py).
- **In-App Invitation Lifecycle**: Two-sided invitation and approval workflow stored in SQLite `care_invitations`. Pending invitations grant zero profile access.
- **Single Primary Caregiver Rule**: Enforced server-side single primary caregiver designation with safe unassignment.
- **Shared Care Notes with Privacy**: Granular visibility controls (`circle` for full circle, `caregivers_only` hidden from family viewers) in `care_notes`.
- **Care Activity Timeline**: Complete chronological audit stream with category and date filtering in [services/activity_service.py](file:///d:/Dearly/services/activity_service.py).

### Criterion 6: Doctor Appointment Management (Phase 6)
- **Appointment Lifecycle & Scheduling**: Complete CRUD, date/time validation, past-date restriction, and support for 5 appointment types in [services/appointment_service.py](file:///d:/Dearly/services/appointment_service.py).
- **Clinical Summaries**: Support for pre-visit reasons and post-visit doctor summaries / clinical instructions.
- **Dual Deterministic Reminders**: 1-day-before and 1-hour-before in-app alerts dispatched to patient and care circle, with unique constraint duplicate suppression.
- **Calendar & Historical Tracking**: Date-grouped appointment agenda and archived history in [views/appointment_view.py](file:///d:/Dearly/views/appointment_view.py).
- **Server-Side RBAC**: Authorized modifications restricted to seniors and editor caregivers; read-only observability enforced for family members.

### Criterion 7: Health Monitoring & Clinical Records (Phase 7)
- **Supported Measurement Types**: Blood Pressure, Blood Sugar, Weight, Heart Rate, Oxygen Saturation (SpO2), and Body Temperature in [services/health_service.py](file:///d:/Dearly/services/health_service.py).
- **Clinical Validation**: Rejection of physically impossible values (non-numeric, negative values, diastolic >= systolic) and unit validation.
- **Informational Reference Guidelines**: Strictly non-diagnostic evaluation flags with neutral guidance to consult a doctor.
- **Plotly Visualizations**: Multi-vital trend lines with reference bands and graceful single-point empty state handling.
- **Correction Audit Trail**: Non-destructive corrections storing previous values in `health_record_audit`.
- **Qualitative Wellbeing Observations**: Category-tagged routine logs with appointment linkage in `health_observations`.
- **CSV Data Export**: Secure, permission-checked RFC-compliant CSV generation.

### Criterion 8: Emergency SOS Workflow & Contact Management (Phase 8)
- **Accessible Two-Step Activation**: Large high-contrast SOS button with deliberate confirmation dialog to eliminate accidental triggers in [views/emergency_view.py](file:///d:/Dearly/views/emergency_view.py).
- **Mandatory Safety Disclaimer & Helplines**: Prominent clinical safety disclaimer and quick-reference directory for official Indian helplines (112, 108/102, 100, 14567).
- **Active Circle Routing & Duplicate Guard**: Automatic in-app alerts routed to active Care Circle members while blocking duplicate triggers in [services/emergency_service.py](file:///d:/Dearly/services/emergency_service.py). Revoked/inactive members receive zero alerts.
- **Full Status Lifecycle Coordination**: Structured progression (`pending` -> `acknowledged` -> `assistance_in_progress` -> `resolved` / `cancelled`) with response notes and audit trail in `emergency_status_history`.
- **Emergency Contact Management**: Complete CRUD supporting validated phone numbers, priority ordering, and single-primary contact rule.
- **Privacy & Role Enforcement**: Caregivers with editor permissions can manage contacts and response status; family viewers maintain read-only awareness.

### Criterion 9: Healthcare Analytics & Reporting (Phase 9)
- **Executive Overview Analytics**: Real KPI metrics for adherence %, scheduled doses, taken, skipped, overdue, and appointment counts in [services/analytics_service.py](file:///d:/Dearly/services/analytics_service.py).
- **Medication Adherence Mathematics**: Strictly excludes future scheduled doses and deduplicates entries; computes daily and weekly adherence trends.
- **Clinical Vital Trends**: Plotly charts with reference bands, metric summaries (min, max, avg), and strict separation of incompatible units in [views/analytics_view.py](file:///d:/Dearly/views/analytics_view.py).
- **Appointment Insights**: Categorization into completed, upcoming, cancelled, and missed; monthly history and type distribution. Cancelled visits excluded from completed count.
- **Care Activity Breakdown**: Category distribution and privacy-sanitized activity feeds for family members.
- **RFC-4180 CSV Export**: Complete downloadable care summary reports with zero exposure of sensitive authentication credentials.
- **Non-Diagnostic Safety Policy**: Prominent disclaimer stating that analytics and charts are informational and never replace professional medical judgment.

### Criterion 10: Automated Testing & Verification
- **Test Suites**:
  - `test_phase9_analytics.py`: 23 mandatory Phase 9 tests covering adherence math, future dose exclusion, zero-dose safety, deduplication, health trends, unit separation, appointment counts, activity filtering, RBAC, CSV export, and persistence.
  - `test_phase8_emergency.py`: 20 mandatory Phase 8 tests covering SOS activation, confirmation, disclaimer, duplicate guard, notifications, status history, contacts CRUD, and regression.
  - `test_phase7_health.py`: 22 mandatory Phase 7 tests covering all measurement types, validation, audit trails, charts, CSV export, and RBAC.
  - `test_phase6_appts.py`: 21 mandatory Phase 6 tests covering appointment CRUD, past-date validation, rescheduling, reminders, and RBAC.
  - `test_phase5_circle.py`: 20 mandatory Phase 5 tests covering invitation workflow, permission levels, care notes privacy, and primary caregiver designation.
  - `test_phase4_reminders.py`: 17 mandatory Phase 4 tests covering reminder statuses, grace period boundaries, caregiver escalation, and duplicate prevention.
  - `test_phase3_meds.py`: 17 mandatory Phase 3 tests covering CRUD, date validation, period grouping, and adherence mathematics.
  - `test_phase2_auth.py`: 15 authentication & RBAC unit tests.
  - `test_app.py`: 8 end-to-end integration tests.
  - Total: **163 passing automated tests** with 0 errors and 0 failures.
