# Dearly
> **Care that stays close.**  
> An intelligent, accessible, and collaborative Elderly Care & Medication Management Platform.

Dearly is built to solve one of the most critical challenges in aging populations: **helping older adults maintain safe, independent health and medication routines while giving family members and caregivers continuous visibility and coordination.**

---

## Why Dearly?

Elderly individuals often struggle with complex multi-drug regimens, conflicting schedules, and appointment follow-ups. Meanwhile, family members worry from a distance, and caregivers lack an integrated tool to monitor adherence, escalate missed doses, and coordinate care.

Dearly connects all three stakeholders in a **closed-loop healthcare ecosystem**:

| Stakeholder | Key Experience | Value Delivered |
|---|---|---|
| **Elderly Individual** | Simplified, high-contrast, distraction-free screen answering *"What medicine do I take right now?"* in 5 seconds with large tap confirmation. | Independence, reduced cognitive burden, and reassurance. |
| **Caregiver** | Real-time adherence tracking, overdue dose escalation alerts, medication CRUD, appointment scheduling, and vital logs. | Coordinated care, fewer errors, and actionable oversight. |
| **Family Member** | Peace of mind through weekly adherence trends, vital history, doctor calendar, and AI-synthesized daily briefings. | Remote reassurance, proactive support, and staying connected. |

---

## Live Demo Credentials

The platform includes pre-seeded realistic healthcare data for immediate jury and peer evaluation:

| Role | Name | Email | Password | Access Details |
|---|---|---|---|---|
| **Elderly** | Asha Patil (Age 74) | `elderly@dearly.demo` | `demo123` | Accessible routine, large confirmation buttons, SOS button |
| **Caregiver** | Rahul Patil (Son) | `caregiver@dearly.demo` | `demo123` | Full medication CRUD, missed dose alerts, vital recording, escalations |
| **Family** | Neha Patil (Daughter) | `family@dearly.demo` | `demo123` | Observability, Plotly adherence charts, AI care briefing |

*Tip: A role switcher is available directly in the sidebar for instant evaluation across all 3 perspectives without re-typing passwords.*

---

## Technology Stack

