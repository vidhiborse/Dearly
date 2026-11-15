# Dearly — Evaluation Mapping & Jury Guide

This document maps hackathon evaluation criteria to the Dearly codebase, implementation architecture, and user workflows.

---

## 1. Quick Evaluator Verification Guide

### Launching the Application
```powershell
streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.

### Test Credentials
All demo profiles use password: `demo123`

| Role | Name | Email | Primary Testing Goal |
|---|---|---|---|
| **Elderly** | Asha Patil (74) | `elderly@dearly.demo` | High-accessibility, large button doses, emergency SOS |
| **Caregiver** | Rahul Patil (Son) | `caregiver@dearly.demo` | Ward switcher, adherence tracking, missed-dose escalation |
| **Family** | Neha Patil (Daughter) | `family@dearly.demo` | Peace-of-mind dashboard, adherence trends, AI care briefing |

*Note: You can switch roles instantly at any time using the "Switch Role for Evaluation" buttons located in the left sidebar.*

---

## 2. Evaluation Criteria Mapping

### Criterion 1: Product Design & Healthcare Usability
- **Design System Documentation**: [DESIGN.md](file:///d:/Dearly/DESIGN.md) documents color tokens, typography scales, spacing grids, and anti-patterns.
- **Visual Contrast & Tone**: Calm palette `#234B70`, `#FFFFFF`, `#F5F8FC` with zero neon gimmicks, zero emojis, and WCAG AAA contrast ratios.
- **Elderly-First Accessibility**:
  - Body text is scaled to 18px; important dosage instructions are 20px–22px.
  - Generous touch targets (`min-height: 48px`).
  - Answer within 5 seconds: Home dashboard clearly shows today's next dose, upcoming appointment, caregiver phone, and emergency alert.

### Criterion 2: Role-Based Application Shell & Navigation
- **Elderly Navigation**:
  - Menu: `Home`, `My Medicines`, `Appointments`, `My Health`, `Emergency Contacts`.
  - Implemented in [views/elderly_view.py](file:///d:/Dearly/views/elderly_view.py).
- **Caregiver Navigation**:
  - Menu: `Overview`, `Elderly Profiles`, `Medication Monitoring`, `Appointments`, `Health Records`, `Activity History`.
  - Implemented in [views/caregiver_view.py](file:///d:/Dearly/views/caregiver_view.py).
- **Family Navigation**:
  - Menu: `Overview`, `Care Updates`, `Medicines`, `Appointments`, `Health Summary`.
  - Implemented in [views/family_view.py](file:///d:/Dearly/views/family_view.py).
- **Session State & Routing**: Managed cleanly in [app.py](file:///d:/Dearly/app.py#L31-L98) with persistent role state across reruns.

### Criterion 3: Software Architecture & Maintainability
- **Decoupled Architecture**:
  - `services/`: Encapsulates business logic, parameterized SQLite queries, and audit logging.
  - `views/`: Dedicated view files per role with reusable components in `views/common.py`.
- **Database Schema & Migrations**: Implemented in [database.py](file:///d:/Dearly/database.py) with foreign keys, indexes, and idempotent demo data seeding.
- **Automated Test Suite**: [test_app.py](file:///d:/Dearly/test_app.py) contains 8 unit and integration tests verifying authentication, ward access, dose logging, appointments, vitals, permissions, emergency alerts, and AI summary disclaimers.

### Criterion 4: Healthcare Safety & Clinical Guardrails
- **Non-Diagnostic Policy**: Explicit disclaimer banners across all AI briefings and emergency screens ([views/common.py](file:///d:/Dearly/views/common.py#L270-L278)).
- **Emergency Escalation Clarification**: SOS workflows clearly instruct users that the platform does not replace municipal 911 / 112 emergency services.
- **Permission Boundaries**: Verified in [services/care_circle_service.py](file:///d:/Dearly/services/care_circle_service.py#L125-L141).

---

## 3. Automated Test Execution
Run the test suite directly from PowerShell:
```powershell
python -m unittest test_app.py
```
**Result:** 8 tests passed, 0 failures.
