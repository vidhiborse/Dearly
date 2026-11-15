import streamlit as st
from datetime import datetime, date
from services.medication_service import (
    get_today_schedule,
    get_grouped_daily_schedule,
    get_overdue_doses,
    record_dose_status,
    get_medications,
)
from services.appointment_service import get_next_upcoming_appointment, get_appointments
from services.health_service import get_health_readings, get_latest_vitals
from services.care_circle_service import get_elderly_profile, get_care_circle_members
from services.emergency_service import trigger_sos_alert, get_active_emergency_alerts
from views.common import render_clinical_disclaimer
from views.health_view import render_health_view

def render_elderly_view(user: dict, page: str = "Home"):
    elderly_id = user["id"]
    elderly_name = user["name"]
    profile = get_elderly_profile(elderly_id) or {}
    today_formatted = date.today().strftime("%A, %B %d, %Y")
    
    # Active emergency notice
    active_alerts = get_active_emergency_alerts(elderly_id)
    if active_alerts:
        st.error("Emergency Alert Active: Caregivers and family members have been alerted.")

    # 1. HOME DASHBOARD
    if page == "Home":
        # Overdue Dose Notification for Patient Reassurance
        overdue_doses = get_overdue_doses(elderly_id, user=user)
        if overdue_doses:
            med_names = ", ".join([f"{d['medicine_name']} ({d['formatted_time']})" for d in overdue_doses])
            st.markdown(f"""
            <div style="background-color: #FDF3E7; border: 1px solid #F5D7A1; border-left: 5px solid #C07D1E; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <span style="font-size: 13px; font-weight: 700; color: #8A4B08; text-transform: uppercase;">Scheduled Medicine Notice</span>
                <div style="font-size: 17px; font-weight: 700; color: #243447; margin-top: 2px;">
                    Scheduled time has passed for: {med_names}
                </div>
                <p style="margin: 4px 0 0 0; font-size: 15px; color: #607086;">
                    If you haven't taken this medicine yet, please take your regular dose or check with your caregiver. Please never take extra medicines or double your dose.
                </p>
            </div>
            """, unsafe_allow_html=True)

        # Welcome Banner
        with st.container(border=True):
            top_c1, top_c2 = st.columns([2.5, 1], vertical_alignment="center")
            with top_c1:
                st.caption(today_formatted)
                st.markdown(f"<h1 style='margin: 0; font-size: 26px; color: #234B70;'>Welcome, {elderly_name}</h1>", unsafe_allow_html=True)
                st.markdown("<p style='margin: 4px 0 0 0; font-size: 18px; color: #243447;'>Here is your daily healthcare overview.</p>", unsafe_allow_html=True)
            with top_c2:
                schedule = get_today_schedule(elderly_id, user=user)
                taken_count = sum(1 for s in schedule if s["status"] == "taken")
                st.markdown(f"""
                <div style="background-color: #EBF8F2; border: 1px solid #A8E5CB; padding: 10px 14px; border-radius: 8px; text-align: center;">
                    <span style="font-size: 13px; color: #23815C; font-weight: 700; text-transform: uppercase;">Today's Doses</span>
                    <div style="font-size: 18px; font-weight: 700; color: #23815C;">{taken_count} of {len(schedule)} taken</div>
                </div>
                """, unsafe_allow_html=True)

        st.write("")

        # 2-column home layout
        col_main, col_side = st.columns([1.5, 1], gap="large")

        with col_main:
            # Next Scheduled Dose
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Next Scheduled Dose</h2>", unsafe_allow_html=True)
            schedule = get_today_schedule(elderly_id, user=user)
            pending_doses = [s for s in schedule if s["status"] == "pending"]
            next_dose = pending_doses[0] if pending_doses else None

            with st.container(border=True):
                if next_dose:
                    n_time = next_dose["schedule_time"]
                    n_formatted = next_dose.get("formatted_time", n_time)

                    st.markdown(f"""
                    <div style="background-color: #F0F6FC; border-left: 4px solid #234B70; padding: 14px 18px; border-radius: 6px; margin-bottom: 14px;">
                        <span style="font-size: 14px; color: #607086; font-weight: 600;">UPCOMING AT {n_formatted} ({next_dose.get('period', 'Scheduled')})</span>
                        <div style="font-size: 22px; font-weight: 700; color: #243447; margin-top: 2px;">{next_dose['medicine_name']} ({next_dose['dosage']})</div>
                        <div style="font-size: 16px; color: #607086; margin-top: 4px;">{next_dose['meal_timing']} &bull; {next_dose['instructions']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    btn_c1, btn_c2 = st.columns([1.5, 1])
                    today_str = date.today().isoformat()
                    with btn_c1:
                        if st.button(f"Mark {next_dose['medicine_name']} as Taken", key=f"home_take_{next_dose['medication_id']}", type="primary", use_container_width=True):
                            record_dose_status(
                                medication_id=next_dose["medication_id"],
                                elderly_user_id=elderly_id,
                                scheduled_date=today_str,
                                scheduled_time=next_dose["schedule_time"],
                                status="taken",
                                recorded_by=elderly_id,
                                notes="Confirmed by patient from Home Dashboard",
                                user=user,
                            )
                            st.rerun()
                    with btn_c2:
                        if st.button("Skip this dose", key=f"home_skip_{next_dose['medication_id']}", use_container_width=True):
                            record_dose_status(
                                medication_id=next_dose["medication_id"],
                                elderly_user_id=elderly_id,
                                scheduled_date=today_str,
                                scheduled_time=next_dose["schedule_time"],
                                status="skipped",
                                recorded_by=elderly_id,
                                notes="Skipped from Home Dashboard",
                                user=user,
                            )
                            st.rerun()
                else:
                    st.markdown("""
                    <div style="padding: 10px 0;">
                        <span style="font-size: 17px; font-weight: 700; color: #23815C;">All scheduled doses for today have been completed.</span>
                        <p style="margin: 4px 0 0 0; font-size: 15px; color: #607086;">Great job keeping your health routine consistent today.</p>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

            # Today's Medication Overview Grouped by Period
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Today's Schedule by Time of Day</h2>", unsafe_allow_html=True)
            grouped_today = get_grouped_daily_schedule(elderly_id, user=user)
            total_items = sum(len(items) for items in grouped_today.values())

            if total_items == 0:
                st.info("No medications recorded in your schedule for today.")
            else:
                for period_name, period_hours in [("Morning", "05:00 - 11:59"), ("Afternoon", "12:00 - 16:59"), ("Evening", "17:00 - 20:59"), ("Night", "21:00 - 04:59")]:
                    p_items = grouped_today.get(period_name, [])
                    if p_items:
                        st.markdown(f"<div style='font-size: 16px; font-weight: 700; color: #234B70; margin-top: 10px; margin-bottom: 4px;'>{period_name} ({period_hours})</div>", unsafe_allow_html=True)
                        for item in p_items:
                            m_name = item["medicine_name"]
                            dosage = item["dosage"]
                            t_fmt = item.get("formatted_time", item["schedule_time"])
                            status = item["status"]
                            is_overdue = item.get("is_overdue", False)

                            if status == "taken":
                                badge = '<span class="badge-taken">TAKEN</span>'
                            elif is_overdue:
                                badge = '<span class="badge-overdue">PAST DUE</span>'
                            elif status == "skipped":
                                badge = '<span class="badge-skipped">SKIPPED</span>'
                            else:
                                badge = '<span class="badge-pending">PENDING</span>'

                            with st.container(border=True):
                                r1, r2 = st.columns([3, 1], vertical_alignment="center")
                                with r1:
                                    st.markdown(f"**{t_fmt}** &bull; **{m_name}** ({dosage}) — *{item['meal_timing']}*")
                                with r2:
                                    st.markdown(f"<div style='text-align: right;'>{badge}</div>", unsafe_allow_html=True)

        with col_side:
            # Upcoming Appointments Card
            st.markdown("<h2 style='font-size: 18px; color: #234B70; margin-bottom: 10px;'>Upcoming Appointments</h2>", unsafe_allow_html=True)
            next_appt = get_next_upcoming_appointment(elderly_id)
            with st.container(border=True):
                if next_appt:
                    st.markdown(f"""
                    <span style="background-color: #EDF2F7; color: #234B70; font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 12px;">Next Visit</span>
                    <h3 style="margin: 8px 0 2px 0; font-size: 18px; color: #234B70;">{next_appt['doctor_name']}</h3>
                    <p style="margin: 0; font-size: 15px; font-weight: 600; color: #243447;">{next_appt['hospital']}</p>
                    <div style="margin-top: 6px; font-size: 16px; color: #234B70; font-weight: 700;">
                        {next_appt['appointment_date']} at {next_appt['appointment_time']}
                    </div>
                    <p style="margin: 6px 0 0 0; font-size: 14px; color: #607086;">Purpose: {next_appt['purpose']}</p>
                    """, unsafe_allow_html=True)
                else:
                    st.caption("No doctor appointments scheduled for the upcoming week.")

            st.write("")

            # Caregiver Contact Information
            st.markdown("<h2 style='font-size: 18px; color: #234B70; margin-bottom: 10px;'>Caregiver Contact</h2>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("""
                <div style="font-size: 17px; font-weight: 700; color: #243447;">Rahul Patil</div>
                <div style="font-size: 14px; color: #607086;">Son & Primary Caregiver</div>
                <div style="font-size: 18px; font-weight: 700; color: #234B70; margin-top: 6px;">
                    Phone: +91 98200 12345
                </div>
                """, unsafe_allow_html=True)

            st.write("")

            # Emergency Contact Access
            st.markdown("<h2 style='font-size: 18px; color: #B84040; margin-bottom: 10px;'>Emergency Assistance</h2>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("""
                <p style="margin: 0 0 8px 0; font-size: 14px; color: #607086;">
                    Dispatches an immediate alert to registered caregiver and family contacts.
                </p>
                """, unsafe_allow_html=True)
                if st.button("SEND EMERGENCY ALERT", key="home_sos_btn", type="primary", use_container_width=True):
                    alert_id = trigger_sos_alert(
                        elderly_user_id=elderly_id,
                        triggered_by_user_id=elderly_id,
                        message="Urgent assistance button pressed from Asha's Home Dashboard",
                    )
                    st.error(f"Emergency alert dispatched to Rahul Patil and Neha Patil (Alert #{alert_id}).")
                    st.rerun()
                st.caption("Notice: In a life-threatening emergency, call local emergency dispatch (112 or 911) directly.")

    # 2. MY MEDICINES PAGE
    elif page == "My Medicines":
        st.markdown("<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>My Medicines</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Review and confirm your prescribed daily medication routine grouped by time of day.</p>", unsafe_allow_html=True)

        grouped_today = get_grouped_daily_schedule(elderly_id, user=user)
        total_items = sum(len(items) for items in grouped_today.values())

        if total_items == 0:
            st.info("No active medications found in your routine for today.")
        else:
            today_str = date.today().isoformat()
            period_labels = [
                ("Morning", "05:00 - 11:59"),
                ("Afternoon", "12:00 - 16:59"),
                ("Evening", "17:00 - 20:59"),
                ("Night", "21:00 - 04:59"),
            ]

            for period_name, period_hours in period_labels:
                period_meds = grouped_today.get(period_name, [])
                if period_meds:
                    st.markdown(f"""
                    <div style="margin: 20px 0 10px 0; padding-bottom: 6px; border-bottom: 2px solid #E2E8F0;">
                        <span style="font-size: 19px; font-weight: 700; color: #234B70;">{period_name}</span>
                        <span style="font-size: 14px; color: #607086; margin-left: 8px;">({period_hours})</span>
                    </div>
                    """, unsafe_allow_html=True)

                    for item in period_meds:
                        med_id = item["medication_id"]
                        name = item["medicine_name"]
                        dosage = item["dosage"]
                        time_str = item["schedule_time"]
                        formatted_time = item.get("formatted_time", time_str)
                        timing = item.get("meal_timing") or "Take with water"
                        instructions = item.get("instructions") or "Follow standard directions."
                        status = item["status"]
                        is_overdue = item.get("is_overdue", False)

                        if status == "taken":
                            badge_html = '<span class="badge-taken">TAKEN</span>'
                        elif is_overdue:
                            badge_html = '<span class="badge-overdue">PAST DUE</span>'
                        elif status == "skipped":
                            badge_html = '<span class="badge-skipped">SKIPPED</span>'
                        else:
                            badge_html = '<span class="badge-pending">PENDING</span>'

                        with st.container(border=True):
                            row_info, row_action = st.columns([1.8, 1.2], vertical_alignment="center")
                            with row_info:
                                st.markdown(f"""
                                <div>
                                    <span style="font-size: 22px; font-weight: 700; color: #234B70;">{formatted_time}</span>
                                    <span style="font-size: 15px; color: #607086; margin-left: 8px;">({timing})</span>
                                    <div style="font-size: 20px; font-weight: 700; color: #243447; margin-top: 4px;">{name} &bull; {dosage}</div>
                                    <div style="font-size: 16px; color: #607086; margin-top: 4px;">{instructions}</div>
                                </div>
                                """, unsafe_allow_html=True)

                            with row_action:
                                st.markdown(f"<div style='margin-bottom: 10px; text-align: right;'>{badge_html}</div>", unsafe_allow_html=True)
                                if status == "pending":
                                    if st.button("Mark as Taken", key=f"meds_take_{med_id}", type="primary", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=elderly_id,
                                            scheduled_date=today_str,
                                            scheduled_time=time_str,
                                            status="taken",
                                            recorded_by=elderly_id,
                                            notes="Confirmed by patient",
                                            user=user,
                                        )
                                        st.rerun()
                                    if st.button("Skip this dose", key=f"meds_skip_{med_id}", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=elderly_id,
                                            scheduled_date=today_str,
                                            scheduled_time=time_str,
                                            status="skipped",
                                            recorded_by=elderly_id,
                                            notes="Skipped by patient",
                                            user=user,
                                        )
                                        st.rerun()
                                elif status == "taken":
                                    if st.button("Undo / Reset", key=f"meds_undo_{med_id}", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=elderly_id,
                                            scheduled_date=today_str,
                                            scheduled_time=time_str,
                                            status="pending",
                                            recorded_by=elderly_id,
                                            notes="Reset to pending by patient",
                                            user=user,
                                        )
                                        st.rerun()
                                elif status == "skipped":
                                    if st.button("Take Now", key=f"meds_retake_{med_id}", type="primary", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=elderly_id,
                                            scheduled_date=today_str,
                                            scheduled_time=time_str,
                                            status="taken",
                                            recorded_by=elderly_id,
                                            notes="Taken later by patient",
                                            user=user,
                                        )
                                        st.rerun()

        # Detailed Prescriptions List
        st.write("")
        with st.expander("View Full Prescription Details & Doctor Information"):
            all_my_meds = get_medications(elderly_id, status_filter="active", user=user)
            if not all_my_meds:
                st.info("No active prescription records found.")
            else:
                for m in all_my_meds:
                    with st.container(border=True):
                        st.markdown(f"**{m['medicine_name']} ({m['dosage']})** &bull; {m.get('medication_type', 'Tablet')} &bull; Scheduled: {m['schedule_time']}")
                        st.caption(f"Instructions: {m.get('instructions') or 'As directed'} | Prescribing Doctor: {m.get('prescribing_doctor') or 'Primary Physician'} | Stock: {m.get('stock_quantity', 30)} units")

    # 3. APPOINTMENTS PAGE
    elif page == "Appointments":
        st.markdown("<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Doctor Appointments</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Scheduled clinical visits and checkups.</p>", unsafe_allow_html=True)

        appts = get_appointments(elderly_id)
        if not appts:
            st.info("No medical appointments currently scheduled.")
        else:
            for a in appts:
                status_label = "Upcoming" if a["status"] == "upcoming" else ("Completed" if a["status"] == "completed" else "Cancelled")
                with st.container(border=True):
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 18px; font-weight: 700; color: #234B70;">{a['doctor_name']}</span>
                        <span style="font-size: 13px; font-weight: 700; color: #234B70; background-color: #EDF2F7; padding: 2px 8px; border-radius: 4px;">{status_label}</span>
                    </div>
                    <div style="font-size: 15px; font-weight: 600; color: #243447; margin-top: 4px;">{a['hospital']}</div>
                    <div style="font-size: 15px; color: #234B70; font-weight: 600; margin-top: 4px;">Date: {a['appointment_date']} at {a['appointment_time']}</div>
                    <div style="font-size: 14px; color: #607086; margin-top: 4px;">Purpose: {a['purpose']}</div>
                    <div style="font-size: 13px; color: #607086; margin-top: 2px;">Notes: {a['notes'] or 'None recorded'}</div>
                    """, unsafe_allow_html=True)

    # 4. MY HEALTH PAGE
    elif page == "My Health":
        render_health_view(user, page="My Health")

    # 5. EMERGENCY CONTACTS PAGE
    elif page == "Emergency Contacts":
        st.markdown("<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Emergency Contacts</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Authorized contacts and urgent care resources.</p>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("### Primary Emergency Contact")
            st.markdown(f"**{profile.get('emergency_contact', 'Rahul Patil: +91 98200 12345')}**")
            st.caption("Designated primary contact notified in case of health events.")

        st.write("")

        with st.container(border=True):
            st.markdown("### Primary Physician")
            st.markdown(f"**{profile.get('primary_physician', 'Dr. Sunita Kulkarni')}**")
            st.markdown(f"Phone: **{profile.get('primary_physician_phone', '+91 98111 22334')}**")
            st.caption(f"Allergies on record: {profile.get('allergies', 'Penicillin')}")

        st.write("")

        with st.container(border=True):
            st.markdown("### Emergency Alert Action")
            st.markdown("Dispatches an immediate notification to all members of your care circle.")
            if st.button("DISPATCH EMERGENCY ALERT NOW", key="contacts_sos_btn", type="primary", use_container_width=True):
                alert_id = trigger_sos_alert(
                    elderly_user_id=elderly_id,
                    triggered_by_user_id=elderly_id,
                    message="Emergency alert dispatched from Emergency Contacts page",
                )
                st.error(f"Emergency alert dispatched to Rahul Patil and Neha Patil (Alert #{alert_id}).")
                st.rerun()
            st.caption("Notice: For life-threatening emergencies, dial local emergency services (112 or 911) directly.")

    render_clinical_disclaimer()
