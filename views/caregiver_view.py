import streamlit as st
from datetime import datetime, date, timedelta
from services.auth_service import get_accessible_elderly_wards
from services.medication_service import (
    get_medications,
    get_today_schedule,
    get_grouped_daily_schedule,
    record_dose_status,
    add_medication,
    update_medication,
    deactivate_medication,
    activate_medication,
    delete_medication,
    get_adherence_metrics,
    get_overdue_doses,
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
        overdue_doses = get_overdue_doses(selected_ward_id)
        if overdue_doses:
            med_list_str = ", ".join([f"{d['medicine_name']} ({d['dosage']} at {d['formatted_time']})" for d in overdue_doses])
            st.markdown(f"""
            <div style="background-color: #FDF3E7; border: 1px solid #F5D7A1; border-left: 5px solid #C07D1E; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <span style="font-size: 13px; font-weight: 700; color: #8A4B08; text-transform: uppercase; letter-spacing: 0.5px;">Overdue Medication Notice</span>
                <div style="font-size: 17px; font-weight: 700; color: #243447; margin-top: 2px;">
                    {len(overdue_doses)} dose(s) past due for {ward_name}: {med_list_str}
                </div>
                <p style="margin: 4px 0 0 0; font-size: 14px; color: #607086;">
                    Please verify directly with {ward_name} if this dose was taken. Clinical safety guidance: Never advise taking an extra dose or doubling medication to make up for a missed dose.
                </p>
            </div>
            """, unsafe_allow_html=True)
        elif overdue_count > 0:
            st.warning(f"Notice: {overdue_count} dose(s) scheduled for today require status confirmation.")

        # KPI Metrics
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            adh_val = f"{metrics['adherence_percentage']}%" if metrics.get("has_data") else "No data yet"
            st.metric("7-Day Adherence", adh_val)
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
                            st.markdown(f"**{item['schedule_time']}** &bull; **{item['medicine_name']} {item['dosage']}** ({item.get('medication_type', 'Tablet')}) &bull; {item['meal_timing']}")
                            st.caption(f"Instructions: {item.get('instructions') or 'Follow regular directions'} &bull; Stock: {item['stock_quantity']} units remaining")
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
                                    user=user,
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
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Review daily schedules, update active prescriptions, and log administration status.</p>", unsafe_allow_html=True)

        tab_schedule, tab_registry, tab_add = st.tabs(["Daily Schedule", "Medications Registry", "Add Medication"])

        # TAB 1: DAILY SCHEDULE GROUPED BY TIME PERIOD
        with tab_schedule:
            c_date, c_quick = st.columns([1.5, 2], vertical_alignment="bottom")
            with c_date:
                inspect_date = st.date_input("View Schedule for Date", value=date.today(), key="cg_inspect_date")
            inspect_date_str = inspect_date.isoformat()

            grouped_schedule = get_grouped_daily_schedule(selected_ward_id, target_date=inspect_date_str, user=user)
            total_scheduled_items = sum(len(items) for items in grouped_schedule.values())

            if total_scheduled_items == 0:
                st.info("No medications are scheduled for this date. Check start/end dates or add a medication.")
            else:
                period_display_order = [
                    ("Morning", "05:00 - 11:59"),
                    ("Afternoon", "12:00 - 16:59"),
                    ("Evening", "17:00 - 20:59"),
                    ("Night", "21:00 - 04:59"),
                ]

                for period_name, period_hours in period_display_order:
                    items = grouped_schedule.get(period_name, [])
                    if items:
                        st.markdown(f"""
                        <div style="margin: 18px 0 10px 0; padding-bottom: 6px; border-bottom: 2px solid #E2E8F0;">
                            <span style="font-size: 18px; font-weight: 700; color: #234B70;">{period_name}</span>
                            <span style="font-size: 13px; color: #607086; margin-left: 8px;">({period_hours}) &bull; {len(items)} dose(s)</span>
                        </div>
                        """, unsafe_allow_html=True)

                        for item in items:
                            med_id = item["medication_id"]
                            status = item["status"]
                            is_overdue = item.get("is_overdue", False)

                            if status == "taken":
                                status_style = '<span class="badge-taken">TAKEN</span>'
                            elif is_overdue:
                                status_style = '<span class="badge-overdue">PAST DUE</span>'
                            elif status == "skipped":
                                status_style = '<span class="badge-skipped">SKIPPED</span>'
                            elif status == "missed":
                                status_style = '<span class="badge-missed">MISSED</span>'
                            else:
                                status_style = '<span class="badge-pending">PENDING</span>'

                            with st.container(border=True):
                                r_top, r_badge = st.columns([3, 1.2], vertical_alignment="center")
                                with r_top:
                                    st.markdown(f"**{item['formatted_time']}** &bull; <strong style='font-size: 17px; color: #243447;'>{item['medicine_name']} {item['dosage']}</strong> ({item.get('medication_type', 'Tablet')})", unsafe_allow_html=True)
                                    detail_bits = []
                                    if item.get("meal_timing"):
                                        detail_bits.append(item["meal_timing"])
                                    if item.get("instructions"):
                                        detail_bits.append(item["instructions"])
                                    if item.get("stock_quantity") is not None:
                                        detail_bits.append(f"Stock: {item['stock_quantity']} units")
                                    st.caption(" &bull; ".join(detail_bits))
                                with r_badge:
                                    st.markdown(f"<div style='text-align: right;'>{status_style}</div>", unsafe_allow_html=True)

                                b1, b2, b3, b4 = st.columns([1, 1, 1, 1.3])
                                with b1:
                                    if st.button("Mark Taken", key=f"cg_take_{med_id}_{inspect_date_str}", use_container_width=True, type="primary"):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=selected_ward_id,
                                            scheduled_date=inspect_date_str,
                                            scheduled_time=item["schedule_time"],
                                            status="taken",
                                            recorded_by=user["id"],
                                            notes="Recorded by caregiver",
                                            user=user,
                                        )
                                        st.rerun()
                                with b2:
                                    if st.button("Mark Missed", key=f"cg_miss_{med_id}_{inspect_date_str}", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=selected_ward_id,
                                            scheduled_date=inspect_date_str,
                                            scheduled_time=item["schedule_time"],
                                            status="missed",
                                            recorded_by=user["id"],
                                            notes="Recorded as missed by caregiver",
                                            user=user,
                                        )
                                        st.rerun()
                                with b3:
                                    if st.button("Skip", key=f"cg_skip_{med_id}_{inspect_date_str}", use_container_width=True):
                                        record_dose_status(
                                            medication_id=med_id,
                                            elderly_user_id=selected_ward_id,
                                            scheduled_date=inspect_date_str,
                                            scheduled_time=item["schedule_time"],
                                            status="skipped",
                                            recorded_by=user["id"],
                                            notes="Recorded as skipped with caregiver approval",
                                            user=user,
                                        )
                                        st.rerun()
                                with b4:
                                    if status != "pending":
                                        if st.button("Reset Status", key=f"cg_reset_{med_id}_{inspect_date_str}", use_container_width=True):
                                            record_dose_status(
                                                medication_id=med_id,
                                                elderly_user_id=selected_ward_id,
                                                scheduled_date=inspect_date_str,
                                                scheduled_time=item["schedule_time"],
                                                status="pending",
                                                recorded_by=user["id"],
                                                notes="Dose status reset by caregiver",
                                                user=user,
                                            )
                                            st.rerun()

        # TAB 2: MEDICATIONS REGISTRY (FILTER, VIEW, EDIT, DEACTIVATE, DELETE)
        with tab_registry:
            r_c1, r_c2 = st.columns([1.5, 2], vertical_alignment="center")
            with r_c1:
                filter_choice = st.radio(
                    "Filter by Status",
                    ["All Medications", "Active Medications", "Inactive Medications"],
                    horizontal=True,
                    key="cg_reg_filter",
                )
            filter_map = {
                "All Medications": "all",
                "Active Medications": "active",
                "Inactive Medications": "inactive",
            }
            active_filter = filter_map[filter_choice]
            meds_list = get_medications(selected_ward_id, status_filter=active_filter, user=user)

            if not meds_list:
                st.info(f"No medications match the '{filter_choice}' filter.")
            else:
                st.caption(f"Showing {len(meds_list)} medication(s) for {ward_name}")
                for med in meds_list:
                    m_id = med["id"]
                    is_active = med.get("active", 1) == 1
                    status_badge = '<span class="badge-taken">ACTIVE</span>' if is_active else '<span class="badge-skipped">INACTIVE</span>'

                    with st.container(border=True):
                        top_l, top_r = st.columns([3, 1], vertical_alignment="center")
                        with top_l:
                            st.markdown(f"<strong style='font-size: 19px; color: #234B70;'>{med['medicine_name']} {med['dosage']}</strong> &bull; {med.get('medication_type', 'Tablet')}", unsafe_allow_html=True)
                            st.markdown(f"**Schedule:** {med['schedule_time']} &bull; **Frequency:** {med['frequency']} &bull; **Meal Timing:** {med.get('meal_timing', 'After Meal')}")
                        with top_r:
                            st.markdown(f"<div style='text-align: right;'>{status_badge}</div>", unsafe_allow_html=True)

                        info_col1, info_col2 = st.columns(2)
                        with info_col1:
                            st.caption(f"Start Date: {med.get('start_date') or 'Ongoing'} &bull; End Date: {med.get('end_date') or 'No end date'}")
                            if med.get("instructions"):
                                st.markdown(f"**Instructions:** {med['instructions']}")
                            if med.get("purpose"):
                                st.markdown(f"**Indication / Purpose:** {med['purpose']}")
                        with info_col2:
                            if med.get("prescribing_doctor"):
                                st.markdown(f"**Prescribed by:** {med['prescribing_doctor']}")
                            if med.get("notes"):
                                st.markdown(f"**Clinical Notes:** {med['notes']}")
                            st.caption(f"Stock Remaining: {med.get('stock_quantity', 30)} units")

                        # Action Expander for Edit, Deactivate, and Delete
                        with st.expander(f"Manage / Edit Details: {med['medicine_name']} ({med['dosage']})"):
                            with st.form(f"edit_med_form_{m_id}"):
                                ed_name = st.text_input("Medication Name", value=med["medicine_name"])
                                ed_dosage = st.text_input("Dosage", value=med["dosage"])
                                ed_c1, ed_c2 = st.columns(2)
                                with ed_c1:
                                    type_options = ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Inhaler", "Topical", "Other"]
                                    cur_type = med.get("medication_type") or "Tablet"
                                    type_idx = type_options.index(cur_type) if cur_type in type_options else 0
                                    ed_type = st.selectbox("Medication Type", type_options, index=type_idx)
                                with ed_c2:
                                    freq_options = ["Daily", "Twice Daily", "Three Times Daily", "Weekly", "As needed"]
                                    cur_freq = med.get("frequency") or "Daily"
                                    freq_idx = freq_options.index(cur_freq) if cur_freq in freq_options else 0
                                    ed_freq = st.selectbox("Frequency", freq_options, index=freq_idx)

                                ed_t1, ed_t2 = st.columns(2)
                                with ed_t1:
                                    ed_time = st.text_input("Scheduled Time (24h HH:MM)", value=med["schedule_time"])
                                with ed_t2:
                                    timing_options = ["After Meal", "Before Meal", "With Meal", "Anytime"]
                                    cur_timing = med.get("meal_timing") or "After Meal"
                                    timing_idx = timing_options.index(cur_timing) if cur_timing in timing_options else 0
                                    ed_timing = st.selectbox("Meal Timing", timing_options, index=timing_idx)

                                ed_d1, ed_d2 = st.columns(2)
                                with ed_d1:
                                    ed_start = st.text_input("Start Date (YYYY-MM-DD)", value=med.get("start_date") or date.today().isoformat())
                                with ed_d2:
                                    ed_end = st.text_input("End Date (Optional YYYY-MM-DD)", value=med.get("end_date") or "")

                                ed_inst = st.text_area("Patient Instructions", value=med.get("instructions") or "")
                                ed_purpose = st.text_input("Condition / Purpose", value=med.get("purpose") or "")
                                ed_doc = st.text_input("Prescribing Doctor", value=med.get("prescribing_doctor") or "")
                                ed_notes = st.text_area("Additional Notes", value=med.get("notes") or "")
                                ed_stock = st.number_input("Stock Quantity", min_value=0, max_value=1000, value=int(med.get("stock_quantity") or 30))

                                ed_submit = st.form_submit_button("Save Changes", type="primary", use_container_width=True)

                            if ed_submit:
                                try:
                                    update_medication(
                                        medication_id=m_id,
                                        elderly_user_id=selected_ward_id,
                                        medicine_name=ed_name,
                                        dosage=ed_dosage,
                                        schedule_time=ed_time,
                                        medication_type=ed_type,
                                        frequency=ed_freq,
                                        start_date=ed_start,
                                        end_date=ed_end if ed_end.strip() else None,
                                        meal_timing=ed_timing,
                                        instructions=ed_inst,
                                        purpose=ed_purpose,
                                        prescribing_doctor=ed_doc,
                                        notes=ed_notes,
                                        stock_quantity=ed_stock,
                                        updated_by=user["id"],
                                        user=user,
                                    )
                                    st.success(f"Medication '{ed_name}' details updated successfully.")
                                    st.rerun()
                                except (ValueError, PermissionError) as ex:
                                    st.error(str(ex))

                            st.write("")
                            act_c1, act_c2 = st.columns(2)
                            with act_c1:
                                if is_active:
                                    if st.button(f"Deactivate {med['medicine_name']}", key=f"deact_{m_id}", use_container_width=True):
                                        deactivate_medication(m_id, selected_ward_id, user=user)
                                        st.warning(f"Medication {med['medicine_name']} deactivated. Historical logs remain preserved.")
                                        st.rerun()
                                else:
                                    if st.button(f"Reactivate {med['medicine_name']}", key=f"react_{m_id}", use_container_width=True, type="primary"):
                                        activate_medication(m_id, selected_ward_id, user=user)
                                        st.success(f"Medication {med['medicine_name']} reactivated into daily schedule.")
                                        st.rerun()

                            with act_c2:
                                delete_confirm = st.checkbox(f"Confirm deletion or archiving for {med['medicine_name']}", key=f"del_chk_{m_id}")
                                if st.button(f"Delete Medication", key=f"del_{m_id}", use_container_width=True):
                                    if not delete_confirm:
                                        st.error("Please tick the confirmation checkbox above before deleting.")
                                    else:
                                        delete_medication(m_id, selected_ward_id, confirmed=True, user=user)
                                        st.success(f"Medication {med['medicine_name']} processed. Historical records preserved.")
                                        st.rerun()

        # TAB 3: ADD MEDICATION
        with tab_add:
            with st.container(border=True):
                st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-top: 0;'>Prescribe New Medication</h3>", unsafe_allow_html=True)
                st.caption(f"Add a new medication routine for {ward_name}. All clinical schedule fields are strictly validated.")

                with st.form("add_medication_form"):
                    med_name = st.text_input("Medication Name *", placeholder="e.g. Metformin")
                    med_dosage = st.text_input("Dosage *", placeholder="e.g. 500 mg or 1 tablet")

                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        med_type = st.selectbox("Medication Type *", ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Inhaler", "Topical", "Other"])
                    with col_t2:
                        frequency = st.selectbox("Frequency *", ["Daily", "Twice Daily", "Three Times Daily", "Weekly", "As needed"])

                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        sched_time = st.text_input("Scheduled Time (24h HH:MM) *", value="08:30", placeholder="08:30")
                    with col_s2:
                        meal_timing = st.selectbox("Meal Timing", ["After Meal", "Before Meal", "With Meal", "Anytime"])

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        start_d = st.date_input("Start Date *", value=date.today())
                    with col_d2:
                        has_end_date = st.checkbox("Has End Date", value=False)
                        end_d = st.date_input("End Date", value=date.today() + timedelta(days=30)) if has_end_date else None

                    purpose = st.text_input("Condition / Purpose", placeholder="e.g. Type 2 Diabetes")
                    instructions = st.text_area("Patient Instructions", placeholder="e.g. Take with a full glass of water immediately after breakfast")
                    doc_name = st.text_input("Prescribing Doctor's Name (Optional)", placeholder="e.g. Dr. Sunita Kulkarni")
                    notes = st.text_area("Additional Notes (Optional)", placeholder="e.g. Monitor fasting blood glucose weekly")
                    stock = st.number_input("Starting Stock Count", min_value=1, max_value=500, value=30)

                    submit_med = st.form_submit_button("Save Medication Routine", use_container_width=True, type="primary")

                if submit_med:
                    end_d_str = end_d.isoformat() if has_end_date and end_d else None
                    try:
                        add_medication(
                            elderly_user_id=selected_ward_id,
                            medicine_name=med_name,
                            dosage=med_dosage,
                            medication_type=med_type,
                            schedule_time=sched_time,
                            frequency=frequency,
                            start_date=start_d.isoformat(),
                            end_date=end_d_str,
                            meal_timing=meal_timing,
                            instructions=instructions,
                            purpose=purpose,
                            prescribing_doctor=doc_name,
                            notes=notes,
                            stock_quantity=stock,
                            user=user,
                        )
                        st.success(f"Medication '{med_name}' ({med_dosage}) added successfully to {ward_name}'s routine.")
                        st.rerun()
                    except (ValueError, PermissionError) as ex:
                        st.error(str(ex))

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
