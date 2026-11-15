# Security Architecture and Quality Assurance — Dearly

Dearly (*Care that stays close.*) is an elderly-care and medication-management platform designed with defense-in-depth principles. The application handles sensitive medication schedules, health vitals, care circle authorizations, and emergency notifications. This document outlines the security architecture, threat model, access control policies, and implementation safeguards.

---

## 1. Authentication Security

### 1.1 Password Hashing and Storage
- **Algorithm**: `bcrypt` with work factor 12 (`rounds=12`).
- **Salting**: Cryptographically random salt generated per user via `bcrypt.gensalt(rounds=12)`.
- **Zero Plaintext**: Passwords are never written to disk, database columns, log files, or session objects in plaintext.
- **Migration & Upgrade**: Transparent upgrade pipeline detects legacy prototype hashes upon successful login and seamlessly re-hashes credentials to bcrypt `$2b$12$...` without user disruption.

### 1.2 Password Complexity Policy
- Minimum length: 8 characters.
- Requires at least one uppercase letter (`[A-Z]`).
- Requires at least one lowercase letter (`[a-z]`).
- Requires at least one digit (`[0-9]`).
- Requires at least one special character (`[!@#$%^&*(),.?":{}|<>]`).
- Client-side and server-side verification before registration or password update.

### 1.3 Session Security
- Streamlit session state stores authenticated user identity (`id`, `name`, `email`, `role`, `phone`).
- The `password_hash` field is stripped immediately upon database retrieval prior to placing the user record in session state.
- **Session Cleanup**: Explicit `logout_user()` purges all authentication keys, active profile selections, and cached circle permissions from `st.session_state`.
- **Role Immutability**: Role permissions are re-verified against the persistent database on critical operations to prevent client-side session tampering.

---

## 2. Role-Based Access Control (RBAC)

Dearly defines three primary user roles:
1. **Elderly**: The individual receiving care. Owns personal records, medication logs, and SOS activation triggers.
2. **Caregiver**: Primary or secondary care coordinator (e.g., adult child, home nurse). Granted editor or viewer permissions over connected elderly wards.
3. **Family Member**: Extended care network member (e.g., daughter, cousin). Typically granted read-only visibility into medication adherence, schedule calendars, and health vitals.

### 2.1 Backend Enforcement Layer
Access control is enforced at the service layer (`services/permissions.py`) and cannot be bypassed through URL manipulation or UI tampering:

```text
+--------------------------------------------------------------+
|                    Presentation / UI Layer                   |
+--------------------------------------------------------------+
                               |
                               v
+--------------------------------------------------------------+
|     Backend Direct-Service Authorization (permissions.py)    |
|   - enforce_elderly_access(user, elderly_id, write_access)   |
|   - can_access_elderly_record(user, elderly_id)              |
|   - can_manage_elderly_care(user, elderly_id)                |
+--------------------------------------------------------------+
                               |
                               v
+--------------------------------------------------------------+
|               Data Access Layer (SQLite 3 + WAL)             |
|              PRAGMA foreign_keys = ON; Parameterized         |
+--------------------------------------------------------------+
```

### 2.2 Permissions Matrix

| Resource / Action | Elderly (Self) | Caregiver (Editor) | Caregiver (Viewer) | Family (Viewer) | Unconnected User |
| :--- | :--- | :--- | :--- | :--- | :--- |
| View Medications | Yes | Yes | Yes | Yes | Denied |
| Add / Edit / Deactivate Meds | Yes | Yes | Denied | Denied | Denied |
| Log Dose (Taken / Skipped) | Yes | Yes | Denied | Denied | Denied |
| Trigger Emergency SOS | Yes | Yes | Yes | Denied | Denied |
| Acknowledge / Resolve SOS | Yes | Yes | Yes | Denied | Denied |
| View Care Notes (Circle) | Yes | Yes | Yes | Yes | Denied |
| View Care Notes (Caregivers-Only) | Denied | Yes | Yes | Denied | Denied |
| Add / Correct Health Readings | Yes | Yes | Denied | Denied | Denied |
| Manage Care Circle Members | Yes | Yes (if Primary) | Denied | Denied | Denied |
| Export Analytics & CSV | Yes | Yes | Yes | Yes | Denied |

---

## 3. Database Security and Data Integrity

### 3.1 SQL Injection Prevention
- **100% Parameterized Queries**: All database queries across all services utilize standard SQLite parameter binding (`?` placeholders).
- **Dynamic Identifier Validation**: Dynamic table or column names in administrative utilities (e.g., `ensure_column`) validate inputs using Python's `str.isidentifier()` to prevent identifier injection.
- Zero string formatting or concatenation (`f"SELECT ... {user_input}"`) is permitted in SQL statements.

### 3.2 Relational Integrity and Foreign Keys
- `PRAGMA foreign_keys = ON` is executed on every database connection.
- Cascading deletions (`ON DELETE CASCADE`) are configured on dependent tables (`medications`, `medication_logs`, `care_circle`, `elderly_profiles`, `health_readings`, `emergency_assistance_requests`).
- Orphaned row cleanup executes during database initialization to maintain structural integrity across test cycles and system updates.

