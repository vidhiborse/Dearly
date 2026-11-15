import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, date
from services.auth_service import get_accessible_elderly_wards
from services.medication_service import (
    get_today_schedule,
    get_grouped_daily_schedule,
    get_adherence_metrics,
    get_medications,
)
from services.appointment_service import get_appointments, get_next_upcoming_appointment
from services.health_service import get_health_readings, get_latest_vitals
from services.care_circle_service import get_care_circle_members, get_elderly_profile
from services.activity_service import get_recent_activities
from services.summary_service import generate_daily_care_summary
from views.common import render_hero_header, render_clinical_disclaimer
from views.health_view import render_health_view

def render_family_view(user: dict, page: str = "Overview"):
    wards = get_accessible_elderly_wards(user)
    if not wards:
        st.warning("No linked elderly family members found. Please request an invitation from the primary caregiver.")
        return

    ward_options = {w["id"]: w["name"] for w in wards}
    if "family_ward_id" not in st.session_state or st.session_state.family_ward_id not in ward_options:
        st.session_state.family_ward_id = wards[0]["id"]

    if len(wards) > 1:
        st.session_state.family_ward_id = st.selectbox(
            "Viewing Care Profile For",
            options=list(ward_options.keys()),
            format_func=lambda x: ward_options[x],
        )

    elderly_id = st.session_state.family_ward_id
    current_ward = next((w for w in wards if w["id"] == elderly_id), wards[0])
    elderly_name = current_ward["name"]
    profile = get_elderly_profile(elderly_id) or {}

    metrics = get_adherence_metrics(elderly_id, days=7)
    today_schedule = get_today_schedule(elderly_id)
    next_appt = get_next_upcoming_appointment(elderly_id)
    taken_cnt = sum(1 for s in today_schedule if s["status"] == "taken")
    total_today = len(today_schedule)

    render_hero_header(
        title=f"Family Care Circle • {elderly_name}",
        subtitle=f"Care status: Active • Today's routine: {taken_cnt} of {total_today} doses confirmed",
        role_badge="Family Role",
    )

    # 1. OVERVIEW DASHBOARD
    if page == "Overview":
        # Reassurance Hero Banner
        if taken_cnt == total_today and total_today > 0:
            reassurance_msg = f"All scheduled medicines for today have been confirmed taken. {elderly_name}'s routine is on track."
            banner_bg = "#EBF8F2"
            banner_border = "#A8E5CB"
            banner_text = "#23815C"
        elif taken_cnt > 0:
            reassurance_msg = f"Routine is progressing well today: {taken_cnt} of {total_today} doses completed."
            banner_bg = "#F0F6FC"
            banner_border = "#C8DAEB"
            banner_text = "#234B70"
        else:
            reassurance_msg = f"{elderly_name}'s daily routine is underway. Upcoming doses are scheduled."
            banner_bg = "#FFFFFF"
            banner_border = "#DFE6EE"
            banner_text = "#243447"

        st.markdown(f"""
        <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 10px; padding: 14px 18px; margin-bottom: 20px;">
            <span style="font-size: 17px; font-weight: 700; color: {banner_text};">{reassurance_msg}</span>
        </div>
        """, unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            adh_val = f"{metrics['adherence_percentage']}%" if metrics.get("has_data") else "No doses due yet"
            st.metric("7-Day Adherence", adh_val)
        with m2:
            st.metric("Confirmed Doses", f"{metrics['total_taken']} doses")
        with m3:
            st.metric("Next Doctor Visit", next_appt["appointment_date"] if next_appt else "None soon")
        with m4:
            vitals = get_latest_vitals(elderly_id)
            latest_bp = vitals["Blood Pressure"]["reading_value"] if vitals.get("Blood Pressure") else "—"
            st.metric("Latest Blood Pressure", latest_bp)

        st.write("")

        col_l, col_r = st.columns([1.5, 1], gap="large")
        with col_l:
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Today's Routine by Time of Day</h2>", unsafe_allow_html=True)
            grouped_today = get_grouped_daily_schedule(elderly_id, user=user)
            total_items = sum(len(items) for items in grouped_today.values())

            if total_items == 0:
                st.info("No medications are scheduled for today.")
            else:
                for period_name, period_hours in [("Morning", "05:00 - 11:59"), ("Afternoon", "12:00 - 16:59"), ("Evening", "17:00 - 20:59"), ("Night", "21:00 - 04:59")]:
                    p_items = grouped_today.get(period_name, [])
                    if p_items:
                        st.markdown(f"<div style='font-size: 16px; font-weight: 700; color: #234B70; margin-top: 10px; margin-bottom: 4px;'>{period_name} ({period_hours})</div>", unsafe_allow_html=True)
                        for item in p_items:
                            status = item["status"]
                            is_overdue = item.get("is_overdue", False)
                            badge = {
                                "taken": '<span class="badge-taken">TAKEN</span>',
                                "pending": '<span class="badge-overdue">PAST DUE</span>' if is_overdue else '<span class="badge-pending">UPCOMING</span>',
                                "missed": '<span class="badge-missed">MISSED</span>',
                                "skipped": '<span class="badge-skipped">SKIPPED</span>',
                            }.get(status, '<span class="badge-pending">UPCOMING</span>')

                            with st.container(border=True):
                                r1, r2 = st.columns([3, 1], vertical_alignment="center")
                                with r1:
                                    st.markdown(f"**{item.get('formatted_time', item['schedule_time'])}** &bull; **{item['medicine_name']} {item['dosage']}** ({item['meal_timing']})")
                                    st.caption(f"Instructions: {item.get('instructions') or 'Follow regular routine'}")
                                with r2:
                                    st.markdown(f"<div style='text-align: right;'>{badge}</div>", unsafe_allow_html=True)

        with col_r:
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Next Medical Appointment</h2>", unsafe_allow_html=True)
            with st.container(border=True):
                if next_appt:
                    st.markdown(f"""
                    <span style="font-size: 13px; font-weight: 700; color: #234B70; background-color: #EDF2F7; padding: 2px 8px; border-radius: 4px;">Upcoming Visit</span>
                    <h3 style="margin: 6px 0 2px 0; font-size: 18px; color: #234B70;">{next_appt['doctor_name']}</h3>
                    <div style="font-size: 15px; font-weight: 600; color: #243447;">{next_appt['hospital']}</div>
                    <div style="font-size: 15px; color: #234B70; font-weight: 700; margin-top: 4px;">
                        {next_appt['appointment_date']} at {next_appt['appointment_time']}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.caption("No doctor appointments scheduled.")

            st.write("")
            st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Primary Caregiver</h2>", unsafe_allow_html=True)
            members = get_care_circle_members(elderly_id)
            caregiver = next((m for m in members if m["permission_level"] == "editor"), None)
            with st.container(border=True):
                if caregiver:
                    st.markdown(f"**{caregiver['name']}** ({caregiver['relationship']})")
                    st.markdown(f"Phone: **{caregiver['phone'] or '+91 98200 12345'}**")
                else:
                    st.caption("Primary caregiver details not assigned.")

    # 2. CARE UPDATES
    elif page == "Care Updates":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Daily Care Briefing &bull; {elderly_name}</h1>", unsafe_allow_html=True)
        summary_md = generate_daily_care_summary(elderly_name, elderly_id)
        with st.container(border=True):
            st.markdown(summary_md)

        st.write("")
        st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Recent Care Activity Stream</h2>", unsafe_allow_html=True)
        activities = get_recent_activities(elderly_id, limit=20)
        for act in activities:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1], vertical_alignment="center")
                with c1:
                    st.markdown(f"**{act['action']}** &bull; {act['details']}")
                    st.caption(f"Actor: {act['actor_name']} ({act['actor_role']})")
                with c2:
                    st.markdown(f"<div style='text-align: right; font-size: 13px; color: #607086;'>{act['created_at']}</div>", unsafe_allow_html=True)

    # 3. MEDICINES
    elif page == "Medicines":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Prescribed Medicines &bull; {elderly_name}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Active prescription schedule and adherence summary (Family view is read-only).</p>", unsafe_allow_html=True)

        # Adherence Summary Cards
        with st.container(border=True):
            st.markdown("<h3 style='font-size: 18px; color: #234B70; margin-top: 0;'>7-Day Adherence Summary</h3>", unsafe_allow_html=True)
            if not metrics.get("has_data"):
                st.info("No scheduled doses have become due yet in this observation window. Metrics will automatically calculate once scheduled times pass.")
            else:
                a1, a2, a3, a4, a5 = st.columns(5)
                with a1:
                    st.metric("Adherence Rate", f"{metrics['adherence_percentage']}%")
                with a2:
                    st.metric("Total Due", f"{metrics['total_due']}")
                with a3:
                    st.metric("Taken", f"{metrics['total_taken']}")
                with a4:
                    st.metric("Skipped", f"{metrics['total_skipped']}")
                with a5:
                    st.metric("Pending/Due", f"{metrics['total_pending']}")

        st.write("")
        st.markdown("<h2 style='font-size: 20px; color: #234B70; margin-bottom: 10px;'>Today's Schedule by Time Period</h2>", unsafe_allow_html=True)
        grouped_today = get_grouped_daily_schedule(elderly_id, user=user)
        total_items = sum(len(items) for items in grouped_today.values())

        if total_items == 0:
            st.info("No scheduled medications recorded for today.")
        else:
            for period_name, period_hours in [("Morning", "05:00 - 11:59"), ("Afternoon", "12:00 - 16:59"), ("Evening", "17:00 - 20:59"), ("Night", "21:00 - 04:59")]:
                p_items = grouped_today.get(period_name, [])
                if p_items:
                    st.markdown(f"<div style='font-size: 16px; font-weight: 700; color: #234B70; margin-top: 10px; margin-bottom: 4px;'>{period_name} ({period_hours})</div>", unsafe_allow_html=True)
                    for s in p_items:
                        status = s["status"]
                        is_overdue = s.get("is_overdue", False)
                        badge = {
                            "taken": '<span class="badge-taken">TAKEN</span>',
                            "pending": '<span class="badge-overdue">PAST DUE</span>' if is_overdue else '<span class="badge-pending">UPCOMING</span>',
                            "missed": '<span class="badge-missed">MISSED</span>',
                            "skipped": '<span class="badge-skipped">SKIPPED</span>',
                        }.get(status, '<span class="badge-pending">UPCOMING</span>')

                        with st.container(border=True):
                            c_info, c_badge = st.columns([3, 1], vertical_alignment="center")
                            with c_info:
                                st.markdown(f"**{s.get('formatted_time', s['schedule_time'])}** &bull; **{s['medicine_name']} {s['dosage']}** ({s.get('medication_type', 'Tablet')})")
                                st.caption(f"Instructions: {s['instructions']} &bull; Purpose: {s['purpose'] or 'Daily routine'}")
                            with c_badge:
                                st.markdown(f"<div style='text-align: right;'>{badge}</div>", unsafe_allow_html=True)

        st.write("")
        with st.expander("View Complete Prescriptions Registry"):
            active_meds = get_medications(elderly_id, status_filter="all", user=user)
            if not active_meds:
                st.info("No medication records found.")
            else:
                for m in active_meds:
                    st_label = "ACTIVE" if m.get("active") == 1 else "INACTIVE"
                    with st.container(border=True):
                        st.markdown(f"**{m['medicine_name']} ({m['dosage']})** &bull; {m.get('medication_type', 'Tablet')} &bull; Status: **{st_label}**")
                        st.caption(f"Schedule: {m['schedule_time']} ({m['frequency']}) | Doctor: {m.get('prescribing_doctor') or 'Not specified'} | Instructions: {m.get('instructions') or 'As directed'}")

    # 4. APPOINTMENTS
    elif page == "Appointments":
        st.markdown(f"<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>Doctor Appointments &bull; {elderly_name}</h1>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 18px;'>Upcoming and past clinical consultations.</p>", unsafe_allow_html=True)

        appts = get_appointments(elderly_id)
        if not appts:
            st.info("No appointments currently scheduled.")
        else:
            for a in appts:
                status_icon = "Upcoming" if a["status"] == "upcoming" else "Completed"
                with st.container(border=True):
                    st.markdown(f"**{a['doctor_name']}** [{status_icon}]")
                    st.markdown(f"<div style='font-size: 15px; font-weight: 600; color: #243447;'>{a['hospital']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 15px; color: #234B70; font-weight: 600;'>Date: {a['appointment_date']} at {a['appointment_time']}</div>", unsafe_allow_html=True)
                    st.caption(f"Purpose: {a['purpose']} &bull; Notes: {a['notes'] or 'None'}")

    # 5. HEALTH SUMMARY
    elif page == "Health Summary":
        render_health_view(user, page="Health Summary")

    render_clinical_disclaimer()
