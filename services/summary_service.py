from datetime import date
from services.medication_service import get_today_schedule, get_adherence_metrics
from services.health_service import get_latest_vitals
from services.appointment_service import get_next_upcoming_appointment

def generate_daily_care_summary(elderly_name: str, elderly_user_id: int):
    """
    Synthesizes a structured, calm, and reassuring daily care summary.
    Applies strict clinical guardrails: non-diagnostic, informational only.
    """
    today_str = date.today().strftime("%A, %B %d, %Y")
    schedule = get_today_schedule(elderly_user_id)
    metrics = get_adherence_metrics(elderly_user_id, days=7)
    vitals = get_latest_vitals(elderly_user_id)
    next_appt = get_next_upcoming_appointment(elderly_user_id)

    total_today = len(schedule)
    taken_today = sum(1 for s in schedule if s["status"] == "taken")
    pending_today = sum(1 for s in schedule if s["status"] == "pending")
    missed_today = sum(1 for s in schedule if s["status"] == "missed")
    overdue_today = sum(1 for s in schedule if s.get("is_overdue"))

    # Medication status sentence
    if total_today == 0:
        med_summary = "No active scheduled medications recorded for today."
    elif taken_today == total_today:
        med_summary = f"Excellent routine today. All {total_today} scheduled doses have been confirmed."
    else:
        status_parts = []
        if taken_today > 0:
            status_parts.append(f"{taken_today} dose(s) completed")
        if pending_today > 0:
            status_parts.append(f"{pending_today} upcoming dose(s)")
        if missed_today > 0:
            status_parts.append(f"{missed_today} missed dose(s)")
        if overdue_today > 0:
            status_parts.append(f"{overdue_today} dose(s) currently past scheduled time")
        med_summary = f"{', '.join(status_parts)}."

    # Vitals overview
    vitals_parts = []
    if vitals.get("Blood Pressure"):
        bp = vitals["Blood Pressure"]["reading_value"]
        vitals_parts.append(f"Blood Pressure is recorded at **{bp}** (recorded {vitals['Blood Pressure']['recorded_on']})")
    if vitals.get("Blood Sugar (Fasting)"):
        bs = vitals["Blood Sugar (Fasting)"]["reading_value"]
        vitals_parts.append(f"Fasting Blood Sugar is **{bs}**")
    if vitals.get("Heart Rate"):
        hr = vitals["Heart Rate"]["reading_value"]
        vitals_parts.append(f"Heart Rate is **{hr}**")
    if vitals.get("Oxygen Saturation (SpO2)"):
        spo2 = vitals["Oxygen Saturation (SpO2)"]["reading_value"]
        vitals_parts.append(f"SpO2 is **{spo2}**")

    vitals_text = "; ".join(vitals_parts) if vitals_parts else "No recent vitals logged yet."

    # Appointment reminder
    if next_appt:
        appt_text = f"Next scheduled appointment is with **{next_appt['doctor_name']}** at {next_appt['hospital']} on **{next_appt['appointment_date']} at {next_appt['appointment_time']}**."
    else:
        appt_text = "No upcoming doctor appointments scheduled for the next 14 days."

    # Low stock notice
    low_stock = metrics.get("low_stock_meds", [])
    if low_stock:
        low_stock_names = ", ".join([f"{m['medicine_name']} ({m['stock_quantity']} left)" for m in low_stock])
        inventory_text = f"**Medication refill alert**: {low_stock_names}. Please request a prescription refill soon."
    else:
        inventory_text = "All regular medications have sufficient inventory."

    summary_markdown = f"""
### Daily Care Briefing for {elderly_name}
**Date:** {today_str}

#### 1. Medication Routine & Adherence
- **Today's Progress:** {med_summary}
- **7-Day Adherence:** **{metrics['adherence_percentage']}%** adherence over the past week ({metrics['total_taken']} confirmed doses).

#### 2. Latest Health Observations
- {vitals_text}

#### 3. Appointments & Follow-ups
- {appt_text}

#### 4. Pharmacy & Supplies
- {inventory_text}

---
> **Safety & Clinical Disclaimer**: This informational summary is automatically synthesized from logged medication timestamps and caregiver entries. It is intended for coordination and family peace of mind. It does not provide medical diagnosis, treatment recommendations, or changes to prescribed therapies.
"""
    return summary_markdown
