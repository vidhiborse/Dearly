from datetime import date, datetime, timedelta
import streamlit as st
from services.appointment_service import get_appointments
from services.auth_service import get_accessible_elderly_wards
from services.health_service import (
    SUPPORTED_MEASUREMENTS,
    OBSERVATION_CATEGORIES,
    add_health_measurement,
    add_health_observation,
    add_health_reading,
    correct_health_reading,
    create_health_chart,
    evaluate_reference_range,
    export_health_records_csv,
    get_health_observations,
    get_health_readings,
    get_health_record_audit,
    get_health_summary,
    get_latest_vitals,
)
from services.permissions import can_manage_health_records, can_view_health_records


def render_health_view(user: dict, page: str = "Health Records"):
    """
    Renders the accessible Health Records & Health Monitoring dashboard.
    Strictly follows DESIGN.md with high-contrast elements, zero emojis, and explicit non-diagnostic disclaimers.
    """
    role = user.get("role", "")
    accessible_wards = get_accessible_elderly_wards(user)

    if not accessible_wards:
        st.warning("No elderly care profiles are currently linked to your account.")
        return

    # Ward resolution
    if role == "elderly":
        selected_ward = accessible_wards[0]
        selected_ward_id = selected_ward["id"]
        ward_name = selected_ward["name"]
    else:
        ward_options = {w["id"]: f"{w['name']} (Age {w.get('age', 'N/A')})" for w in accessible_wards}
        default_idx = 0
        if "selected_ward_id" in st.session_state and st.session_state.selected_ward_id in ward_options:
            default_idx = list(ward_options.keys()).index(st.session_state.selected_ward_id)

        col_w1, col_w2 = st.columns([2, 1], vertical_alignment="bottom")
        with col_w1:
            selected_ward_id = st.selectbox(
                "Select Elderly Individual",
                options=list(ward_options.keys()),
                format_func=lambda x: ward_options[x],
                index=default_idx,
                key="health_ward_selector",
            )
        st.session_state.selected_ward_id = selected_ward_id
        selected_ward = next(w for w in accessible_wards if w["id"] == selected_ward_id)
        ward_name = selected_ward["name"]

    can_edit = can_manage_health_records(user, selected_ward_id)

    # Page Header
    st.markdown(
        f"""
        <div style="margin-bottom: 12px;">
            <h1 style="font-size: 26px; color: #234B70; margin: 0 0 4px 0; font-weight: 700;">
                Health Records & Monitoring
            </h1>
            <p style="font-size: 17px; color: #607086; margin: 0;">
                Clinical vital logs, trend visualization, and wellbeing observations for <strong>{ward_name}</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Prominent Non-Diagnostic Medical Disclaimer
    st.markdown(
        """
        <div style="background-color: #F8FAFC; border-left: 4px solid #234B70; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 15px; color: #243447; line-height: 1.5;">
                <strong>Medical Notice:</strong> Dearly is designed for care coordination and personal health tracking only.
                It is <strong>not</strong> a medical diagnostic system and never replaces professional clinical advice.
                Reference ranges shown are informational guidelines. If you suspect an emergency, immediately contact local emergency medical services.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Five Accessible Tabs
    tabs = st.tabs([
        "Health Summary & Latest Vitals",
        "Health Trends & Charts",
        "Record History & Audit",
        "Record New Measurement",
        "Wellbeing Observations",
    ])

    # =========================================================================
    # TAB 1: HEALTH SUMMARY & LATEST VITALS
    # =========================================================================
    with tabs[0]:
        st.markdown("### Latest Recorded Vitals")
        summary = get_health_summary(selected_ward_id, user=user)
        latest_vitals = summary["latest_vitals"]

        all_readings = get_health_readings(selected_ward_id, limit=100, user=user)

        if not all_readings:
            st.info(
                f"No health records currently exist for {ward_name}. "
                + ("Use the 'Record New Measurement' tab to log the first vital reading." if can_edit else "Your care circle team has not recorded any vitals yet.")
            )
        else:
            # 6 Key Vitals Grid
            vital_items = [
                ("Blood Pressure", latest_vitals.get("Blood Pressure")),
                ("Blood Sugar", latest_vitals.get("Blood Sugar") or latest_vitals.get("Blood Sugar (Fasting)")),
                ("Heart Rate", latest_vitals.get("Heart Rate")),
                ("Oxygen Saturation (SpO2)", latest_vitals.get("Oxygen Saturation (SpO2)")),
                ("Weight", latest_vitals.get("Weight")),
                ("Body Temperature", latest_vitals.get("Body Temperature")),
            ]

            c1, c2 = st.columns(2, gap="medium")
            for idx, (v_name, v_data) in enumerate(vital_items):
                target_col = c1 if idx % 2 == 0 else c2
                with target_col:
                    with st.container(border=True):
                        st.markdown(f"<div style='font-size: 16px; font-weight: 600; color: #234B70;'>{v_name}</div>", unsafe_allow_html=True)
                        if v_data:
                            val_str = v_data.get("reading_value") or "Recorded"
                            rec_dt = f"{v_data.get('recorded_on')} {v_data.get('recorded_time') or ''}".strip()
                            st.markdown(f"<div style='font-size: 26px; font-weight: 700; color: #1E293B; margin: 6px 0;'>{val_str}</div>", unsafe_allow_html=True)

                            # Range status badge
                            if v_data.get("is_outside_range"):
                                st.markdown(
                                    f"""<div style='display: inline-block; background-color: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; margin-bottom: 6px;'>
                                        {v_data.get('status_label', 'Outside standard reference range')}
                                    </div>""",
                                    unsafe_allow_html=True,
                                )
                                if v_data.get("warning"):
                                    st.caption(v_data["warning"])
                            else:
                                st.markdown(
                                    f"""<div style='display: inline-block; background-color: #ECFDF5; color: #065F46; padding: 4px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; margin-bottom: 6px;'>
                                        {v_data.get('status_label', 'Within standard reference range')}
                                    </div>""",
                                    unsafe_allow_html=True,
                                )

                            st.caption(f"Recorded: {rec_dt} &bull; Context: {v_data.get('notes') or v_data.get('context') or 'Routine log'}")
                        else:
                            st.markdown("<div style='font-size: 20px; color: #94A3B8; margin: 10px 0;'>No reading logged</div>", unsafe_allow_html=True)
                            st.caption("No historical records found for this measurement type.")

            st.write("")
            # Summary Metrics Bar
            with st.container(border=True):
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Total Health Readings", summary["total_readings_in_period"])
                with m2:
                    st.metric("First Recorded Date", summary["first_recorded_date"] or "N/A")
                with m3:
                    st.metric("Most Recent Log", summary["last_recorded_date"] or "N/A")

            # Informational Reference Range Guide
            with st.expander("View Standard Reference Ranges (Informational Guide)"):
                st.markdown(
                    """
                    | Vital Sign | Typical Adult Reference Range | Measurement Context |
                    |---|---|---|
                    | **Blood Pressure** | Systolic: 90 - 120 mmHg<br>Diastolic: 60 - 80 mmHg | Resting, seated for 5 minutes |
                    | **Fasting Blood Sugar** | 70 - 99 mg/dL (3.9 - 5.5 mmol/L) | Morning before food or drink |
                    | **Post-Meal Blood Sugar** | Less than 140 mg/dL (7.8 mmol/L) | 2 hours after a meal |
                    | **Resting Heart Rate** | 60 - 100 bpm | Seated at rest |
                    | **Oxygen Saturation (SpO2)** | 95% - 100% | Pulse oximeter reading |
                    | **Oral Temperature** | 36.1 - 37.2 °C (97.0 - 99.0 °F) | Standard oral digital thermometer |

                    *Note: Target ranges vary based on individual physician care plans, age, and existing diagnoses. Always consult the attending doctor.*
                    """
                )

    # =========================================================================
    # TAB 2: HEALTH TRENDS & CHARTS
    # =========================================================================
    with tabs[1]:
        st.markdown("### Health Trend Analysis")
        st.markdown("<p style='font-size: 16px; color: #607086;'>Interactive trends charted directly from actual database measurements.</p>", unsafe_allow_html=True)

        chart_type = st.selectbox(
            "Select Measurement Trend to Inspect",
            ["Blood Pressure", "Blood Sugar", "Weight", "Heart Rate", "Oxygen Saturation (SpO2)"],
            key="chart_vital_selector",
        )

        all_readings = get_health_readings(selected_ward_id, limit=200, user=user)
        matching_readings = [r for r in all_readings if chart_type.lower() in r["reading_type"].lower()]

        if len(matching_readings) == 0:
            st.info(f"No {chart_type} readings found in the database. Log measurements to see trends.")
        elif len(matching_readings) == 1:
            single = matching_readings[0]
            st.info(f"Only 1 {chart_type} reading recorded ({single['reading_value']} on {single['recorded_on']}). At least 2 readings are required to plot a historical trend line.")
        else:
            fig = create_health_chart(all_readings, chart_type)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Unable to generate trend chart for {chart_type}. Please check measurement values.")

    # =========================================================================
    # TAB 3: RECORD HISTORY & AUDIT TRAIL
    # =========================================================================
    with tabs[2]:
        st.markdown("### Chronological Health Records")

        # Filters Bar
        f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.2, 1.2, 1])
        with f_col1:
            filter_type = st.selectbox(
                "Filter by Measurement",
                ["All Measurements"] + SUPPORTED_MEASUREMENTS,
                key="filter_hist_type",
            )
        with f_col2:
            start_date = st.date_input("From Date", value=date.today() - timedelta(days=30), key="filter_hist_start")
        with f_col3:
            end_date = st.date_input("To Date", value=date.today(), key="filter_hist_end")
        with f_col4:
            limit_val = st.selectbox("Max Records", [25, 50, 100, 200], index=1, key="filter_hist_limit")

        sel_type = None if filter_type == "All Measurements" else filter_type
        hist_readings = get_health_readings(
            elderly_user_id=selected_ward_id,
            reading_type=sel_type,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=limit_val,
            user=user,
        )

        # CSV Export Action
        csv_data = export_health_records_csv(
            elderly_user_id=selected_ward_id,
            reading_type=sel_type,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            user=user,
        )
        st.download_button(
            label="Export Filtered Records to CSV",
            data=csv_data,
            file_name=f"dearly_health_records_{ward_name.replace(' ', '_').lower()}_{date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=False,
        )

        st.write("")
        if not hist_readings:
            st.info("No records matched the selected filters.")
        else:
            for r in hist_readings:
                with st.container(border=True):
                    hc1, hc2 = st.columns([3, 1], vertical_alignment="top")
                    with hc1:
                        st.markdown(
                            f"<div style='font-size: 18px; font-weight: 700; color: #234B70;'>{r['reading_type']}: {r['reading_value']}</div>",
                            unsafe_allow_html=True,
                        )
                        ctx_text = f"Context: {r['context']}" if r.get("context") else ""
                        note_text = f"Notes: {r['notes']}" if r.get("notes") else ""
                        meta_parts = [p for p in [ctx_text, note_text] if p]
                        if meta_parts:
                            st.caption(" &bull; ".join(meta_parts))

                        if r.get("is_corrected"):
                            st.markdown(
                                f"""<div style='display: inline-block; background-color: #FEF3C7; color: #92400E; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-top: 4px;'>
                                    Corrected Record &bull; Reason: {r.get('correction_notes', 'Record updated')}
                                </div>""",
                                unsafe_allow_html=True,
                            )

                    with hc2:
                        dt_label = f"{r['recorded_on']} {r.get('recorded_time') or ''}".strip()
                        st.markdown(f"<div style='text-align: right; color: #607086; font-size: 14px;'>{dt_label}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align: right; color: #607086; font-size: 13px;'>By: {r.get('recorded_by_name', 'Caregiver')}</div>", unsafe_allow_html=True)

                    # Expanders: View Audit & Correct Record (if permitted)
                    with st.expander(f"View Details & Audit for Reading #{r['id']}"):
                        audit_rows = get_health_record_audit(reading_id=r["id"], user=user)
                        if audit_rows:
                            st.markdown("##### Correction Audit History")
                            for a in audit_rows:
                                st.markdown(
                                    f"- **{a['changed_at']}** by **{a['changed_by_name']}**: Changed from `{a['old_reading_value']}` to `{a['new_reading_value']}`. Reason: *{a['reason_for_change']}*"
                                )
                        else:
                            st.caption("Original recorded reading. No corrections made.")

                        if can_edit:
                            st.divider()
                            st.markdown("##### Correct this Health Record")
                            st.caption("Updating a record preserves the original values in the immutable audit log.")
                            with st.form(f"correct_reading_form_{r['id']}"):
                                new_val = st.text_input("New Reading Value", value=r["reading_value"])
                                corr_reason = st.text_input("Reason for Correction (Required)", placeholder="e.g. Typo in systolic value / Re-measured with calibrated cuff")
                                corr_notes = st.text_input("Updated Clinical Notes", value=r.get("notes") or "")
                                submit_corr = st.form_submit_button("Save Correction with Audit Trail", type="primary", use_container_width=True)

                                if submit_corr:
                                    try:
                                        correct_health_reading(
                                            reading_id=r["id"],
                                            elderly_user_id=selected_ward_id,
                                            new_value=new_val,
                                            reason=corr_reason,
                                            changed_by=user["id"],
                                            new_notes=corr_notes,
                                            user=user,
                                        )
                                        st.success("Record corrected successfully with audit trail.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Correction failed: {str(e)}")

    # =========================================================================
    # TAB 4: RECORD NEW MEASUREMENT
    # =========================================================================
    with tabs[3]:
        st.markdown("### Record Health Measurement")

        if not can_edit:
            st.warning("You have read-only permissions for this profile. Only the senior or an authorized editor caregiver can record new measurements.")
        else:
            meas_type = st.selectbox(
                "Measurement Type",
                SUPPORTED_MEASUREMENTS,
                key="new_meas_type",
            )

            with st.form("add_measurement_form"):
                m_c1, m_c2 = st.columns(2)
                sys_val = None
                dia_val = None
                num_val = None
                unit_val = ""
                ctx_val = ""

                # Dynamic form inputs depending on measurement type
                if meas_type == "Blood Pressure":
                    with m_c1:
                        sys_val = st.number_input("Systolic (mmHg)", min_value=50, max_value=280, value=120, step=1)
                    with m_c2:
                        dia_val = st.number_input("Diastolic (mmHg)", min_value=30, max_value=180, value=80, step=1)
                    ctx_val = st.selectbox("Measurement Context", ["Resting (Morning)", "Resting (Evening)", "Post-Activity", "Sitting", "Lying down"])
                    unit_val = "mmHg"

                elif meas_type == "Blood Sugar":
                    with m_c1:
                        num_val = st.number_input("Blood Sugar Value", min_value=20.0, max_value=800.0, value=100.0, step=1.0)
                    with m_c2:
                        unit_val = st.selectbox("Unit", ["mg/dL", "mmol/L"])
                    ctx_val = st.selectbox("Measurement Timing Context", ["fasting", "before_meal", "after_meal", "random"])

                elif meas_type == "Weight":
                    with m_c1:
                        num_val = st.number_input("Weight Value", min_value=15.0, max_value=350.0, value=65.0, step=0.1)
                    with m_c2:
                        unit_val = st.selectbox("Unit", ["kg", "lb"])
                    ctx_val = st.selectbox("Timing", ["Morning (Pre-Breakfast)", "Evening", "Routine Weigh-In"])

                elif meas_type == "Heart Rate":
                    with m_c1:
                        num_val = st.number_input("Heart Rate (bpm)", min_value=30, max_value=220, value=72, step=1)
                    with m_c2:
                        unit_val = "bpm"
                        st.text_input("Unit", value="bpm", disabled=True)
                    ctx_val = st.selectbox("Context", ["Resting", "Post-Walking", "Morning checkup"])

                elif meas_type == "Oxygen Saturation (SpO2)":
                    with m_c1:
                        num_val = st.number_input("Oxygen Saturation (%)", min_value=60.0, max_value=100.0, value=98.0, step=1.0)
                    with m_c2:
                        unit_val = "%"
                        st.text_input("Unit", value="%", disabled=True)
                    ctx_val = st.selectbox("Context", ["Resting room air", "With supplemental oxygen", "Post-exercise"])

                elif meas_type == "Body Temperature":
                    with m_c1:
                        num_val = st.number_input("Temperature", min_value=32.0, max_value=108.0, value=36.6, step=0.1)
                    with m_c2:
                        unit_val = st.selectbox("Unit", ["°C", "°F"])
                    ctx_val = st.selectbox("Method", ["Oral thermometer", "Forehead scanner", "Axillary (armpit)"])

                f_c1, f_c2 = st.columns(2)
                with f_c1:
                    meas_date = st.date_input("Date Recorded", value=date.today())
                with f_c2:
                    meas_time = st.text_input("Time Recorded", value=datetime.now().strftime("%I:%M %p"))

                notes_val = st.text_input("Clinical Observations / Notes (Optional)", placeholder="e.g. Measured before taking morning hypertension pill")

                # Optional Link to an Appointment
                recent_appts = get_appointments(selected_ward_id, status="all", limit=10, user=user)
                appt_options = {0: "None (Standard Home Check)"}
                for a in recent_appts:
                    appt_options[a["id"]] = f"Dr. {a['doctor_name']} ({a['appointment_date']}) - {a['hospital']}"

                selected_appt_id = st.selectbox(
                    "Link Reading to Doctor Appointment (Optional)",
                    options=list(appt_options.keys()),
                    format_func=lambda x: appt_options[x],
                )
                final_appt_id = selected_appt_id if selected_appt_id != 0 else None

                submit_meas = st.form_submit_button("Record Health Measurement", use_container_width=True, type="primary")

                if submit_meas:
                    try:
                        raw_val = f"{sys_val}/{dia_val} mmHg" if meas_type == "Blood Pressure" else f"{num_val} {unit_val}"
                        rid = add_health_reading(
                            elderly_user_id=selected_ward_id,
                            reading_type=meas_type,
                            reading_value=raw_val,
                            recorded_on=meas_date.isoformat(),
                            notes=notes_val,
                            recorded_by=user["id"],
                            unit=unit_val,
                            systolic=int(sys_val) if sys_val is not None else None,
                            diastolic=int(dia_val) if dia_val is not None else None,
                            numeric_value=float(num_val) if num_val is not None else None,
                            context=ctx_val,
                            recorded_time=meas_time,
                            appointment_id=final_appt_id,
                            user=user,
                        )
                        st.success(f"Health measurement recorded successfully (Record #{rid}).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to record measurement: {str(e)}")

    # =========================================================================
    # TAB 5: WELLBEING OBSERVATIONS
    # =========================================================================
    with tabs[4]:
        st.markdown("### Qualitative Wellbeing Observations")
        st.markdown("<p style='font-size: 16px; color: #607086;'>Log and track day-to-day observations on sleep quality, appetite, mobility, and mood.</p>", unsafe_allow_html=True)

        if can_edit:
            with st.expander("Record New Wellbeing Observation", expanded=False):
                with st.form("add_observation_form"):
                    obs_text = st.text_area("Observation Note (Required)", placeholder="e.g. Reported sleeping deeply for 8 hours; had good breakfast appetite.")
                    o_c1, o_c2 = st.columns(2)
                    with o_c1:
                        obs_cat = st.selectbox(
                            "Observation Category",
                            OBSERVATION_CATEGORIES,
                            format_func=lambda x: x.replace("_", " ").title(),
                        )
                    with o_c2:
                        obs_date = st.date_input("Date Observed", value=date.today())

                    submit_obs = st.form_submit_button("Save Wellbeing Observation", type="primary", use_container_width=True)
                    if submit_obs:
                        try:
                            oid = add_health_observation(
                                elderly_user_id=selected_ward_id,
                                observation_text=obs_text,
                                recorded_by=user["id"],
                                category=obs_cat,
                                recorded_on=obs_date.isoformat(),
                                user=user,
                            )
                            st.success(f"Observation logged successfully (Record #{oid}).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save observation: {str(e)}")

        st.write("")
        st.markdown("##### Recent Observations Log")
        observations = get_health_observations(selected_ward_id, limit=30, user=user)

        if not observations:
            st.info("No wellbeing observations recorded yet.")
        else:
            for obs in observations:
                with st.container(border=True):
                    oc1, oc2 = st.columns([3, 1], vertical_alignment="top")
                    with oc1:
                        cat_label = obs.get("category", "general").replace("_", " ").title()
                        st.markdown(
                            f"""<span style='background-color: #EDF2F7; color: #234B70; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-weight: 600;'>
                                {cat_label}
                            </span>""",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"<p style='font-size: 16px; color: #1E293B; margin: 8px 0 0 0;'>{obs['observation_text']}</p>", unsafe_allow_html=True)
                        if obs.get("appointment_doctor"):
                            st.caption(f"Linked to visit with Dr. {obs['appointment_doctor']} ({obs.get('appointment_date')})")

                    with oc2:
                        obs_time = f"{obs['recorded_on']} {obs.get('recorded_time') or ''}".strip()
                        st.markdown(f"<div style='text-align: right; color: #607086; font-size: 14px;'>{obs_time}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align: right; color: #607086; font-size: 13px;'>By: {obs.get('recorded_by_name', 'Caregiver')}</div>", unsafe_allow_html=True)
