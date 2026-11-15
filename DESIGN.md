# Dearly — Design System & UX Architecture

> **Care that stays close.**  
> A shared healthcare ecosystem for elderly individuals, family members, and caregivers.

---

## 1. Design Philosophy

Dearly is built upon eight fundamental design tenets:

1. **Minimalism over decoration**: Every pixel must serve a healthcare purpose.
2. **Accessibility over visual complexity**: Clear affordances for older adults with reduced vision or dexterity.
3. **Consistency over unnecessary creativity**: Predictable layouts across every tab and workflow.
4. **Functionality over visual gimmicks**: No non-functional buttons, fake charts, or ornamental flourishes.
5. **Clear information hierarchy**: Immediate clarity on who, what, when, and what next.
6. **Predictable navigation**: Plain-language role navigation; no deep multi-nested menus.
7. **Large and readable controls**: Generous tap/click targets (minimum 48px height) and legible labels.
8. **Calm and reassuring visual language**: Soft, clinical yet warm palette that reduces anxiety.

### Explicit Anti-Patterns ("Do Not Use")
- No purple/black neon gradient backgrounds or dark theme gimmickry.
- No glowing decorative orbs or drop-shadows exceeding 4px.
- No repetitive 3-column generic icon cards with empty marketing text.
- No icon-only buttons without explicit accompanying text.
- No unreadable captions below 14px or low-contrast muted gray on light gray.
- No fake AI diagnostics, treatment promises, or medical prescribing.

---

## 2. Color System

| Token | Hex Value | Role / Usage | Contrast Ratio on Surface |
|---|---|---|---|
| **Primary** | `#234B70` | Primary brand, main action buttons, page headers | 7.9:1 (Passes AAA) |
| **Primary Hover** | `#193B5A` | Button hover and active states | 10.8:1 (Passes AAA) |
| **Background** | `#F5F8FC` | Application canvas, page background | — |
| **Surface** | `#FFFFFF` | Cards, modals, form containers, elevated panels | — |
| **Secondary Surface** | `#EDF2F7` | Table headers, chip backgrounds, disabled inputs | — |
| **Primary Text** | `#243447` | Headings, labels, primary body text | 11.2:1 (Passes AAA) |
| **Secondary Text** | `#607086` | Supporting context, timestamps, metadata | 4.8:1 (Passes AA) |
| **Border** | `#DFE6EE` | 1px clean dividers, container outlines | — |
| **Success** | `#23815C` | Taken dose status, verified alerts, confirmations | 5.2:1 (Passes AA) |
| **Warning** | `#A66B16` | Pending doses, overdue reminders, non-critical warnings | 4.9:1 (Passes AA) |
| **Danger** | `#B84040` | Missed doses, emergency SOS actions, critical alerts | 5.4:1 (Passes AA) |

---

## 3. Typography

- **Font Family**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
- **Font Weights**:
  - `400` (Regular) for descriptions and secondary text.
  - `500` (Medium) for body copy and readable labels.
  - `600` / `700` (Semi-bold / Bold) reserved for headings and crucial statuses.

### Typographic Scale

| Level | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| **Display / Hero** | 28px - 32px | 700 | 1.25 | Page titles, hero banners |
| **Heading 1** | 22px - 24px | 600 | 1.3 | Major section titles (e.g. "Today's Medicines") |
| **Elderly Instruction** | 20px - 22px | 600 | 1.4 | High-prominence dose directions for older adults |
| **Heading 2** | 18px - 20px | 600 | 1.35 | Subsection headers, modal headers |
| **Body (Default)** | 17px - 18px | 400 / 500 | 1.5 | General descriptions, form inputs, table content |
| **Secondary / Meta** | 14px - 15px | 500 | 1.4 | Timestamps, dosage instructions, caregiver notes |

*Strict Rule: No text anywhere in the user interface is styled smaller than 14px.*

---

## 4. Spacing & Layout System

Based on a strict 8px grid system:
- `8px` (`0.5rem`): Intra-element spacing (icon to text, chip padding, badge gaps).
- `16px` (`1.0rem`): Card internal padding, form field gaps, table cell padding.
- `24px` (`1.5rem`): Section gaps, card-to-card separation.
- `32px` (`2.0rem`): Major workflow block separation.
- `40px` (`2.5rem`): Top and bottom canvas margins.

