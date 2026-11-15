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

def render_caregiver_view(user: dict):
    wards = get_accessible_elderly_wards(user)
    if not wards:
        st.warning("No linked care recipients found. Please link an elderly profile under Care Circle.")
        return

    ward_options = {w["id"]: f"{w['name']} (ID: #{w['id']})" for w in wards}
    
    if "selected_ward_id" not in st.session_state or st.session_state.selected_ward_id not in ward_options:
        st.session_state.selected_ward_id = wards[0]["id"]

    c_ward, c_info = st.columns([1.5, 2])
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

    # Active emergency alerts
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
        title=f"Care Coordination for {ward_name}",
        subtitle=f"7-day adherence: {metrics['adherence_percentage']}% • {len(today_schedule)} doses scheduled today",
        role_badge="Caregiver Workspace",
    )

    if overdue_count > 0:
        st.warning(f"Escalation Notice: {overdue_count} dose(s) scheduled for earlier today have not been confirmed taken.")

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

    tab_routine, tab_manage_meds, tab_appts, tab_vitals, tab_circle, tab_audit = st.tabs([
        "Daily Routine",
        "Manage Medications",
        "Appointments",
        "Vitals & Readings",
        "Care Circle & Profile",
        "Audit & Activity Log",
    ])

    # 1. DAILY ROUTINE TAB
    with tab_routine:
        col_date, col_summary = st.columns([1, 2])
        with col_date:
            inspect_date = st.date_input("View Schedule for Date", value=date.today())
        
        inspect_date_str = inspect_date.isoformat()
        schedule_items = get_today_schedule(selected_ward_id, target_date=inspect_date_str)

        st.subheader(f"Schedule for {inspect_date.strftime('%A, %B %d, %Y')}")
        if not schedule_items:
            st.info("No active medications found for this date.")
        else:
            for item in schedule_items:
                med_id = item["medication_id"]
                med_name = item["medicine_name"]
                dose = item["dosage"]
                sched_time = item["schedule_time"]
                status = item["status"]
                timing = item["meal_timing"] or ""
                stock = item["stock_quantity"]

                status_style = {
                    "taken": '<span class="badge-taken">TAKEN</span>',
                    "pending": '<span class="badge-pending">PENDING</span>',
                    "missed": '<span class="badge-missed">MISSED</span>',
                    "skipped": '<span class="badge-skipped">SKIPPED</span>',
                }.get(status, '<span class="badge-pending">PENDING</span>')

                if item.get("is_overdue") and status == "pending":
                    status_style = '<span class="badge-overdue">PAST DUE</span>'

                with st.container(border=True):
                    row_top, row_badge = st.columns([3, 1], vertical_alignment="center")
                    with row_top:
                        st.markdown(f"""
                        <div>
                            <span style="font-size: 19px; font-weight: 700; color: #234B70;">{sched_time}</span>
                            <span style="font-size: 17px; font-weight: 700; color: #243447; margin-left: 12px;">{med_name} {dose}</span>
                            <span style="font-size: 14px; color: #607086; margin-left: 10px;">({timing})</span>
                            <span style="font-size: 14px; color: #607086; margin-left: 14px;">Stock: {stock} units left</span>
                        </div>
                        """, unsafe_allow_html=True)
                    with row_badge:
                        st.markdown(f"<div style='text-align: right;'>{status_style}</div>", unsafe_allow_html=True)

                    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns([1, 1, 1, 1.4])
                    with btn_c1:
                        if st.button("Mark Taken", key=f"cg_take_{med_id}_{inspect_date_str}", use_container_width=True, type="primary"):
                            record_dose_status(
                                medication_id=med_id,
                                elderly_user_id=selected_ward_id,
                                scheduled_date=inspect_date_str,
                                scheduled_time=sched_time,
                                status="taken",
                                recorded_by=user["id"],
                                notes="Verified by caregiver",
                            )
                            st.rerun()
                    with btn_c2:
                        if st.button("Mark Missed", key=f"cg_miss_{med_id}_{inspect_date_str}", use_container_width=True):
                            record_dose_status(
                                medication_id=med_id,
                                elderly_user_id=selected_ward_id,
                                scheduled_date=inspect_date_str,
                                scheduled_time=sched_time,
                                status="missed",
                                recorded_by=user["id"],
                                notes="Marked missed by caregiver",
                            )
                            st.rerun()
                    with btn_c3:
                        if st.button("Skip", key=f"cg_skip_{med_id}_{inspect_date_str}", use_container_width=True):
                            record_dose_status(
                                medication_id=med_id,
                                elderly_user_id=selected_ward_id,
                                scheduled_date=inspect_date_str,
                                scheduled_time=sched_time,
                                status="skipped",
                                recorded_by=user["id"],
                                notes="Skipped with caregiver approval",
                            )
                            st.rerun()
                    with btn_c4:
                        if status != "pending":
                            if st.button("Reset to Pending", key=f"cg_reset_{med_id}_{inspect_date_str}", use_container_width=True):
                                record_dose_status(
                                    medication_id=med_id,
                                    elderly_user_id=selected_ward_id,
                                    scheduled_date=inspect_date_str,
                                    scheduled_time=sched_time,
                                    status="pending",
                                    recorded_by=user["id"],
                                    notes="Status reset by caregiver",
                                )
                                st.rerun()

    # 2. MANAGE MEDICATIONS TAB
    with tab_manage_meds:
        med_col1, med_col2 = st.columns([1.1, 1], gap="large")

        with med_col1:
            st.markdown("### Existing Medications")
            all_meds = get_medications(selected_ward_id, active_only=False)
            if not all_meds:
                st.info("No medications added yet. Use the form on the right to configure.")
            else:
                for m in all_meds:
                    m_id = m["id"]
                    is_active = (m["active"] == 1)
                    status_text = "Active" if is_active else "Paused"
                    stock_warn = " (Low Stock)" if m["stock_quantity"] <= 7 else ""

                    with st.expander(f"{m['medicine_name']} {m['dosage']} — {m['schedule_time']} [{status_text}{stock_warn}]", expanded=is_active):
                        st.markdown(f"""
                        - **Purpose**: {m['purpose'] or 'General care'}
                        - **Frequency**: {m['frequency']} at {m['schedule_time']}
                        - **Meal Timing**: {m['meal_timing']}
                        - **Instructions**: {m['instructions'] or 'None recorded'}
                        - **Inventory Stock**: **{m['stock_quantity']} units remaining**
                        """)

                        action_c1, action_c2 = st.columns(2)
                        with action_c1:
                            if is_active:
                                if st.button("Pause Medication", key=f"pause_{m_id}", use_container_width=True):
                                    toggle_medication_status(m_id, selected_ward_id, active=0, updated_by=user["id"])
                                    st.rerun()
                            else:
                                if st.button("Resume Medication", key=f"resume_{m_id}", type="primary", use_container_width=True):
                                    toggle_medication_status(m_id, selected_ward_id, active=1, updated_by=user["id"])
                                    st.rerun()
                        with action_c2:
                            if st.button("Discontinue", key=f"del_{m_id}", use_container_width=True):
                                delete_medication(m_id, selected_ward_id, deleted_by=user["id"])
                                st.rerun()

        with med_col2:
            st.markdown("### Add New Medication")
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

    # 3. APPOINTMENTS TAB
    with tab_appts:
        appt_c1, appt_c2 = st.columns([1.2, 1], gap="large")

        with appt_c1:
            st.markdown("### Scheduled Appointments")
            appts = get_appointments(selected_ward_id)
            if not appts:
                st.info("No appointments currently scheduled.")
            else:
                for a in appts:
                    a_id = a["id"]
                    status = a["status"]
                    status_badge = "Upcoming" if status == "upcoming" else ("Completed" if status == "completed" else "Cancelled")
                    
                    with st.expander(f"{a['appointment_date']} at {a['appointment_time']} — {a['doctor_name']} [{status_badge}]", expanded=(status == "upcoming")):
                        st.markdown(f"""
                        - **Hospital / Clinic**: {a['hospital']}
                        - **Purpose**: {a['purpose']}
                        - **Notes & Instructions**: {a['notes'] or 'None recorded'}
                        """)
                        if status == "upcoming":
                            btn_c1, btn_c2 = st.columns(2)
                            with btn_c1:
                                if st.button("Mark Completed", key=f"done_appt_{a_id}", use_container_width=True):
                                    update_appointment_status(a_id, selected_ward_id, "completed", updated_by=user["id"])
                                    st.rerun()
                            with btn_c2:
                                if st.button("Cancel Appointment", key=f"cancel_appt_{a_id}", use_container_width=True):
                                    update_appointment_status(a_id, selected_ward_id, "cancelled", updated_by=user["id"])
                                    st.rerun()

        with appt_c2:
            st.markdown("### Schedule Doctor Visit")
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

    # 4. VITALS & HEALTH RECORDS TAB
    with tab_vitals:
        v_col1, v_col2 = st.columns([1.2, 1], gap="large")

        with v_col1:
            st.markdown("### Recent Health Readings")
            readings = get_health_readings(selected_ward_id, limit=20)
            if not readings:
                st.info("No health readings recorded yet.")
            else:
                for r in readings:
                    st.markdown(f"""
                    <div style="background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 8px; padding: 12px 18px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 700; color: #234B70; font-size: 16px;">{r['reading_type']}</span>
                            <span style="font-weight: 600; font-size: 16px; color: #243447; margin-left: 12px;">{r['reading_value']}</span>
                            <div style="font-size: 13px; color: #607086;">{r['notes'] or 'Routine reading'}</div>
                        </div>
                        <div style="font-size: 13px; color: #607086; text-align: right;">
                            {r['recorded_on']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with v_col2:
            st.markdown("### Log New Vitals")
            with st.form("add_vital_form"):
                vital_type = st.selectbox(
                    "Measurement Type",
                    [
                        "Blood Pressure",
                        "Blood Sugar (Fasting)",
                        "Heart Rate",
                        "Oxygen Saturation (SpO2)",
                        "Weight",
                    ],
                )
                placeholder_map = {
                    "Blood Pressure": "e.g. 124/80 mmHg",
                    "Blood Sugar (Fasting)": "e.g. 110 mg/dL",
                    "Heart Rate": "e.g. 74 bpm",
                    "Oxygen Saturation (SpO2)": "e.g. 98 %",
                    "Weight": "e.g. 64.5 kg",
                }
                vital_value = st.text_input("Reading Value", placeholder=placeholder_map.get(vital_type, ""))
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

    # 5. CARE CIRCLE & PROFILE TAB
    with tab_circle:
        c_left, c_right = st.columns([1, 1], gap="large")

        with c_left:
            st.markdown("### Care Circle Members")
            members = get_care_circle_members(selected_ward_id)
            for m in members:
                perm_badge = "Editor (Caregiver)" if m["permission_level"] == "editor" else "Viewer (Family)"
                st.markdown(f"""
                <div class="dearly-card" style="margin-bottom: 12px; padding: 14px 18px;">
                    <div style="font-weight: 700; font-size: 16px; color: #234B70;">{m['name']}</div>
                    <div style="font-size: 14px; color: #243447;">{m['relationship']} &bull; {m['email']}</div>
                    <div style="font-size: 13px; color: #607086; margin-top: 4px;">Phone: {m['phone'] or 'Not provided'}</div>
                    <span style="background-color: #EDF2F7; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; color: #234B70; display: inline-block; margin-top: 6px;">
                        {perm_badge}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("#### Invite Family / Caregiver")
            with st.form("invite_circle_form"):
                new_email = st.text_input("Member Email", placeholder="e.g. family@dearly.demo")
                relationship = st.text_input("Relationship", placeholder="e.g. Sister, Grandson, Nurse")
                perm = st.selectbox("Permission", ["viewer", "editor"], format_func=lambda x: "Viewer (Read-only)" if x == "viewer" else "Editor (Manage Doses & Meds)")
                submit_invite = st.form_submit_button("Link to Circle", use_container_width=True)

            if submit_invite:
                ok, msg = add_care_circle_member(
                    elderly_user_id=selected_ward_id,
                    email=new_email,
                    relationship=relationship,
                    permission_level=perm,
                    added_by=user["id"],
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with c_right:
            st.markdown("### Medical Profile")
            profile = get_elderly_profile(selected_ward_id) or {}
            with st.form("edit_profile_form"):
                e_phone = st.text_input("Ward Phone Number", value=profile.get("phone") or "")
                e_dob = st.text_input("Date of Birth (YYYY-MM-DD)", value=profile.get("date_of_birth") or "1952-04-12")
                e_blood = st.text_input("Blood Group", value=profile.get("blood_group") or "O+")
                e_emg = st.text_input("Emergency Contact Line", value=profile.get("emergency_contact") or "")
                e_allergies = st.text_input("Known Allergies", value=profile.get("allergies") or "Penicillin")
                e_doc = st.text_input("Primary Physician", value=profile.get("primary_physician") or "")
                e_doc_phone = st.text_input("Physician Phone", value=profile.get("primary_physician_phone") or "")
                e_notes = st.text_area("Everyday Care Notes", value=profile.get("notes") or "")
                submit_profile = st.form_submit_button("Update Medical Profile", use_container_width=True)

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

    # 6. AUDIT & ACTIVITY LOG TAB
    with tab_audit:
        st.markdown("### Caregiver Audit Trail")
        activities = get_recent_activities(selected_ward_id, limit=30)
        if not activities:
            st.info("No activity records found.")
        else:
            for act in activities:
                st.markdown(f"""
                <div style="background-color: #FFFFFF; border-left: 4px solid #234B70; border-top: 1px solid #DFE6EE; border-right: 1px solid #DFE6EE; border-bottom: 1px solid #DFE6EE; border-radius: 6px; padding: 10px 16px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: 700; color: #234B70;">{act['action']}</span>
                        <span style="font-size: 13px; color: #607086;">{act['created_at']}</span>
                    </div>
                    <div style="font-size: 14px; color: #243447; margin-top: 2px;">{act['details']}</div>
                    <div style="font-size: 12px; color: #607086; margin-top: 2px;">Actor: {act['actor_name'] or 'System'} ({act['actor_role'] or 'Automated'})</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Dispatched Notifications (Simulated)")
        sim_reminders = get_simulated_reminders(selected_ward_id, limit=10)
        if sim_reminders:
            for sr in sim_reminders:
                st.caption(f"[{sr['sent_at']}] Sent to {sr['recipient_email']}: {sr['subject']} — {sr['message']}")
        else:
            st.caption("No simulated notifications logged.")

    render_clinical_disclaimer()
