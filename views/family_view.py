import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, date
from services.auth_service import get_accessible_elderly_wards
from services.medication_service import get_today_schedule, get_adherence_metrics
from services.appointment_service import get_appointments, get_next_upcoming_appointment
from services.health_service import get_health_readings, get_latest_vitals
from services.care_circle_service import get_care_circle_members, get_elderly_profile
from services.activity_service import get_recent_activities
from services.summary_service import generate_daily_care_summary
from views.common import render_hero_header, render_clinical_disclaimer

def render_family_view(user: dict):
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
        role_badge="Family Observability",
    )

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
    <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 10px; padding: 14px 18px; margin-bottom: 22px;">
        <span style="font-size: 17px; font-weight: 700; color: {banner_text};">{reassurance_msg}</span>
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("7-Day Adherence", f"{metrics['adherence_percentage']}%")
    with m2:
        st.metric("Confirmed Doses", f"{metrics['total_taken']} doses")
    with m3:
        st.metric("Next Doctor Visit", next_appt["appointment_date"] if next_appt else "None soon")
    with m4:
        vitals = get_latest_vitals(elderly_id)
        latest_bp = vitals["Blood Pressure"]["reading_value"] if vitals.get("Blood Pressure") else "—"
        st.metric("Latest Blood Pressure", latest_bp)

    st.write("")

    tab_summary, tab_trends, tab_schedule, tab_appts, tab_activity = st.tabs([
        "Daily Care Briefing",
        "Adherence & Health Trends",
        "Medication Schedule",
        "Doctor Appointments",
        "Care Activity Stream",
    ])

    # 1. DAILY CARE SUMMARY
    with tab_summary:
        summary_md = generate_daily_care_summary(elderly_name, elderly_id)
        st.markdown(f"""
        <div class="dearly-card">
            {summary_md}
        </div>
        """, unsafe_allow_html=True)

    # 2. ADHERENCE & HEALTH TRENDS (PLOTLY)
    with tab_trends:
        st.markdown("### 7-Day Medication Adherence Breakdown")
        breakdown = metrics.get("daily_breakdown", {})
        dates = list(breakdown.keys())
        taken_series = [breakdown[d]["taken"] for d in dates]
        missed_series = [breakdown[d]["missed"] for d in dates]
        skipped_series = [breakdown[d]["skipped"] for d in dates]

        formatted_dates = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in dates]

        fig_adherence = go.Figure()
        fig_adherence.add_trace(go.Bar(
            x=formatted_dates,
            y=taken_series,
            name="Taken",
            marker_color="#23815C",
        ))
        fig_adherence.add_trace(go.Bar(
            x=formatted_dates,
            y=missed_series,
            name="Missed",
            marker_color="#B84040",
        ))
        fig_adherence.add_trace(go.Bar(
            x=formatted_dates,
            y=skipped_series,
            name="Skipped",
            marker_color="#A0AEC0",
        ))
        fig_adherence.update_layout(
            barmode="stack",
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color="#243447"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#243447")),
            yaxis=dict(title="Doses", gridcolor="#EDF2F7", titlefont=dict(color="#243447"), tickfont=dict(color="#243447")),
            xaxis=dict(gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
        )
        st.plotly_chart(fig_adherence, use_container_width=True)

        st.markdown("---")
        st.markdown("### Health Readings History")
        readings = get_health_readings(elderly_id, limit=20)
        
        sugar_readings = [r for r in readings if "Blood Sugar" in r["reading_type"]]
        if len(sugar_readings) >= 2:
            sugar_readings_sorted = sorted(sugar_readings, key=lambda x: x["recorded_on"])
            s_dates = [r["recorded_on"] for r in sugar_readings_sorted]
            s_vals = []
            for r in sugar_readings_sorted:
                val_num = ''.join(c for c in r["reading_value"] if c.isdigit())
                s_vals.append(int(val_num) if val_num else 100)

            fig_sugar = go.Figure()
            fig_sugar.add_trace(go.Scatter(
                x=s_dates,
                y=s_vals,
                mode="lines+markers",
                name="Fasting Sugar (mg/dL)",
                line=dict(color="#234B70", width=3),
                marker=dict(size=8, color="#234B70"),
            ))
            fig_sugar.add_hrect(
                y0=70, y1=125,
                fillcolor="#23815C", opacity=0.08,
                line_width=0,
                annotation_text="Target Range (70-125 mg/dL)",
                annotation_position="top left",
                annotation_font_color="#23815C",
            )
            fig_sugar.update_layout(
                title=dict(text="Fasting Blood Sugar Trend (mg/dL)", font=dict(color="#234B70", size=16)),
                height=280,
                margin=dict(l=20, r=20, t=40, b=20),
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                font=dict(family="Plus Jakarta Sans, sans-serif", size=14, color="#243447"),
                yaxis=dict(title="mg/dL", gridcolor="#EDF2F7", titlefont=dict(color="#243447"), tickfont=dict(color="#243447")),
                xaxis=dict(gridcolor="#EDF2F7", tickfont=dict(color="#243447")),
            )
            st.plotly_chart(fig_sugar, use_container_width=True)
        else:
            st.info("Additional vitals logs needed to chart blood sugar trends.")

    # 3. MEDICATION SCHEDULE
    with tab_schedule:
        st.markdown(f"### Prescribed Regimen for {elderly_name}")
        for s in today_schedule:
            time_str = s["schedule_time"]
            m_name = s["medicine_name"]
            dosage = s["dosage"]
            timing = s["meal_timing"] or ""
            status = s["status"]

            status_badge = {
                "taken": '<span class="badge-taken">TAKEN</span>',
                "pending": '<span class="badge-pending">UPCOMING</span>',
                "missed": '<span class="badge-missed">MISSED</span>',
                "skipped": '<span class="badge-skipped">SKIPPED</span>',
            }.get(status, '<span class="badge-pending">UPCOMING</span>')

            with st.container(border=True):
                c_info, c_badge = st.columns([3, 1], vertical_alignment="center")
                with c_info:
                    st.markdown(f"""
                    <div>
                        <span style="font-size: 18px; font-weight: 700; color: #234B70;">{time_str}</span>
                        <span style="font-size: 16px; font-weight: 700; color: #243447; margin-left: 12px;">{m_name} {dosage}</span>
                        <span style="font-size: 14px; color: #607086; margin-left: 10px;">({timing})</span>
                        <div style="font-size: 13px; color: #607086; margin-top: 4px;">Purpose: {s['purpose'] or 'Daily routine'}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_badge:
                    st.markdown(f"<div style='text-align: right;'>{status_badge}</div>", unsafe_allow_html=True)

    # 4. DOCTOR APPOINTMENTS
    with tab_appts:
        st.markdown("### Medical Appointments Calendar")
        appts = get_appointments(elderly_id)
        if not appts:
            st.info("No medical appointments scheduled.")
        else:
            for a in appts:
                status_icon = "Upcoming" if a["status"] == "upcoming" else "Completed"
                st.markdown(f"""
                <div class="dearly-card" style="margin-bottom: 12px; padding: 16px 20px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 17px; font-weight: 700; color: #234B70;">{a['doctor_name']}</span>
                        <span style="font-size: 13px; font-weight: 600; color: #234B70;">[{status_icon}]</span>
                    </div>
                    <div style="font-size: 15px; font-weight: 600; color: #243447; margin-top: 4px;">{a['hospital']}</div>
                    <div style="font-size: 15px; color: #234B70; font-weight: 600; margin-top: 4px;">Date: {a['appointment_date']} at {a['appointment_time']}</div>
                    <div style="font-size: 13px; color: #607086; margin-top: 6px;">Purpose: {a['purpose']}</div>
                    <div style="font-size: 13px; color: #607086; margin-top: 2px;">Notes: {a['notes'] or 'None'}</div>
                </div>
                """, unsafe_allow_html=True)

    # 5. CARE ACTIVITY STREAM
    with tab_activity:
        st.markdown("### Recent Care Circle Updates")
        activities = get_recent_activities(elderly_id, limit=20)
        for act in activities:
            st.markdown(f"""
            <div style="background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: 700; color: #234B70;">{act['action']}</span>
                    <span style="font-size: 12px; color: #607086;">{act['created_at']}</span>
                </div>
                <div style="font-size: 14px; color: #243447; margin-top: 4px;">{act['details']}</div>
                <div style="font-size: 12px; color: #607086; margin-top: 2px;">Actor: {act['actor_name']} ({act['actor_role']})</div>
            </div>
            """, unsafe_allow_html=True)

    # Primary Caregiver Contact Info for Family
    st.markdown("---")
    st.markdown("### Primary Caregiver Contact")
    members = get_care_circle_members(elderly_id)
    caregiver = next((m for m in members if m["permission_level"] == "editor"), None)
    if caregiver:
        st.markdown(f"""
        <div style="background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 10px; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div>
                <div style="font-size: 17px; font-weight: 700; color: #234B70;">{caregiver['name']}</div>
                <div style="font-size: 14px; color: #243447;">{caregiver['relationship']} &bull; {caregiver['email']}</div>
            </div>
            <div style="font-size: 17px; font-weight: 700; color: #234B70;">
                Phone: {caregiver['phone'] or '+91 98200 12345'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    render_clinical_disclaimer()
