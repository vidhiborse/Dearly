import streamlit as st
from datetime import date, datetime, timedelta
from services.appointment_service import (
    get_appointments,
    get_appointment_by_id,
    get_next_upcoming_appointment,
    add_appointment,
    update_appointment,
    reschedule_appointment,
    cancel_appointment,
    complete_appointment,
    mark_appointment_missed,
    get_appointment_calendar,
    get_appointment_history,
)
from services.auth_service import get_accessible_elderly_wards
from services.permissions import can_manage_elderly_care
from services.health_service import get_latest_vitals, add_health_observation
from views.common import render_clinical_disclaimer


def render_appointment_view(user: dict):
    role = user.get("role", "")
    user_id = user["id"]

    # Determine elderly ward context
    if role == "elderly":
        elderly_id = user_id
        ward_name = user["name"]
    else:
        wards = get_accessible_elderly_wards(user)
        if not wards:
            st.warning("No linked care recipients found.")
            render_clinical_disclaimer()
            return

        ward_options = {w["id"]: f"{w['name']} (ID: #{w['id']})" for w in wards}
        if "appt_selected_ward" not in st.session_state or st.session_state.appt_selected_ward not in ward_options:
            st.session_state.appt_selected_ward = wards[0]["id"]

        c_w1, c_w2 = st.columns([1.5, 2], vertical_alignment="center")
        with c_w1:
            selected_ward_id = st.selectbox(
                "Select Care Recipient",
                options=list(ward_options.keys()),
                format_func=lambda x: ward_options[x],
                index=list(ward_options.keys()).index(st.session_state.appt_selected_ward),
                key="appt_ward_selector",
            )
            st.session_state.appt_selected_ward = selected_ward_id

        elderly_id = st.session_state.appt_selected_ward
        cur_ward = next((w for w in wards if w["id"] == elderly_id), wards[0])
        ward_name = cur_ward["name"]

    can_write = can_manage_elderly_care(user, elderly_id)

    # Page Header
    st.markdown(f"<h1 style='font-size: 26px; color: #234B70; margin-bottom: 4px;'>Doctor Appointments &bull; {ward_name}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 16px;'>Clinical consultations, routine examinations, and specialist follow-ups.</p>", unsafe_allow_html=True)

    # KPI Row
    all_appts = get_appointments(elderly_id, status="all", user=user)
    upcoming_appts = [a for a in all_appts if a["status"] == "upcoming" and a["appointment_date"] >= date.today().isoformat()]
    completed_appts = [a for a in all_appts if a["status"] == "completed"]
    next_appt = get_next_upcoming_appointment(elderly_id, user=user)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        next_txt = f"{next_appt['appointment_date']} ({next_appt['appointment_time']})" if next_appt else "None"
        st.metric("Next Visit", next_txt)
    with k2:
        st.metric("Upcoming Scheduled", f"{len(upcoming_appts)} visits")
    with k3:
        st.metric("Completed History", f"{len(completed_appts)} visits")
    with k4:
        st.metric("Total Records", f"{len(all_appts)}")

    st.write("")

    # 4 Functional Tabs
    tab_upcoming, tab_cal, tab_schedule, tab_history = st.tabs([
        f"Upcoming Visits ({len(upcoming_appts)})",
        "Calendar & Date View",
        "Schedule Visit",
        f"Visit History ({len(all_appts) - len(upcoming_appts)})",
    ])

    # ==========================================
    # TAB 1: UPCOMING VISITS
    # ==========================================
    with tab_upcoming:
        today_str = date.today().isoformat()
        today_appts = [a for a in upcoming_appts if a["appointment_date"] == today_str]

        # Highlight Today's appointments if any
        if today_appts:
            st.markdown(f"""
            <div style="background-color: #EAF3FF; border: 1px solid #B8D5FA; border-left: 5px solid #234B70; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
                <span style="font-size: 13px; font-weight: 700; color: #234B70; text-transform: uppercase;">Happening Today</span>
                <div style="font-size: 18px; font-weight: 700; color: #243447; margin-top: 2px;">
                    {len(today_appts)} doctor appointment(s) scheduled for today
                </div>
            </div>
            """, unsafe_allow_html=True)

        if not upcoming_appts:
            st.info(f"No upcoming doctor visits currently scheduled for {ward_name}. You can schedule a visit using the 'Schedule Visit' tab.")
        else:
            for a in upcoming_appts:
                a_id = a["id"]
                spec_str = f" &bull; {a['specialization']}" if a.get("specialization") else ""
                type_badge = f"<span style='font-size: 12px; font-weight: 700; color: #234B70; background: #EDF2F7; padding: 2px 8px; border-radius: 4px;'>{a.get('appointment_type', 'Consultation')}</span>"
                status_badge = "<span style='font-size: 12px; font-weight: 700; color: #23815C; background: #EBF8F2; padding: 2px 8px; border-radius: 4px;'>UPCOMING</span>"

                with st.container(border=True):
                    head_l, head_r = st.columns([3, 1], vertical_alignment="center")
                    with head_l:
                        st.markdown(f"<strong style='font-size: 20px; color: #234B70;'>{a['doctor_name']}</strong>{spec_str} &bull; {type_badge}", unsafe_allow_html=True)
                        st.markdown(f"**Date:** {a['appointment_date']} at **{a['appointment_time']}** &bull; **Hospital / Clinic:** {a['hospital']}")
                        if a.get("location"):
                            st.caption(f"Location / Address: {a['location']}")
                        if a.get("reason"):
                            st.markdown(f"**Reason for Visit:** {a['reason']}")
                        if a.get("notes"):
                            st.caption(f"Preparation Notes: {a['notes']}")
                        st.caption(f"Scheduled by: {a.get('created_by_name') or 'Caregiver'} &bull; Created: {a['created_at']}")
                    with head_r:
                        st.markdown(f"<div style='text-align: right;'>{status_badge}</div>", unsafe_allow_html=True)

                    # Action controls for authorized users
                    if can_write:
                        st.write("")
                        b_comp, b_resched, b_cancel, b_vital = st.columns(4)
                        with b_comp:
                            with st.expander("Mark Completed"):
                                post_notes = st.text_area("Post-Visit Notes", placeholder="e.g. Blood pressure checked, prescription renewed for 30 days.", key=f"post_{a_id}")
                                if st.button("Confirm Completed", key=f"done_btn_{a_id}", type="primary", use_container_width=True):
                                    complete_appointment(a_id, elderly_id, post_visit_notes=post_notes, user=user)
                                    st.success("Appointment marked as completed.")
                                    st.rerun()
                        with b_resched:
                            with st.expander("Reschedule"):
                                new_d = st.date_input("New Date", value=date.today() + timedelta(days=2), key=f"rsch_d_{a_id}")
                                new_t = st.text_input("New Time (e.g. 11:00 AM)", value=a["appointment_time"], key=f"rsch_t_{a_id}")
                                rsch_reason = st.text_input("Reason for Reschedule", key=f"rsch_r_{a_id}")
                                if st.button("Save Reschedule", key=f"rsch_btn_{a_id}", use_container_width=True):
                                    try:
                                        reschedule_appointment(a_id, elderly_id, new_d.isoformat(), new_t, rsch_reason, user=user)
                                        st.success("Appointment rescheduled.")
                                        st.rerun()
                                    except ValueError as ve:
                                        st.error(str(ve))
                        with b_cancel:
                            with st.expander("Cancel Visit"):
                                c_reason = st.text_input("Cancellation Reason", placeholder="e.g. Doctor cancelled clinic hours", key=f"canc_r_{a_id}")
                                st.caption("Confirm cancellation?")
                                if st.button("Confirm Cancel", key=f"canc_btn_{a_id}", use_container_width=True):
                                    cancel_appointment(a_id, elderly_id, cancellation_reason=c_reason, user=user)
                                    st.warning("Appointment cancelled.")
                                    st.rerun()
                        with b_vital:
                            with st.expander("Post-Visit Note"):
                                post_obs = st.text_area("Clinical Observation", placeholder="e.g. Attending physician suggested checking morning blood pressure daily.", key=f"p_obs_{a_id}")
                                if st.button("Save Observation", key=f"p_obs_btn_{a_id}", use_container_width=True):
                                    if post_obs.strip():
                                        add_health_observation(
                                            elderly_user_id=elderly_id,
                                            observation_text=post_obs.strip(),
                                            recorded_by=user_id,
                                            category="post_visit",
                                            appointment_id=a_id,
                                            user=user,
                                        )
                                        st.success("Post-visit observation linked to appointment.")
                                        st.rerun()
                                    else:
                                        st.error("Please enter observation text.")

    # ==========================================
    # TAB 2: CALENDAR & DATE VIEW
    # ==========================================
    with tab_cal:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Appointment Calendar &bull; Select Date</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Select a date to review visits scheduled on that day.</p>", unsafe_allow_html=True)

        c_pick, c_summary = st.columns([1.5, 2], vertical_alignment="center")
        with c_pick:
            chosen_date = st.date_input("Select Date to Inspect", value=date.today(), key="appt_cal_picker")
        chosen_date_str = chosen_date.isoformat()

        day_appts = get_appointments(elderly_id, status="all", start_date=chosen_date_str, end_date=chosen_date_str, user=user)

        with c_summary:
            st.markdown(f"**Date Selected:** {chosen_date.strftime('%A, %B %d, %Y')}")
            st.markdown(f"Total appointments on this day: **{len(day_appts)}**")

        st.write("")

        if not day_appts:
            st.info(f"No doctor appointments scheduled on {chosen_date.strftime('%B %d, %Y')}.")
        else:
            for da in day_appts:
                st_color = {
                    "upcoming": "#23815C",
                    "completed": "#234B70",
                    "cancelled": "#B84040",
                    "missed": "#C07D1E",
                }.get(da["status"], "#234B70")

                with st.container(border=True):
                    st.markdown(f"<strong style='font-size: 18px; color: #234B70;'>{da['appointment_time']} &bull; {da['doctor_name']}</strong> <span style='font-size: 12px; font-weight: 700; color: {st_color}; text-transform: uppercase;'>[{da['status']}]</span>", unsafe_allow_html=True)
                    st.markdown(f"Hospital / Clinic: **{da['hospital']}** &bull; Purpose: {da.get('reason') or 'Consultation'}")
                    if da.get("notes"):
                        st.caption(f"Notes: {da['notes']}")

    # ==========================================
    # TAB 3: SCHEDULE VISIT
    # ==========================================
    with tab_schedule:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Schedule a New Doctor Visit</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Create a scheduled medical consultation with automatic 1-day and 1-hour in-app reminders.</p>", unsafe_allow_html=True)

        if not can_write:
            st.info("Notice: Family members have read-only observation access. Doctor appointments can be scheduled by authorized caregivers or the senior.")
        else:
            with st.container(border=True):
                with st.form("new_appointment_form"):
                    f_doc = st.text_input("Doctor Name *", placeholder="e.g. Dr. Sunita Kulkarni")
                    f_spec = st.text_input("Specialization (Optional)", placeholder="e.g. Cardiology, Endocrinology, Ophthalmology")
                    f_hosp = st.text_input("Hospital / Clinic Name *", placeholder="e.g. Apollo Heart Clinic, Khar")
                    f_loc = st.text_input("Clinic Address / Room (Optional)", placeholder="e.g. 2nd Floor, Room 204, Linking Road")

                    c_d, c_t = st.columns(2)
                    with c_d:
                        f_date = st.date_input("Appointment Date *", value=date.today() + timedelta(days=3))
                    with c_t:
                        f_time = st.text_input("Appointment Time *", value="10:30 AM", placeholder="e.g. 10:30 AM")

                    c_type, c_space = st.columns(2)
                    with c_type:
                        type_opts = ["General check-up", "Follow-up visit", "Specialist consultation", "Routine examination", "Other"]
                        f_type = st.selectbox("Appointment Type", type_opts)

                    f_reason = st.text_input("Reason for Visit *", placeholder="e.g. Quarterly blood pressure and medication review")
                    f_notes = st.text_area("Preparation Notes (Optional)", placeholder="e.g. Fasting 10 hours required; carry previous blood work reports")

                    st.caption("Reminders will automatically be dispatched to the care circle 1 day and 1 hour before the scheduled time.")
                    submit_appt = st.form_submit_button("Save Doctor Appointment", use_container_width=True, type="primary")

                if submit_appt:
                    try:
                        add_appointment(
                            elderly_user_id=elderly_id,
                            doctor_name=f_doc,
                            specialization=f_spec,
                            hospital=f_hosp,
                            appointment_date=f_date.isoformat(),
                            appointment_time=f_time,
                            appointment_type=f_type,
                            location=f_loc,
                            reason=f_reason,
                            notes=f_notes,
                            user=user,
                        )
                        st.success(f"Appointment with {f_doc} on {f_date.isoformat()} scheduled successfully.")
                        st.rerun()
                    except (ValueError, PermissionError) as ex:
                        st.error(str(ex))

    # ==========================================
    # TAB 4: VISIT HISTORY & SUMMARIES
    # ==========================================
    with tab_history:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Consultation History & Post-Visit Summaries</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Archived clinical consultations, completed visits, and doctor feedback notes.</p>", unsafe_allow_html=True)

        history_visits = get_appointment_history(elderly_id, user=user)
        if not history_visits:
            st.info("No past or completed doctor visits on record.")
        else:
            for h in history_visits:
                h_id = h["id"]
                st_tag = h["status"].upper()
                st_color = "#23815C" if st_tag == "COMPLETED" else ("#B84040" if st_tag == "CANCELLED" else "#C07D1E")

                with st.container(border=True):
                    st.markdown(f"<strong style='font-size: 18px; color: #234B70;'>{h['doctor_name']}</strong> ({h.get('specialization') or 'Doctor'}) &bull; <span style='font-size: 12px; font-weight: 700; color: {st_color};'>[{st_tag}]</span>", unsafe_allow_html=True)
                    st.markdown(f"**Date:** {h['appointment_date']} at {h['appointment_time']} &bull; **Clinic:** {h['hospital']}")
                    if h.get("reason"):
                        st.caption(f"Reason: {h['reason']}")
                    if h.get("post_visit_notes"):
                        st.markdown(f"""
                        <div style="background-color: #F8FAFD; border-left: 3px solid #234B70; padding: 8px 12px; margin: 6px 0; border-radius: 4px;">
                            <strong style="font-size: 14px; color: #234B70;">Post-Visit Summary & Doctor Feedback:</strong>
                            <div style="font-size: 14px; color: #243447; margin-top: 2px;">{h['post_visit_notes']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    if h.get("updated_by_name"):
                        st.caption(f"Last updated by: {h['updated_by_name']} &bull; Updated: {h.get('updated_at') or 'Recorded'}")

                    if can_write and st_tag == "COMPLETED":
                        with st.expander("Update Post-Visit Notes"):
                            up_notes = st.text_area("Edit Consultation Feedback", value=h.get("post_visit_notes") or "", key=f"up_post_{h_id}")
                            if st.button("Save Feedback", key=f"btn_up_post_{h_id}", use_container_width=True):
                                complete_appointment(h_id, elderly_id, post_visit_notes=up_notes, user=user)
                                st.success("Post-visit feedback updated.")
                                st.rerun()

    render_clinical_disclaimer()