### Component Geometry
- **Card Border**: `1px solid #DFE6EE`
- **Card Background**: `#FFFFFF`
- **Corner Radii**:
  - Small elements (chips, badges, small buttons): `6px - 8px`
  - Medium elements (inputs, standard buttons): `10px - 12px`
  - Containers (hero cards, medication cards, modals): `14px - 16px`
- **Elevation**: Flat with subtle 1px border. Box shadows limited to `0 2px 4px rgba(36, 52, 71, 0.04)`.

---

## 5. Controls & Interaction Guidelines

### Buttons
- **Touch Target**: Minimum height `48px`, minimum horizontal padding `20px`.
- **Primary Buttons**: Background `#234B70`, Text `#FFFFFF`, font size `17px`, bold font weight.
- **Secondary Buttons**: Background `#FFFFFF`, Border `1px solid #234B70`, Text `#234B70`.
- **Action Confirmation Buttons (Elderly UI)**:
  - Take Dose: `#23815C` (Green) with checkmark icon + clear label "Mark as Taken".
  - Skip / Later: `#607086` (Neutral outline) with clear label "Skip this dose".
- **Emergency Button**: High-contrast red `#B84040` with explicit non-911 demo safety label.

### Forms & Inputs
- Every form field must feature an explicit, bold label (`17px`).
- Helpful placeholder text with real-world examples.
- Inline validation with descriptive error strings ("Please enter a valid time in HH:MM format").
- Checkboxes and radio options must feature large tap targets (minimum 24px box / 44px hit-box).

---

## 6. Elderly-First Accessibility Standard

1. **Self-Service Within 5 Seconds**:
   An elderly user opening their screen must instantly see:
   - What medicine to take now.
   - Exact dosage and timing.
   - Single-click confirmation ("Mark as Taken").
   - Next doctor appointment date and time.
   - Caregiver contact phone number.
   - Emergency contact button.
2. **High-Contrast Affordance**: All critical information meets WCAG AAA standards (minimum 7:1 for text, 4.5:1 for interactive borders).
3. **Zero Ambiguity**: No ambiguous icons like standalone gear, hamburger, or bell icons without clear labels.
4. **Time & Date Representation**: Always spelled out in clear human formats (e.g. "Today at 8:00 AM", "Thursday, Nov 20, 2026").

---

## 7. Role-Based UX Architecture

### Elderly Individual
- Simplified single-column or high-contrast 2-column view.
- Huge status banners for current time window (Morning, Afternoon, Evening, Bedtime).
- Visual pill dosage indicator with instructions (e.g., "Take after food with water").
- One-click confirmation that immediately updates caregiver's live feed.

### Caregiver
- Multi-ward switcher for linked elderly family members.
- Real-time adherence rate (%) with color-coded risk meter.
- Escalation panel showing overdue/unconfirmed doses.
- Full Medication CRUD (name, dosage, timing, stock count, instructions).
- Appointment manager (Dr. name, hospital, date, reminders).
- Vitals recording (Blood Pressure, Glucose, Pulse, SpO2, Weight).
- Audit activity log with timestamps and actor tracking.

### Family Member
- Observability and peace of mind dashboard.
- Daily Care Summary (clear status report).
- Adherence trend visualization (Plotly weekly chart).
- Upcoming medical calendar.
- Activity feed showing when doses were confirmed and by whom.
- Contact card for primary caregiver.

---

## 8. Clinical & AI Guardrails

- **Non-Diagnostic Policy**: Dearly never provides medical diagnosis, does not change dosages, and does not replace licensed medical practitioners.
- **AI Summary Identification**: All AI or automated care summaries are explicitly labeled:
  `"Informational summary generated from recorded logs. Does not substitute professional medical care."`
- **Emergency Workflow**: Emergency SOS triggers simulated alerts to registered family and caregiver contacts with explicit disclaimer:
  `"Demo simulation only. For immediate life-threatening emergencies, call your local emergency services (e.g., 911 / 112 / 108) immediately."`
