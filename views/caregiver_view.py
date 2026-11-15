import streamlit as st
from datetime import datetime, date, timedelta
from services.auth_service import get_accessible_elderly_wards
from services.medication_service import (
    get_medications,
    get_today_schedule,
    record_dose_status,
    add_medication,
    toggle_medication_status,
    delete_medication,
    get_adherence_metrics,
)
from services.appointment_service import (
    get_appointments,
    add_appointment,
    update_appointment_status,
    delete_appointment,
    get_next_upcoming_appointment,
)
from services.health_service import get_health_readings, add_health_reading, get_latest_vitals
from services.care_circle_service import (
    get_care_circle_members,
    add_care_circle_member,
    get_elderly_profile,
    update_elderly_profile,
)
from services.activity_service import get_recent_activities
from services.emergency_service import (
    get_active_emergency_alerts,
    acknowledge_alert,
    get_simulated_reminders,
)
from views.common import render_hero_header, render_clinical_disclaimer

def render_caregiver_view(user: dict, page: str = "Overview"):
    wards = get_accessible_elderly_wards(user)
    if not wards:
        st.warning("No linked care recipients found. Please link an elderly profile under Care Circle.")
        return

    ward_options = {w["id"]: f"{w['name']} (ID: #{w['id']})" for w in wards}
    
    if "selected_ward_id" not in st.session_state or st.session_state.selected_ward_id not in ward_options:
        st.session_state.selected_ward_id = wards[0]["id"]

    # Ward switcher header
    c_ward, c_info = st.columns([1.5, 2], vertical_alignment="center")
    with c_ward:
        selected_ward_id = st.selectbox(
            "Select Care Recipient",
            options=list(ward_options.keys()),
            format_func=lambda x: ward_options[x],
            index=list(ward_options.keys()).index(st.session_state.selected_ward_id),
            key="caregiver_ward_select",
        )
        st.session_state.selected_ward_id = selected_ward_id

    current_ward = next((w for w in wards if w["id"] == selected_ward_id), wards[0])
    ward_name = current_ward["name"]

    # Active emergency alerts banner
    active_alerts = get_active_emergency_alerts(selected_ward_id)
    if active_alerts:
        for al in active_alerts:
            st.error(f"Active Emergency Alert (Alert #{al['id']}): {al['message']} (Triggered: {al['created_at']})")
            if st.button(f"Acknowledge & Mark Handled (Alert #{al['id']})", key=f"ack_{al['id']}", type="primary"):
                acknowledge_alert(al["id"], selected_ward_id, user["id"])
                st.success(f"Alert #{al['id']} acknowledged.")
                st.rerun()

    metrics = get_adherence_metrics(selected_ward_id, days=7)
    today_schedule = get_today_schedule(selected_ward_id)
    overdue_count = sum(1 for s in today_schedule if s.get("is_overdue"))

    render_hero_header(
        title=f"Caregiver Workspace • {ward_name}",
        subtitle=f"7-day adherence: {metrics['adherence_percentage']}% • {len(today_schedule)} doses scheduled today",
        role_badge="Caregiver Role",
    )

    # 1. OVERVIEW DASHBOARD
    if page == "Overview":
        if overdue_count > 0:
            st.warning(f"Escalation Notice: {overdue_count} dose(s) scheduled for earlier today have not been confirmed taken.")

        # KPI Metrics
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("7-Day Adherence", f"{metrics['adherence_percentage']}%")
        with k2:
            taken_today = sum(1 for s in today_schedule if s["status"] == "taken")
            st.metric("Today's Doses", f"{taken_today} / {len(today_schedule)}")
        with k3:
            next_appt = get_next_upcoming_appointment(selected_ward_id)
            st.metric("Next Appointment", next_appt["appointment_date"] if next_appt else "None")
        with k4:
            low_stock_cnt = len(metrics["low_stock_meds"])
            st.metric("Low Stock Alerts", f"{low_stock_cnt} medicines")

        st.write("")

        col_left, col_right = st.columns([1.5, 1], gap="large")

        with col_left:
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Unconfirmed & Upcoming Doses Today</h2>", unsafe_allow_html=True)
            unconfirmed = [s for s in today_schedule if s["status"] != "taken"]
            if not unconfirmed:
                st.success("All scheduled doses for today have been confirmed taken.")
            else:
                for item in unconfirmed:
                    med_id = item["medication_id"]
                    status = item["status"]
                    is_overdue = item.get("is_overdue", False)
                    status_style = '<span class="badge-overdue">PAST DUE</span>' if is_overdue else '<span class="badge-pending">PENDING</span>'
                    today_str = date.today().isoformat()

                    with st.container(border=True):
                        c1, c2 = st.columns([2.5, 1.2], vertical_alignment="center")
                        with c1:
                            st.markdown(f"**{item['schedule_time']}** &bull; **{item['medicine_name']} {item['dosage']}** ({item['meal_timing']})")
                            st.caption(f"Stock: {item['stock_quantity']} units remaining")
                        with c2:
                            st.markdown(f"<div style='margin-bottom: 6px; text-align: right;'>{status_style}</div>", unsafe_allow_html=True)
                            if st.button("Mark Taken", key=f"ov_take_{med_id}", type="primary", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=selected_ward_id,
                                    scheduled_date=today_str,
                                    scheduled_time=item["schedule_time"],
                                    status="taken",
                                    recorded_by=user["id"],
                                    notes="Confirmed by caregiver from Overview",
                                )
                                st.rerun()

        with col_right:
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Recent Care Activities</h2>", unsafe_allow_html=True)
            activities = get_recent_activities(selected_ward_id, limit=5)
            if not activities:
                st.caption("No recent activities recorded.")
            else:
                for act in activities:
                    with st.container(border=True):
                        st.markdown(f"**{act['action']}** &bull; <span style='font-size: 12px; color: #607086;'>{act['created_at']}</span>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size: 14px; margin: 2px 0 0 0;'>{act['details']}</p>", unsafe_allow_html=True)

    # 2. ELDERLY PROFILES
    elif page == "Elderly Profiles":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Medical Profile &bull; {ward_name}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Manage clinical parameters, allergies, and emergency contacts.</p>", unsafe_allow_html=True)

        profile = get_elderly_profile(selected_ward_id) or {}
        with st.container(border=True):
            with st.form("edit_profile_form"):
                e_phone = st.text_input("Ward Phone Number", value=profile.get("phone") or "")
                e_dob = st.text_input("Date of Birth (YYYY-MM-DD)", value=profile.get("date_of_birth") or "1952-04-12")
                e_blood = st.text_input("Blood Group", value=profile.get("blood_group") or "O+")
                e_emg = st.text_input("Emergency Contact Line", value=profile.get("emergency_contact") or "")
                e_allergies = st.text_input("Known Allergies", value=profile.get("allergies") or "Penicillin")
                e_doc = st.text_input("Primary Physician", value=profile.get("primary_physician") or "")
                e_doc_phone = st.text_input("Physician Phone", value=profile.get("primary_physician_phone") or "")
                e_notes = st.text_area("Everyday Care Notes", value=profile.get("notes") or "")
                submit_profile = st.form_submit_button("Save Profile Changes", use_container_width=True, type="primary")

            if submit_profile:
                update_elderly_profile(
                    elderly_user_id=selected_ward_id,
                    phone=e_phone,
                    date_of_birth=e_dob,
                    blood_group=e_blood,
                    emergency_contact=e_emg,
                    allergies=e_allergies,
                    primary_physician=e_doc,
                    primary_physician_phone=e_doc_phone,
                    notes=e_notes,
                    updated_by=user["id"],
                )
                st.success("Medical profile updated.")
                st.rerun()

    # 3. MEDICATION MONITORING
    elif page == "Medication Monitoring":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Medication Monitoring &bull; {ward_name}</h1>", unsafe_allow_html=True)
        
        tab_list, tab_add = st.tabs(["Active Schedule", "Add Medication"])

        with tab_list:
            inspect_date = st.date_input("View Schedule for Date", value=date.today())
            inspect_date_str = inspect_date.isoformat()
            schedule_items = get_today_schedule(selected_ward_id, target_date=inspect_date_str)

            if not schedule_items:
                st.info("No active medications found for this date.")
            else:
                for item in schedule_items:
                    med_id = item["medication_id"]
                    status = item["status"]
                    status_style = {
                        "taken": '<span class="badge-taken">TAKEN</span>',
                        "pending": '<span class="badge-pending">PENDING</span>',
                        "missed": '<span class="badge-missed">MISSED</span>',
                        "skipped": '<span class="badge-skipped">SKIPPED</span>',
                    }.get(status, '<span class="badge-pending">PENDING</span>')

                    if item.get("is_overdue") and status == "pending":
                        status_style = '<span class="badge-overdue">PAST DUE</span>'

                    with st.container(border=True):
                        r_top, r_badge = st.columns([3, 1], vertical_alignment="center")
                        with r_top:
                            st.markdown(f"**{item['schedule_time']}** &bull; **{item['medicine_name']} {item['dosage']}** ({item['meal_timing']})")
                            st.caption(f"Instructions: {item['instructions']} &bull; Stock: {item['stock_quantity']} left")
                        with r_badge:
                            st.markdown(f"<div style='text-align: right;'>{status_style}</div>", unsafe_allow_html=True)

                        b1, b2, b3, b4 = st.columns([1, 1, 1, 1.4])
                        with b1:
                            if st.button("Mark Taken", key=f"mon_take_{med_id}_{inspect_date_str}", use_container_width=True, type="primary"):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=selected_ward_id,
                                    scheduled_date=inspect_date_str,
                                    scheduled_time=item["schedule_time"],
                                    status="taken",
                                    recorded_by=user["id"],
                                    notes="Verified by caregiver",
                                )
                                st.rerun()
                        with b2:
                            if st.button("Mark Missed", key=f"mon_miss_{med_id}_{inspect_date_str}", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=selected_ward_id,
                                    scheduled_date=inspect_date_str,
                                    scheduled_time=item["schedule_time"],
                                    status="missed",
                                    recorded_by=user["id"],
                                    notes="Marked missed by caregiver",
                                )
                                st.rerun()
                        with b3:
                            if st.button("Skip", key=f"mon_skip_{med_id}_{inspect_date_str}", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=selected_ward_id,
                                    scheduled_date=inspect_date_str,
                                    scheduled_time=item["schedule_time"],
                                    status="skipped",
                                    recorded_by=user["id"],
                                    notes="Skipped with caregiver approval",
                                )
                                st.rerun()
                        with b4:
                            if status != "pending":
                                if st.button("Reset to Pending", key=f"mon_reset_{med_id}_{inspect_date_str}", use_container_width=True):
                                    record_dose_status(
                                        medication_id=med_id,
                                        elderly_user_id=selected_ward_id,
                                        scheduled_date=inspect_date_str,
                                        scheduled_time=item["schedule_time"],
                                        status="pending",
                                        recorded_by=user["id"],
                                        notes="Status reset by caregiver",
                                    )
                                    st.rerun()

        with tab_add:
            with st.container(border=True):
                with st.form("add_medication_form"):
                    med_name = st.text_input("Medicine Name", placeholder="e.g. Metformin")
                    med_dosage = st.text_input("Dosage", placeholder="e.g. 500 mg")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        sched_time = st.text_input("Scheduled Time (24h HH:MM)", value="08:30")
                    with col_t2:
                        frequency = st.selectbox("Frequency", ["Daily", "Twice Daily", "Weekly", "As needed"])
                    meal_timing = st.selectbox("Meal Timing", ["After Meal", "Before Meal", "With Meal", "Anytime"])
                    purpose = st.text_input("Health Condition / Purpose", placeholder="e.g. Hypertension")
                    instructions = st.text_area("Patient Instructions", placeholder="e.g. Take with water after breakfast")
                    stock = st.number_input("Starting Stock Count", min_value=1, max_value=500, value=30)
                    submit_med = st.form_submit_button("Save Medication", use_container_width=True, type="primary")

                if submit_med:
                    if not med_name or not med_dosage:
                        st.error("Please enter both medicine name and dosage.")
                    else:
                        add_medication(
                            elderly_user_id=selected_ward_id,
                            medicine_name=med_name,
                            dosage=med_dosage,
                            schedule_time=sched_time,
                            frequency=frequency,
                            meal_timing=meal_timing,
                            instructions=instructions,
                            purpose=purpose,
                            stock_quantity=stock,
                            created_by=user["id"],
                        )
                        st.success(f"Added {med_name} {med_dosage} to routine.")
                        st.rerun()

    # 4. APPOINTMENTS
    elif page == "Appointments":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Doctor Appointments &bull; {ward_name}</h1>", unsafe_allow_html=True)
        
        c_list, c_new = st.columns([1.2, 1], gap="large")
        with c_list:
            st.markdown("### Scheduled Visits")
            appts = get_appointments(selected_ward_id)
            if not appts:
                st.info("No appointments currently scheduled.")
            else:
                for a in appts:
                    status_badge = "Upcoming" if a["status"] == "upcoming" else ("Completed" if a["status"] == "completed" else "Cancelled")
                    with st.container(border=True):
                        st.markdown(f"**{a['appointment_date']} at {a['appointment_time']}** &bull; **{a['doctor_name']}** [{status_badge}]")
                        st.caption(f"{a['hospital']} &bull; Purpose: {a['purpose']}")
                        if a["status"] == "upcoming":
                            b_c1, b_c2 = st.columns(2)
                            with b_c1:
                                if st.button("Mark Completed", key=f"cg_done_appt_{a['id']}", use_container_width=True):
                                    update_appointment_status(a["id"], selected_ward_id, "completed", updated_by=user["id"])
                                    st.rerun()
                            with b_c2:
                                if st.button("Cancel", key=f"cg_cancel_appt_{a['id']}", use_container_width=True):
                                    update_appointment_status(a["id"], selected_ward_id, "cancelled", updated_by=user["id"])
                                    st.rerun()

        with c_new:
            st.markdown("### Schedule Doctor Visit")
            with st.container(border=True):
                with st.form("add_appointment_form"):
                    doc_name = st.text_input("Doctor Name", placeholder="e.g. Dr. Sunita Kulkarni")
                    hospital = st.text_input("Hospital / Clinic & Location", placeholder="e.g. Apollo Heart Clinic, Khar")
                    col_d, col_tm = st.columns(2)
                    with col_d:
                        appt_date = st.date_input("Appointment Date", value=date.today() + timedelta(days=5))
                    with col_tm:
                        appt_time = st.text_input("Time (e.g. 10:30 AM)", value="10:30 AM")
                    purpose = st.text_input("Purpose of Visit", placeholder="e.g. Quarterly Blood Pressure Review")
                    notes = st.text_area("Preparation Notes", placeholder="e.g. Bring fasting sugar logs")
                    submit_appt = st.form_submit_button("Save Appointment", use_container_width=True, type="primary")

                if submit_appt:
                    if not doc_name or not hospital:
                        st.error("Please enter doctor name and clinic location.")
                    else:
                        add_appointment(
                            elderly_user_id=selected_ward_id,
                            doctor_name=doc_name,
                            hospital=hospital,
                            appointment_date=appt_date.isoformat(),
                            appointment_time=appt_time,
                            purpose=purpose,
                            notes=notes,
                            created_by=user["id"],
                        )
                        st.success("Appointment scheduled.")
                        st.rerun()

    # 5. HEALTH RECORDS
    elif page == "Health Records":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Health Records &bull; {ward_name}</h1>", unsafe_allow_html=True)
        
        hr_c1, hr_c2 = st.columns([1.2, 1], gap="large")
        with hr_c1:
            st.markdown("### Recent Vitals Readings")
            readings = get_health_readings(selected_ward_id, limit=20)
            if not readings:
                st.info("No health readings recorded yet.")
            else:
                for r in readings:
                    with st.container(border=True):
                        st.markdown(f"**{r['reading_type']}**: **{r['reading_value']}** &bull; <span style='font-size: 13px; color: #607086;'>{r['recorded_on']}</span>", unsafe_allow_html=True)
                        st.caption(f"Context: {r['notes'] or 'Routine recording'}")

        with hr_c2:
            st.markdown("### Log New Vitals")
            with st.container(border=True):
                with st.form("add_vital_form"):
                    vital_type = st.selectbox(
                        "Measurement Type",
                        ["Blood Pressure", "Blood Sugar (Fasting)", "Heart Rate", "Oxygen Saturation (SpO2)", "Weight"],
                    )
                    vital_value = st.text_input("Reading Value", placeholder="e.g. 124/80 mmHg")
                    vital_date = st.date_input("Date of Reading", value=date.today())
                    vital_notes = st.text_input("Context / Notes", placeholder="e.g. Measured before breakfast")
                    submit_vital = st.form_submit_button("Record Vital", use_container_width=True, type="primary")

                if submit_vital:
                    if not vital_value:
                        st.error("Please enter a reading value.")
                    else:
                        add_health_reading(
                            elderly_user_id=selected_ward_id,
                            reading_type=vital_type,
                            reading_value=vital_value,
                            recorded_on=vital_date.isoformat(),
                            notes=vital_notes,
                            recorded_by=user["id"],
                        )
                        st.success("Vital recorded.")
                        st.rerun()

    # 6. ACTIVITY HISTORY
    elif page == "Activity History":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Activity History &bull; {ward_name}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Comprehensive audit trail of dose confirmations and care events.</p>", unsafe_allow_html=True)

        activities = get_recent_activities(selected_ward_id, limit=35)
        if not activities:
            st.info("No activity records found.")
        else:
            for act in activities:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1], vertical_alignment="center")
                    with c1:
                        st.markdown(f"**{act['action']}** &bull; {act['details']}")
                        st.caption(f"Actor: {act['actor_name'] or 'System'} ({act['actor_role'] or 'Automated'})")
                    with c2:
                        st.markdown(f"<div style='text-align: right; font-size: 13px; color: #607086;'>{act['created_at']}</div>", unsafe_allow_html=True)

    render_clinical_disclaimer()