### 3.3 Concurrency and Race Condition Safeguards
- Medication dose logging uses SQLite `UNIQUE(medication_id, scheduled_date, scheduled_time)` with `INSERT OR REPLACE` / `UPSERT` semantics to prevent duplicate dose recordings.
- Emergency SOS activation enforces duplicate guards: an active emergency (`pending`, `acknowledged`, or `assistance_in_progress`) blocks redundant triggers until formally resolved.

---

## 4. Input Validation and Data Sanitization

- **Full Name**: Minimum 2 characters, maximum 100 characters, whitespace-trimmed.
- **Email Address**: Validated against RFC 5322 regex pattern; normalized to lowercase.
- **Phone Number**: Validated for E.164 / standard mobile formats (10-15 digits with optional `+` prefix).
- **Medication Dosages**: Required non-empty string, maximum 100 characters.
- **Schedule Times**: Validated 24-hour time format (`HH:MM`).
- **Dates**: Validated ISO-8601 format (`YYYY-MM-DD`). Appointments disallow past dates during creation.
- **Health Measurements**:
  - Systolic Blood Pressure: 50 to 300 mmHg.
  - Diastolic Blood Pressure: 30 to 200 mmHg.
  - Heart Rate: 30 to 250 bpm.
  - Blood Glucose: 20 to 1000 mg/dL.
  - Oxygen Saturation: 50 to 100 %.
  - Body Temperature: 90.0 to 110.0 F (or 32.0 to 43.0 C).
  - Weight: 10 to 400 kg.

---

## 5. Audit Logging and Transparency

1. **Activity Logs (`activity_logs`)**:
   - Records every critical action: user login, medication updates, dose logs, appointments, care circle modifications, and health record entries.
   - Captures `elderly_user_id`, `actor_id`, `action_type`, `description`, and UTC timestamp.
2. **Health Reading Corrections (`health_record_audit`)**:
   - Health vitals are treated as legal clinical observations.
   - Original records are never deleted on correction. Corrections create an audit log documenting `previous_value`, `new_value`, `reason_for_change`, and `changed_by_user_id`.
3. **Emergency Transitions (`emergency_status_history`)**:
   - Every state transition (`pending` -> `acknowledged` -> `assistance_in_progress` -> `resolved`) logs the acting caregiver, timestamp, and optional progress notes.

---

## 6. Environment and Secret Management

- Secrets, database paths, and API keys are loaded via environment variables with fallbacks to secure defaults.
- `.env.example` provides documentation of all supported environment configuration parameters.
- `.gitignore` strictly excludes SQLite database files (`*.db`, `*.sqlite`), environment secret files (`.env`), and temporary logs.

---

## 7. Elderly Accessibility Compliance

In accordance with `DESIGN.md`, security implementations preserve cognitive accessibility:
- **No Intrusive CAPTCHAs**: Avoid confusing visual puzzle gates that impede elderly users.
- **High Contrast UI**: WCAG AAA/AA compliant contrast ratios (Primary `#234B70`, Alert `#B84040`, Charcoal `#222222`).
- **Typography**: Base font scale 18px with touch target minimums of 48px by 48px.
- **Zero Emojis**: 100% text and icon-clean interface for professional medical clarity and screen reader compatibility.

---

## 8. Quality Assurance and Test Automation

The Dearly codebase is covered by an automated test suite comprising 189 tests across 10 test modules:

| Test Module | Focus Area | Test Count | Pass Rate |
| :--- | :--- | :--- | :--- |
| `test_app.py` | Core Application & Architecture | 20 | 100% |
| `test_phase2_auth.py` | Authentication & User Management | 18 | 100% |
| `test_phase3_meds.py` | Medication Schedules & Dosages | 20 | 100% |
| `test_phase4_reminders.py` | Reminders & Escalations | 17 | 100% |
| `test_phase5_circle.py` | Family & Caregiver Circle | 20 | 100% |
| `test_phase6_appts.py` | Doctor Appointments | 20 | 100% |
| `test_phase7_health.py` | Health Records & Vitals Audit | 22 | 100% |
| `test_phase8_emergency.py` | Emergency SOS Workflow | 20 | 100% |
| `test_phase9_analytics.py` | Adherence Analytics & Reports | 26 | 100% |
| `test_phase10_security_qa.py` | Security Hardening & End-to-End QA | 26 | 100% |
| **Total** | **Comprehensive Regression Suite** | **189** | **100%** |

---

## 9. Recommended Production Deployments

For production deployment beyond the hackathon demonstration environment:
1. **Transport Layer Security (TLS)**: Terminate HTTPS via reverse proxy (e.g., NGINX or Caddy) with automated Let's Encrypt certificates.
2. **Session Cookie Hardening**: Configure `SameSite=Strict`, `HttpOnly`, and `Secure` cookie attributes.
3. **Rate Limiting**: Implement upstream rate limiting on `/login` and registration routes (e.g., 5 failed attempts per IP per 15 minutes) to protect against brute-force attacks.
4. **Automated Database Backups**: Enable continuous SQLite WAL mode backups and off-site encrypted storage.