- **Frontend & App Engine**: [Streamlit](https://streamlit.io/) (v1.40+) with custom scoped WCAG-compliant design system.
- **Analytics & Data Visualization**: [Plotly](https://plotly.com/) for interactive adherence and health trend graphs.
- **Security & Authentication**: [bcrypt](https://pypi.org/project/bcrypt/) with standard work factor 12 and salt generation.
- **Data Persistence**: [SQLite3](https://sqlite.org/) with relational schema, foreign key enforcement, indexes, and idempotent migrations.
- **Language**: Python 3.10+
- **Testing**: Python standard library `unittest` suites (`test_phase2_auth.py`, `test_app.py`, `test_phase3_meds.py`, `test_phase4_reminders.py`).

---

## Architecture & Modular Structure

Dearly is organized into clean, decoupled layers separating presentation, data access, business logic, and safety guardrails:

```text
dearly/
├── app.py                      # Main application entry point & session router
├── database.py                 # SQLite schema, migrations, connection pool, and demo seeding
├── DESIGN.md                   # Permanent design system documentation & accessibility standard
├── PROJECT_STATUS.md           # Progress tracking, phase completion status, and roadmap
├── FEATURE_CHECKLIST.md        # Line-by-line verification checklist against requirements
├── EVALUATION_MAPPING.md       # Hackathon jury evaluation mapping & test execution guide
├── README.md                   # Product architecture, instructions, and engineering guide
├── test_phase4_reminders.py    # Phase 4 Reminders, Alerts & Escalation test suite (17 tests)
├── test_phase3_meds.py         # Phase 3 Medication Management test suite (17 tests)
├── test_phase2_auth.py         # Phase 2 Authentication & User Management test suite (15 tests)
├── test_app.py                 # Core workflow integration test suite (8 tests)
├── requirements.txt            # Python runtime dependencies (Streamlit, Plotly, bcrypt)
├── .env.example                # Configuration template
├── .gitignore                  # Git ignore rules
│
├── services/                   # Decoupled Business Logic & Data Access Layer
│   ├── __init__.py
│   ├── auth_service.py         # Authentication & ward access permissions
│   ├── user_service.py         # User registration, validation, and profile management
│   ├── permissions.py          # Role-based access control (RBAC) & cross-patient guards
│   ├── medication_service.py   # Medication CRUD, daily schedule computation, dose status, adherence
│   ├── reminder_service.py     # Deterministic reminder engine, notifications & caregiver escalation
│   ├── appointment_service.py  # Doctor appointment management, scheduling, and completion
│   ├── health_service.py       # Health vitals logging (BP, Blood Sugar, SpO2, Heart Rate, Weight)
│   ├── care_circle_service.py  # Care circle permissions, profiles, and relationship management
│   ├── activity_service.py     # Immutable audit trail and care activity stream
│   ├── emergency_service.py    # Emergency SOS alert dispatch, acknowledgment, and notifications
│   └── summary_service.py      # Algorithmic daily care briefing with strict safety guardrails
│
└── views/                      # Accessible Streamlit Presentation Layer
    ├── __init__.py
    ├── common.py               # Custom design system CSS, hero components, and disclaimers
    ├── auth_view.py            # Clean sign-in & registration with 1-click Quick Demo logins
    ├── profile_view.py         # User profile viewing and contact detail editing
    ├── notification_view.py    # In-App Notification Center, reminder stream & escalation management
    ├── elderly_view.py         # High-contrast, large-button, accessible elderly interface
    ├── caregiver_view.py       # Care coordination, missed-dose escalation, medication & vitals CRUD
    └── family_view.py          # Observability, Plotly trend charts, and daily briefings
```

---

## Relational Database Schema

All database interactions use parameterized SQL statements to prevent injection and guarantee consistency:

1. **`users`**: User identities, roles (`elderly`, `caregiver`, `family`), password hashes, and phone numbers.
2. **`elderly_profiles`**: Clinical background, blood group, allergies, primary physician, and emergency contacts.
3. **`medications`**: Prescriptions, dosages, 24h schedule times, meal timings, instructions, and stock inventory.
4. **`medication_logs`**: Recorded dose statuses (`taken`, `pending`, `missed`, `skipped`), timestamps, and actor IDs.
5. **`notifications`**: In-app alert queue (`due_now`, `overdue`, `escalation`, `completed`) with read/unread tracking.
6. **`caregiver_escalations`**: Overdue dose caregiver escalations with acknowledgment lifecycle.
7. **`reminder_settings`**: Per-user preferences (grace period in minutes, notifications enabled, 12h/24h time format).
8. **`appointments`**: Doctor visits, hospital/clinic details, appointment timestamps, and statuses.
9. **`health_readings`**: Vital observations (Blood Pressure, Blood Sugar, Heart Rate, SpO2, Weight).
10. **`care_circle`**: Relational mapping between elderly individuals and authorized circle members with permission levels (`editor` vs `viewer`).
11. **`activity_logs`**: Immutable audit logs capturing every dose confirmation, profile change, and appointment.
12. **`emergency_alerts`**: Log of triggered SOS emergency requests with active/acknowledged lifecycle.

---

## Local Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/vidhiborse/Dearly.git
cd Dearly
```

### 2. Set up virtual environment
```powershell
# Windows
py -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the test suite
```bash
# Run all automated tests (57 tests across Auth, RBAC, Medication Management, and Reminders)
python -m unittest test_phase2_auth.py test_app.py test_phase3_meds.py test_phase4_reminders.py
```

### 5. Launch Dearly
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## Clinical Guardrails & Safety Policy

Dearly implements strict healthcare and safety guardrails:

- **Non-Diagnostic Policy**: Dearly does not diagnose diseases, recommend drug therapies, adjust dosages, or suggest discontinuing medical treatments.
- **Informational AI Labeling**: All AI-synthesized care briefings carry explicit notices that they are derived from recorded logs and do not replace professional medical judgment.
- **Emergency Workflow Clarification**: Emergency SOS features trigger immediate alerts to registered family and caregiver contacts, with explicit warnings that the platform is not a replacement for municipal 911 / 112 emergency services.
- **Permission Boundaries**: Family members with `viewer` permissions cannot modify prescriptions or delete medical records, preserving caregiver authority.
- **Separation of Escalation & Intake**: Caregiver escalation acknowledgement logs clinical oversight; it does *never* automatically mark a medication dose as taken.

---

## License

Developed for hackathon evaluation under the MIT License.
