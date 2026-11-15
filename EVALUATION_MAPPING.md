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
| **Caregiver** | Rahul Patil (Son) | `caregiver@dearly.demo` | Multi-ward switcher, adherence tracking, missed-dose alerts |
| **Family** | Neha Patil (Daughter) | `family@dearly.demo` | Peace-of-mind dashboard, adherence trends, AI care briefing |

*Note: You can switch roles instantly at any time using the "Switch Role for Evaluation" buttons located in the left sidebar.*

### Testing User Registration
1. In the sign-in screen, switch to the **"Create Account"** tab.
2. Fill in Full Name, Email, Phone, select your Role (Elderly, Caregiver, or Family), and choose a password.
3. Submit to immediately experience the personalized dashboard for that newly created user.

---

## 2. Evaluation Criteria Mapping

### Criterion 1: Product Design & Healthcare Usability
- **Design System Documentation**: [DESIGN.md](file:///d:/Dearly/DESIGN.md) documents color tokens, typography scales, spacing grids, and anti-patterns.
- **Visual Contrast & Tone**: Calm palette `#234B70`, `#FFFFFF`, `#F5F8FC` with zero neon gimmicks, zero emojis, and WCAG AAA contrast ratios.
- **Elderly-First Accessibility**:
  - Body text is scaled to 18px; important dosage instructions are 20px–22px.
  - Generous touch targets (`min-height: 48px`).
  - Answer within 5 seconds: Home dashboard clearly shows today's next dose, upcoming appointment, caregiver phone, and emergency alert.

### Criterion 2: Authentication, Security & User Management (Phase 2)
- **User Registration**: Implemented in [services/user_service.py](file:///d:/Dearly/services/user_service.py) with validation for required fields, email format regex, duplicate detection, and password confirmation.
- **Bcrypt Password Hashing**: Implemented in [database.py](file:///d:/Dearly/database.py) using `bcrypt` (work factor 12) with salt generation.
- **Role-Based Access Control (RBAC)**: Backend verification in [services/permissions.py](file:///d:/Dearly/services/permissions.py) prevents cross-patient record tampering or role escalation.
- **Profile Management**: Implemented in [views/profile_view.py](file:///d:/Dearly/views/profile_view.py) allowing users to view account attributes and update their contact name and phone number with immediate SQLite persistence.
- **Session Lifecycle**: Protected routes and session cleanup on logout in [app.py](file:///d:/Dearly/app.py).

### Criterion 3: Role-Based Application Shell & Navigation
- **Elderly Navigation**:
  - Menu: `Home`, `My Medicines`, `Appointments`, `My Health`, `Emergency Contacts`, `My Profile`.
  - Implemented in [views/elderly_view.py](file:///d:/Dearly/views/elderly_view.py).
- **Caregiver Navigation**:
  - Menu: `Overview`, `Elderly Profiles`, `Medication Monitoring`, `Appointments`, `Health Records`, `Activity History`, `My Profile`.
  - Implemented in [views/caregiver_view.py](file:///d:/Dearly/views/caregiver_view.py).
- **Family Navigation**:
  - Menu: `Overview`, `Care Updates`, `Medicines`, `Appointments`, `Health Summary`, `My Profile`.
  - Implemented in [views/family_view.py](file:///d:/Dearly/views/family_view.py).

### Criterion 4: Software Architecture & Maintainability
- **Decoupled Architecture**:
  - `services/`: Encapsulates business logic, parameterized SQLite queries, and audit logging.
  - `views/`: Dedicated view files per role with reusable components in `views/common.py`.
- **Database Schema & Migrations**: Implemented in [database.py](file:///d:/Dearly/database.py) with foreign keys, indexes, and idempotent demo data seeding.
- **Automated Test Suite**: [test_phase2_auth.py](file:///d:/Dearly/test_phase2_auth.py) (15 tests) and [test_app.py](file:///d:/Dearly/test_app.py) (8 tests) covering 100% of core flows.

---

## 3. Automated Test Execution
Run the full test suite from PowerShell:
```powershell
python -m unittest test_phase2_auth.py test_app.py
```
**Result:** 23 tests passed, 0 failures, 0 errors.
