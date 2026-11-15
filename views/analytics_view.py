import streamlit as st
from datetime import date, datetime, timedelta
import plotly.graph_objects as go

from services.auth_service import get_accessible_elderly_wards
from services.analytics_service import (
    ANALYTICS_SAFETY_NOTICE,
    resolve_date_range,
    get_analytics_overview,
    get_medication_adherence_analytics,
    get_health_trend_analytics,
    get_appointment_analytics,
    get_care_activity_analytics,
    generate_analytics_csv_report,
)
from services.health_service import create_health_chart


def render_analytics_view(user: dict):
    """
    Renders the dedicated Analytics & Reports dashboard for Dearly.
    Accessible to Elderly (own profile), Caregivers (linked wards), and Family (linked wards).
    Follows DESIGN.md: high contrast, 18px body scale, calm healthcare palette, zero emojis.
    """
    role = user.get("role", "")
    user_id = user.get("id")

    # Header section
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h1 style="font-size: 26px; color: #234B70; margin: 0 0 4px 0; font-weight: 700;">
                Analytics & Reports
            </h1>
            <p style="font-size: 17px; color: #607086; margin: 0;">
                Comprehensive health adherence, clinical vitals, appointment insights, and activity reports.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ward selection for multi-ward caregivers and family members
    selected_ward_id = None
    selected_ward_name = ""

    if role == "elderly":
        selected_ward_id = user_id
        selected_ward_name = user.get("name", "My Profile")
    else:
        wards = get_accessible_elderly_wards(user)
        if not wards:
            st.info("No elderly profiles are linked to your account yet. You can connect via Care Circle invitations.")
            return

        ward_options = {w["id"]: f"{w['name']} (ID #{w['id']})" for w in wards}
        selected_ward_id = st.selectbox(
            "Select Care Recipient:",
            options=list(ward_options.keys()),
            format_func=lambda x: ward_options[x],
            key="analytics_ward_selector",
        )
        selected_ward_name = next((w["name"] for w in wards if w["id"] == selected_ward_id), "Care Recipient")

    # Date Range & Period Controls
    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
    c_p1, c_p2, c_p3 = st.columns([2, 2, 2])

    with c_p1:
        period_choice = st.selectbox(
            "Report Time Period:",
            options=["Last 30 Days", "Last 7 Days", "Last 90 Days", "Custom Range"],
            index=0,
            key="analytics_period_choice",
        )

    period_key_map = {
        "Last 7 Days": "last_7_days",
        "Last 30 Days": "last_30_days",
        "Last 90 Days": "last_90_days",
        "Custom Range": "custom",
    }
    p_key = period_key_map.get(period_choice, "last_30_days")

    custom_start = None
    custom_end = None
    if p_key == "custom":
        with c_p2:
            custom_start = st.date_input("Start Date:", value=date.today() - timedelta(days=30), key="analytics_c_start")
        with c_p3:
            custom_end = st.date_input("End Date:", value=date.today(), key="analytics_c_end")

    start_date, end_date = resolve_date_range(p_key, custom_start, custom_end)

    st.markdown(
        f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px;">
            <span style="font-size: 15px; color: #234B70; font-weight: 600;">Active Report Window:</span>
            <span style="font-size: 15px; color: #1E293B; margin-left: 6px;">{start_date} to {end_date}</span>
            <span style="font-size: 14px; color: #607086; margin-left: 12px;">• Care Recipient: <strong>{selected_ward_name}</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 5 Functional Tabs
    tab_overview, tab_meds, tab_health, tab_appts, tab_export = st.tabs([
        "Overview Dashboard",
        "Medication Adherence",
        "Health Trends",
        "Appointment Analytics",
        "Care Activity & Export",
    ])

    # =========================================================================
    # TAB 1: OVERVIEW DASHBOARD
    # =========================================================================
    with tab_overview:
        overview = get_analytics_overview(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            user=user,
        )

        # Prominent Safety Notice
        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border-left: 4px solid #234B70; padding: 10px 14px; border-radius: 4px; margin-bottom: 18px;">
                <p style="margin: 0; font-size: 14px; color: #243447; line-height: 1.5;">
                    <strong>Clinical & Safety Disclaimer:</strong> {ANALYTICS_SAFETY_NOTICE}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Primary KPI Metrics
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        with kpi1:
            adh_val = f"{overview['adherence_percentage']}%" if overview["adherence_percentage"] is not None else "No due doses"
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; text-align: center;">
                    <div style="font-size: 14px; color: #607086; font-weight: 600;">Overall Adherence</div>
                    <div style="font-size: 26px; font-weight: 700; color: #234B70; margin: 6px 0;">{adh_val}</div>
                    <div style="font-size: 13px; color: #607086;">(Taken / Total Due) * 100</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi2:
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; text-align: center;">
                    <div style="font-size: 14px; color: #607086; font-weight: 600;">Doses Taken / Due</div>
                    <div style="font-size: 26px; font-weight: 700; color: #23815C; margin: 6px 0;">
                        {overview['taken_doses']} <span style="font-size: 18px; color: #607086;">/ {overview['total_due_doses']}</span>
                    </div>
                    <div style="font-size: 13px; color: #607086;">Past scheduled doses</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi3:
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; text-align: center;">
                    <div style="font-size: 14px; color: #607086; font-weight: 600;">Skipped & Overdue</div>
                    <div style="font-size: 26px; font-weight: 700; color: #B84040; margin: 6px 0;">
                        {overview['skipped_doses']} <span style="font-size: 16px; color: #607086;">skip</span> • {overview['overdue_doses']} <span style="font-size: 16px; color: #607086;">overdue</span>
                    </div>
                    <div style="font-size: 13px; color: #607086;">Requiring care attention</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with kpi4:
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; text-align: center;">
                    <div style="font-size: 14px; color: #607086; font-weight: 600;">Appointments</div>
                    <div style="font-size: 26px; font-weight: 700; color: #234B70; margin: 6px 0;">
                        {overview['completed_appointments']} <span style="font-size: 16px; color: #607086;">done</span> • {overview['upcoming_appointments']} <span style="font-size: 16px; color: #607086;">next</span>
                    </div>
                    <div style="font-size: 13px; color: #607086;">Doctor consultations</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

        # Secondary Summary Row
        s_col1, s_col2 = st.columns(2)

        with s_col1:
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <h3 style="font-size: 17px; color: #234B70; margin: 0 0 10px 0; font-weight: 600;">Clinical & Activity Volumes</h3>
                    <p style="font-size: 15px; color: #1E293B; margin: 4px 0;">
                        • <strong>Recorded Health Readings:</strong> {overview['health_readings_count']} measurements in window
                    </p>
                    <p style="font-size: 15px; color: #1E293B; margin: 4px 0;">
                        • <strong>Recorded Care Activities:</strong> {overview['recent_activities_count']} care events logged
                    </p>
                    <p style="font-size: 14px; color: #607086; margin-top: 8px;">
                        All analytics are computed strictly from real database records.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with s_col2:
            st.markdown(
                """
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                    <h3 style="font-size: 17px; color: #234B70; margin: 0 0 10px 0; font-weight: 600;">Adherence Calculation Standard</h3>
                    <p style="font-size: 15px; color: #1E293B; margin: 4px 0;">
                        • Formula: <code>(Taken Doses / Total Due Doses) x 100</code>
                    </p>
                    <p style="font-size: 15px; color: #1E293B; margin: 4px 0;">
                        • Future scheduled doses are strictly excluded from adherence counts.
                    </p>
                    <p style="font-size: 14px; color: #607086; margin-top: 8px;">
                        Pending doses whose scheduled time has not arrived do not lower adherence scores.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # =========================================================================
    # TAB 2: MEDICATION ADHERENCE ANALYTICS
    # =========================================================================
    with tab_meds:
        st.markdown(
            """
            <div style="margin-bottom: 14px;">
                <h2 style="font-size: 20px; color: #234B70; margin: 0 0 4px 0; font-weight: 600;">
                    Medication Adherence Analysis
                </h2>
                <p style="font-size: 15px; color: #607086; margin: 0;">
                    Daily and weekly adherence performance based on confirmed doses.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        med_data = get_medication_adherence_analytics(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            user=user,
        )

        if not med_data["has_data"]:
            st.info("No medication dose records found for this period. Future doses are excluded.")
        else:
            # Daily Adherence Trend Plotly Chart
            daily_list = med_data["daily_trend"]
            if daily_list:
                dates = [d["date"] for d in daily_list]
                taken_counts = [d["taken"] for d in daily_list]
                skipped_counts = [d["skipped"] for d in daily_list]
                overdue_counts = [d["overdue"] for d in daily_list]
                adherence_rates = [d["adherence_percentage"] for d in daily_list]

                fig = go.Figure()

                # Stacked Bars for Doses
                fig.add_trace(go.Bar(
                    x=dates,
                    y=taken_counts,
                    name="Taken Doses",
                    marker_color="#23815C",
                ))
                fig.add_trace(go.Bar(
                    x=dates,
                    y=skipped_counts,
                    name="Skipped Doses",
                    marker_color="#C47D15",
                ))
                fig.add_trace(go.Bar(
                    x=dates,
                    y=overdue_counts,
                    name="Overdue Doses",
                    marker_color="#B84040",
                ))

                # Trend Line for Adherence % (secondary y-axis)
                valid_adherence_pts = [
                    (dt, rate) for dt, rate in zip(dates, adherence_rates) if rate is not None
                ]
                if valid_adherence_pts:
                    x_pts, y_pts = zip(*valid_adherence_pts)
                    fig.add_trace(go.Scatter(
                        x=x_pts,
                        y=y_pts,
                        name="Daily Adherence (%)",
                        mode="lines+markers",
                        line=dict(color="#234B70", width=3),
                        marker=dict(size=6, color="#234B70"),
                        yaxis="y2",
                    ))

                fig.update_layout(
                    title="Daily Dose Confirmations and Adherence Rate",
                    barmode="stack",
                    xaxis=dict(title="Date", tickangle=-30),
                    yaxis=dict(title="Dose Count", dtick=1),
                    yaxis2=dict(
                        title="Adherence (%)",
                        overlaying="y",
                        side="right",
                        range=[0, 105],
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=40, r=40, t=60, b=50),
                    height=360,
                )
                st.plotly_chart(fig, use_container_width=True)

            # Medication-wise Adherence Breakdown Table
            st.markdown(
                """
                <h3 style="font-size: 18px; color: #234B70; margin: 20px 0 10px 0; font-weight: 600;">
                    Medication-Wise Performance
                </h3>
                """,
                unsafe_allow_html=True,
            )

            breakdown = med_data["medication_breakdown"]
            if breakdown:
                table_rows = []
                for b in breakdown:
                    adh_str = f"{b['adherence_percentage']}%" if b["adherence_percentage"] is not None else "No due doses"
                    st_label = "Active" if b.get("active", 1) else "Inactive"
                    table_rows.append({
                        "Medication": b["medicine_name"],
                        "Dosage": b["dosage"],
                        "Total Due": b["total_due"],
                        "Taken": b["taken"],
                        "Skipped": b["skipped"],
                        "Overdue": b["overdue"],
                        "Adherence": adh_str,
                        "Status": st_label,
                    })
                st.dataframe(table_rows, use_container_width=True, hide_index=True)

            # Weekly Aggregation Table
            weekly = med_data["weekly_trend"]
            if weekly and len(weekly) > 1:
                st.markdown(
                    """
                    <h3 style="font-size: 18px; color: #234B70; margin: 20px 0 10px 0; font-weight: 600;">
                        Weekly Adherence Summary
                    </h3>
                    """,
                    unsafe_allow_html=True,
                )
                w_rows = [
                    {
                        "Week Range": w["week_label"],
                        "Total Due Doses": w["total_due"],
                        "Taken Doses": w["taken"],
                        "Adherence Rate": f"{w['adherence_percentage']}%" if w["adherence_percentage"] is not None else "No due doses",
                    }
                    for w in weekly
                ]
                st.dataframe(w_rows, use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 3: HEALTH TRENDS
    # =========================================================================
    with tab_health:
        st.markdown(
            """
            <div style="margin-bottom: 14px;">
                <h2 style="font-size: 20px; color: #234B70; margin: 0 0 4px 0; font-weight: 600;">
                    Health Trend Analytics
                </h2>
                <p style="font-size: 15px; color: #607086; margin: 0;">
                    Review clinical vital trends over time using actual recorded measurements.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Query preliminary to get available measurement types
        health_check = get_health_trend_analytics(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            user=user,
        )

        if not health_check["available_types"]:
            st.info("No health readings have been recorded for this care recipient in the selected period.")
        else:
            col_m1, col_m2 = st.columns([3, 2])
            with col_m1:
                sel_mtype = st.selectbox(
                    "Select Vital Sign / Measurement:",
                    options=health_check["available_types"],
                    key="analytics_vital_select",
                )

            # Fetch detailed for selected type to discover available units
            detail_check = get_health_trend_analytics(
                elderly_user_id=selected_ward_id,
                measurement_type=sel_mtype,
                start_date=start_date,
                end_date=end_date,
                user=user,
            )

            sel_unit = None
            if detail_check["available_units"] and len(detail_check["available_units"]) > 1:
                with col_m2:
                    sel_unit = st.selectbox(
                        "Unit (Incompatible Units Separated):",
                        options=detail_check["available_units"],
                        key="analytics_unit_select",
                    )

            # Query finalized dataset
            health_analytics = get_health_trend_analytics(
                elderly_user_id=selected_ward_id,
                measurement_type=sel_mtype,
                unit=sel_unit,
                start_date=start_date,
                end_date=end_date,
                user=user,
            )

            readings = health_analytics["readings"]
            count = health_analytics["count"]

            if count == 0:
                st.info(f"No records found for {sel_mtype} in the selected period.")
            else:
                # Summary Cards
                summary = health_analytics["summary"]
                if summary:
                    if sel_mtype == "Blood Pressure":
                        s1, s2, s3 = st.columns(3)
                        with s1:
                            st.metric("Systolic Range", f"{summary['systolic_min']} - {summary['systolic_max']} mmHg")
                        with s2:
                            st.metric("Diastolic Range", f"{summary['diastolic_min']} - {summary['diastolic_max']} mmHg")
                        with s3:
                            st.metric("Average BP", f"{int(summary['systolic_avg'])}/{int(summary['diastolic_avg'])} mmHg")
                    elif "avg_value" in summary:
                        s1, s2, s3 = st.columns(3)
                        with s1:
                            st.metric("Minimum Value", f"{summary['min_value']} {summary.get('unit', '')}")
                        with s2:
                            st.metric("Maximum Value", f"{summary['max_value']} {summary.get('unit', '')}")
                        with s3:
                            st.metric("Average Value", f"{summary['avg_value']} {summary.get('unit', '')}")

                # Plotly Chart or Insufficient Data Notice
                if not health_analytics["has_sufficient_data"]:
                    st.warning(
                        f"At least 2 measurements are required in the selected period to plot a trend line. "
                        f"Currently recorded: {count} reading on {readings[0]['recorded_on']} ({readings[0]['reading_value']})."
                    )
                else:
                    fig = create_health_chart(readings, sel_mtype)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                # Readings Table
                with st.expander(f"View All Recorded Readings ({count} items)", expanded=False):
                    tbl_rows = [
                        {
                            "Date": r["recorded_on"],
                            "Time": r.get("recorded_time", ""),
                            "Reading Value": r["reading_value"],
                            "Unit": r.get("unit", ""),
                            "Context": r.get("context", ""),
                            "Recorded By": r.get("recorded_by_name", "Caregiver"),
                            "Corrected": "Yes" if r.get("is_corrected") else "No",
                        }
                        for r in reversed(readings)
                    ]
                    st.dataframe(tbl_rows, use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 4: APPOINTMENT ANALYTICS
    # =========================================================================
    with tab_appts:
        st.markdown(
            """
            <div style="margin-bottom: 14px;">
                <h2 style="font-size: 20px; color: #234B70; margin: 0 0 4px 0; font-weight: 600;">
                    Doctor Appointment Analytics
                </h2>
                <p style="font-size: 15px; color: #607086; margin: 0;">
                    Consultation frequency, completion rates, and appointment status distributions.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        appts_analytics = get_appointment_analytics(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            user=user,
        )

        if not appts_analytics["has_data"]:
            st.info("No doctor appointments recorded for this care recipient in the selected period.")
        else:
            # Appointment Metric Cards
            ac1, ac2, ac3, ac4, ac5 = st.columns(5)
            with ac1:
                st.metric("Total Visits", appts_analytics["total_appointments"])
            with ac2:
                st.metric("Completed", appts_analytics["completed_count"])
            with ac3:
                st.metric("Upcoming", appts_analytics["upcoming_count"])
            with ac4:
                st.metric("Cancelled", appts_analytics["cancelled_count"])
            with ac5:
                st.metric("Missed", appts_analytics["missed_count"])

            st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

            # Visual Distribution Charts
            c_chart1, c_chart2 = st.columns(2)

            with c_chart1:
                type_dist = appts_analytics["type_distribution"]
                if type_dist:
                    types = [t["appointment_type"] for t in type_dist]
                    counts = [t["count"] for t in type_dist]
                    fig_types = go.Figure(data=[
                        go.Bar(
                            x=counts,
                            y=types,
                            orientation="h",
                            marker_color="#234B70",
                        )
                    ])
                    fig_types.update_layout(
                        title="Appointments by Type",
                        xaxis_title="Consultation Count",
                        yaxis=dict(autorange="reversed"),
                        height=280,
                        margin=dict(l=20, r=20, t=40, b=40),
                    )
                    st.plotly_chart(fig_types, use_container_width=True)

            with c_chart2:
                monthly = appts_analytics["monthly_distribution"]
                if monthly:
                    months = [m["month_key"] for m in monthly]
                    completed_m = [m["completed"] for m in monthly]
                    cancelled_m = [m["cancelled"] for m in monthly]
                    upcoming_m = [m["upcoming"] for m in monthly]

                    fig_months = go.Figure(data=[
                        go.Bar(name="Completed", x=months, y=completed_m, marker_color="#23815C"),
                        go.Bar(name="Upcoming", x=months, y=upcoming_m, marker_color="#234B70"),
                        go.Bar(name="Cancelled", x=months, y=cancelled_m, marker_color="#B84040"),
                    ])
                    fig_months.update_layout(
                        title="Monthly Appointment History",
                        barmode="stack",
                        yaxis_title="Visits",
                        height=280,
                        margin=dict(l=20, r=20, t=40, b=40),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    )
                    st.plotly_chart(fig_months, use_container_width=True)

            # Appointment Listing Table
            st.markdown(
                """
                <h3 style="font-size: 17px; color: #234B70; margin: 16px 0 8px 0; font-weight: 600;">
                    Appointments Log in Period
                </h3>
                """,
                unsafe_allow_html=True,
            )
            appts_rows = [
                {
                    "Date": a["appointment_date"],
                    "Time": a["appointment_time"],
                    "Doctor": a["doctor_name"],
                    "Specialization": a.get("specialization", ""),
                    "Hospital / Clinic": a["hospital"],
                    "Type": a["appointment_type"],
                    "Status": a["status"].capitalize(),
                }
                for a in appts_analytics["appointments"]
            ]
            st.dataframe(appts_rows, use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 5: CARE ACTIVITY & EXPORT
    # =========================================================================
    with tab_export:
        st.markdown(
            """
            <div style="margin-bottom: 14px;">
                <h2 style="font-size: 20px; color: #234B70; margin: 0 0 4px 0; font-weight: 600;">
                    Care Activity Analytics & Report Export
                </h2>
                <p style="font-size: 15px; color: #607086; margin: 0;">
                    Audit trail breakdown and RFC-4180 compliant CSV export for personal records.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_f1, col_f2 = st.columns([3, 2])
        with col_f1:
            act_cat_choice = st.selectbox(
                "Filter Activity Category:",
                options=["All Activities", "Medication & Doses", "Reminders & Alerts", "Care Circle", "Care Notes", "Emergency SOS"],
                index=0,
                key="analytics_act_cat",
            )

        cat_param_map = {
            "All Activities": "all",
            "Medication & Doses": "medication",
            "Reminders & Alerts": "reminder",
            "Care Circle": "circle",
            "Care Notes": "notes",
            "Emergency SOS": "emergency",
        }
        c_param = cat_param_map.get(act_cat_choice, "all")

        activity_analytics = get_care_activity_analytics(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            category_filter=c_param,
            user=user,
        )

        # Activity Distribution Bar Chart
        cat_counts = activity_analytics["category_counts"]
        if any(cat_counts.values()):
            fig_acts = go.Figure(data=[
                go.Bar(
                    x=list(cat_counts.keys()),
                    y=list(cat_counts.values()),
                    marker_color="#234B70",
                )
            ])
            fig_acts.update_layout(
                title="Activity Volumes by Care Category",
                yaxis_title="Logged Events",
                xaxis_tickangle=-20,
                height=260,
                margin=dict(l=20, r=20, t=40, b=50),
            )
            st.plotly_chart(fig_acts, use_container_width=True)

        # Activities Table
        activities = activity_analytics["activities"]
        if not activities:
            st.info("No activity records matching the category filter in the selected period.")
        else:
            st.markdown(
                f"""
                <h3 style="font-size: 17px; color: #234B70; margin: 16px 0 8px 0; font-weight: 600;">
                    Chronological Activity Stream ({len(activities)} items)
                </h3>
                """,
                unsafe_allow_html=True,
            )
            act_rows = [
                {
                    "Timestamp": a["created_at"],
                    "Action": a["action"],
                    "Details": a["details"],
                    "Actor": f"{a.get('actor_name') or 'System'} ({a.get('actor_role') or 'user'})",
                }
                for a in activities
            ]
            st.dataframe(act_rows, use_container_width=True, hide_index=True)

        st.markdown("<hr style='border: none; border-top: 1px solid #E2E8F0; margin: 24px 0;'>", unsafe_allow_html=True)

        # CSV Export Section
        st.markdown(
            """
            <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 18px;">
                <h3 style="font-size: 18px; color: #234B70; margin: 0 0 6px 0; font-weight: 600;">
                    Export Comprehensive Care Report (CSV)
                </h3>
                <p style="font-size: 15px; color: #607086; margin: 0 0 14px 0;">
                    Generates a complete RFC-4180 compliant CSV report containing the executive summary,
                    medication adherence breakdown, appointments, health measurements, and activity history.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        csv_content = generate_analytics_csv_report(
            elderly_user_id=selected_ward_id,
            start_date=start_date,
            end_date=end_date,
            user=user,
        )

        filename = f"dearly_report_{selected_ward_id}_{start_date}_to_{end_date}.csv"

        st.download_button(
            label="DOWNLOAD ANALYTICS REPORT (CSV)",
            data=csv_content.encode("utf-8"),
            file_name=filename,
            mime="text/csv",
            key="btn_download_analytics_csv",
        )
