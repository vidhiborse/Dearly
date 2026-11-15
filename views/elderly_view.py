import streamlit as st
from datetime import datetime, date
from services.medication_service import get_today_schedule, record_dose_status
from services.appointment_service import get_next_upcoming_appointment
from services.care_circle_service import get_elderly_profile
from services.emergency_service import trigger_sos_alert, get_active_emergency_alerts
from views.common import render_clinical_disclaimer

def render_elderly_view(user: dict):
    elderly_id = user["id"]
    elderly_name = user["name"]
    profile = get_elderly_profile(elderly_id) or {}

    today_formatted = date.today().strftime("%A, %B %d, %Y")
    
    # Active emergency notice
    active_alerts = get_active_emergency_alerts(elderly_id)
    if active_alerts:
        st.error("Emergency Alert Active: Caregivers and family members have been alerted.")

    # High-accessibility Top Welcome Banner
    with st.container(border=True):
        top_c1, top_c2 = st.columns([2.5, 1], vertical_alignment="center")
        with top_c1:
            st.caption(today_formatted)
            st.markdown(f"<h1 style='margin: 0; font-size: 26px; color: #234B70;'>Welcome, {elderly_name}</h1>", unsafe_allow_html=True)
            st.markdown("<p style='margin: 4px 0 0 0; font-size: 16px; color: #243447;'>Here is your daily medication and care routine for today.</p>", unsafe_allow_html=True)
        with top_c2:
            st.markdown("""
            <div style="background-color: #EBF8F2; border: 1px solid #A8E5CB; padding: 8px 14px; border-radius: 8px; text-align: center;">
                <span style="font-size: 12px; color: #23815C; font-weight: 700; text-transform: uppercase;">Status</span>
                <div style="font-size: 16px; font-weight: 700; color: #23815C;">Routine Active</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")

    # 2-column layout
    col_schedule, col_aside = st.columns([1.5, 1], gap="large")

    with col_schedule:
        st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 12px;'>Today's Medications</h2>", unsafe_allow_html=True)

        schedule = get_today_schedule(elderly_id)
        if not schedule:
            st.info("No medications scheduled for today.")
        else:
            for item in schedule:
                med_id = item["medication_id"]
                name = item["medicine_name"]
                dosage = item["dosage"]
                time_str = item["schedule_time"]
                timing = item["meal_timing"] or "Take with water"
                instructions = item["instructions"] or ""
                status = item["status"]
                is_overdue = item.get("is_overdue", False)

                try:
                    time_obj = datetime.strptime(time_str, "%H:%M")
                    formatted_time = time_obj.strftime("%I:%M %p")
                except Exception:
                    formatted_time = time_str

                if status == "taken":
                    badge_html = '<span class="badge-taken">TAKEN</span>'
                elif is_overdue:
                    badge_html = '<span class="badge-overdue">PAST DUE</span>'
                elif status == "skipped":
                    badge_html = '<span class="badge-skipped">SKIPPED</span>'
                else:
                    badge_html = '<span class="badge-pending">PENDING</span>'

                today_str = date.today().isoformat()

                with st.container(border=True):
                    row_info, row_action = st.columns([1.8, 1.2], vertical_alignment="center")
                    with row_info:
                        st.markdown(f"""
                        <div>
                            <span style="font-size: 20px; font-weight: 700; color: #234B70;">{formatted_time}</span>
                            <span style="font-size: 14px; color: #607086; margin-left: 8px;">({timing})</span>
                            <div style="font-size: 18px; font-weight: 700; color: #243447; margin-top: 2px;">{name} &bull; {dosage}</div>
                            <div style="font-size: 14px; color: #607086; margin-top: 2px;">{instructions}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with row_action:
                        st.markdown(f"<div style='margin-bottom: 8px; text-align: right;'>{badge_html}</div>", unsafe_allow_html=True)
                        if status == "pending":
                            if st.button("Mark as Taken", key=f"take_{med_id}", type="primary", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=elderly_id,
                                    scheduled_date=today_str,
                                    scheduled_time=time_str,
                                    status="taken",
                                    recorded_by=elderly_id,
                                    notes="Confirmed by patient",
                                )
                                st.rerun()
                            if st.button("Skip", key=f"skip_{med_id}", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=elderly_id,
                                    scheduled_date=today_str,
                                    scheduled_time=time_str,
                                    status="skipped",
                                    recorded_by=elderly_id,
                                    notes="Skipped by patient",
                                )
                                st.rerun()
                        elif status == "taken":
                            if st.button("Undo / Reset", key=f"undo_{med_id}", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=elderly_id,
                                    scheduled_date=today_str,
                                    scheduled_time=time_str,
                                    status="pending",
                                    recorded_by=elderly_id,
                                    notes="Reset to pending",
                                )
                                st.rerun()
                        elif status == "skipped":
                            if st.button("Take Now", key=f"retake_{med_id}", type="primary", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=elderly_id,
                                    scheduled_date=today_str,
                                    scheduled_time=time_str,
                                    status="taken",
                                    recorded_by=elderly_id,
                                    notes="Taken later",
                                )
                                st.rerun()

    with col_aside:
        # Next Doctor Appointment Card
        st.markdown("<h2 style='font-size: 18px; color: #234B70; margin-bottom: 12px;'>Next Doctor Visit</h2>", unsafe_allow_html=True)
        next_appt = get_next_upcoming_appointment(elderly_id)
        with st.container(border=True):
            if next_appt:
                appt_date = next_appt["appointment_date"]
                appt_time = next_appt["appointment_time"]
                dr = next_appt["doctor_name"]
                hosp = next_appt["hospital"]
                purpose = next_appt["purpose"]
                st.markdown(f"""
                <span style="background-color: #EDF2F7; color: #234B70; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 12px;">Upcoming Visit</span>
                <h3 style="margin: 8px 0 2px 0; font-size: 18px; color: #234B70;">{dr}</h3>
                <p style="margin: 0; font-size: 15px; font-weight: 600; color: #243447;">{hosp}</p>
                <div style="margin-top: 6px; font-size: 16px; color: #234B70; font-weight: 700;">
                    {appt_date} at {appt_time}
                </div>
                <p style="margin: 6px 0 0 0; font-size: 13px; color: #607086;">Purpose: {purpose}</p>
                """, unsafe_allow_html=True)
            else:
                st.caption("No doctor appointments scheduled for the upcoming week.")

        st.write("")

        # Primary Caregiver Card
        st.markdown("<h2 style='font-size: 18px; color: #234B70; margin-bottom: 12px;'>Primary Caregiver</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("""
            <div style="font-size: 17px; font-weight: 700; color: #243447;">Rahul Patil</div>
            <div style="font-size: 14px; color: #607086;">Son & Primary Caregiver</div>
            <div style="font-size: 17px; font-weight: 700; color: #234B70; margin-top: 6px;">
                Phone: +91 98200 12345
            </div>
            <div style="margin-top: 6px; font-size: 13px; color: #607086;">
                Available for medication assistance and questions.
            </div>
            """, unsafe_allow_html=True)

        st.write("")

        # Emergency Assistance Card
        st.markdown("<h2 style='font-size: 18px; color: #B84040; margin-bottom: 12px;'>Urgent Assistance</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("""
            <p style="margin: 0 0 4px 0; font-size: 15px; color: #B84040; font-weight: 700;">
                Need help right away?
            </p>
            <p style="margin: 0 0 10px 0; font-size: 13px; color: #607086;">
                Pressing the button below dispatches an urgent care notification to Rahul and Neha.
            </p>
            """, unsafe_allow_html=True)

            if st.button("SEND EMERGENCY ALERT", key="elderly_sos_btn", type="primary", use_container_width=True):
                alert_id = trigger_sos_alert(
                    elderly_user_id=elderly_id,
                    triggered_by_user_id=elderly_id,
                    message="Emergency assistance button pressed from Asha's care console",
                )
                st.error(f"Emergency alert dispatched to Rahul Patil and Neha Patil (Alert #{alert_id}).")
                st.rerun()

            st.caption("Notice: For life-threatening emergencies, dial local emergency dispatch (112 or 911) directly.")

    render_clinical_disclaimer()
