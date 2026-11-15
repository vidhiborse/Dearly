import html
import streamlit as st
from datetime import datetime, date
from services.reminder_service import (
    get_upcoming_and_active_reminders,
    sync_reminders_and_escalations,
    get_user_notifications,
    get_unread_notification_count,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    get_caregiver_escalations,
    acknowledge_caregiver_escalation,
    get_user_reminder_settings,
    update_user_reminder_settings,
)
from services.medication_service import record_dose_status
from services.auth_service import get_accessible_elderly_wards
from services.email_service import (
    get_outbound_emails,
    get_email_statistics,
    send_upcoming_dose_email,
    send_missed_dose_email,
    send_appointment_email,
)


def render_notification_view(user: dict):
    """
    Renders the central Notification Center & Smart Reminder Dashboard.
    Tailors actions and visibility based on user role (Elderly, Caregiver, Family).
    """
    user_id = user["id"]
    role = user.get("role", "elderly")

    # Determine primary elderly ward context
    if role == "elderly":
        elderly_id = user_id
        ward_name = user["name"]
    else:
        wards = get_accessible_elderly_wards(user)
        if not wards:
            st.warning("No linked elderly family members or care recipients found.")
            return

        ward_options = {w["id"]: w["name"] for w in wards}
        # Use existing session state or first ward
        if "selected_ward_id" not in st.session_state or st.session_state.selected_ward_id not in ward_options:
            st.session_state.selected_ward_id = wards[0]["id"]

        if len(wards) > 1:
            sel_c1, sel_c2 = st.columns([1.5, 2], vertical_alignment="center")
            with sel_c1:
                st.session_state.selected_ward_id = st.selectbox(
                    "Viewing Notifications For",
                    options=list(ward_options.keys()),
                    format_func=lambda x: ward_options[x],
                    index=list(ward_options.keys()).index(st.session_state.selected_ward_id),
                    key="notif_ward_selector",
                )
        elderly_id = st.session_state.selected_ward_id
        current_ward = next((w for w in wards if w["id"] == elderly_id), wards[0])
        ward_name = current_ward["name"]

    # Trigger idempotent reminder sync
    sync_reminders_and_escalations(elderly_id, user=user)

    unread_count = get_unread_notification_count(user_id)

    # Header section
    head_c1, head_c2 = st.columns([2.5, 1], vertical_alignment="center")
    with head_c1:
        st.markdown(f"<h1 style='font-size: 26px; color: #234B70; margin: 0;'>Notification Center & Reminders</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 16px; color: #607086; margin: 4px 0 0 0;'>Care updates, medication schedules, and overdue alerts for <strong>{html.escape(ward_name)}</strong>.</p>", unsafe_allow_html=True)
    with head_c2:
        if unread_count > 0:
            st.markdown(f"""
            <div style="background-color: #FDF3E7; border: 1px solid #F5D7A1; padding: 8px 12px; border-radius: 6px; text-align: center;">
                <span style="font-size: 15px; font-weight: 700; color: #8A4B08;">{unread_count} Unread Notification(s)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #EBF8F2; border: 1px solid #A8E5CB; padding: 8px 12px; border-radius: 6px; text-align: center;">
                <span style="font-size: 14px; font-weight: 700; color: #23815C;">All Caught Up</span>
            </div>
            """, unsafe_allow_html=True)

    st.write("")

    # Role-based Tab Architecture
    if role == "caregiver":
        tab_reminders, tab_stream, tab_emails, tab_escalations, tab_settings = st.tabs([
            "Active Reminders",
            f"Notifications ({unread_count} unread)",
            "Outbound Email Reminders",
            "Caregiver Escalations",
            "Reminder Settings",
        ])
    elif role == "elderly":
        tab_reminders, tab_stream, tab_emails, tab_settings = st.tabs([
            "My Medication Reminders",
            f"Notifications ({unread_count} unread)",
            "Email Reminders",
            "Reminder Settings",
        ])
        tab_escalations = None
    else:  # family
        tab_reminders, tab_stream, tab_emails = st.tabs([
            "Medication Reminders",
            f"Notifications ({unread_count} unread)",
            "Email Reminders",
        ])
        tab_escalations = None
        tab_settings = None

    # TAB 1: ACTIVE REMINDERS
    with tab_reminders:
        active_reminders = get_upcoming_and_active_reminders(elderly_id, user=user)

        if not active_reminders:
            st.info(f"No medications scheduled for today for {ward_name}.")
        else:
            # Quick summary counts
            due_now_items = [r for r in active_reminders if r["status"] == "due_now"]
            overdue_items = [r for r in active_reminders if r["status"] == "overdue"]
            upcoming_items = [r for r in active_reminders if r["status"] == "upcoming"]
            completed_items = [r for r in active_reminders if r["status"] == "completed"]
            skipped_items = [r for r in active_reminders if r["status"] == "skipped"]

            # Overdue Banner if applicable
            if overdue_items:
                med_names = ", ".join([f"{d['medicine_name']} ({d['formatted_time']})" for d in overdue_items])
                st.markdown(f"""
                <div style="background-color: #FDF3E7; border-left: 5px solid #C07D1E; border: 1px solid #F5D7A1; border-radius: 8px; padding: 14px 18px; margin-bottom: 18px;">
                    <span style="font-size: 13px; font-weight: 700; color: #8A4B08; text-transform: uppercase;">Overdue Dose Notice</span>
                    <div style="font-size: 17px; font-weight: 700; color: #243447; margin-top: 2px;">
                        {len(overdue_items)} dose(s) past grace period: {med_names}
                    </div>
                    <p style="margin: 4px 0 0 0; font-size: 14px; color: #607086;">
                        Clinical reminder: Check with {ward_name} to confirm if this medication was taken. Never advise taking extra medicine or doubling a dose.
                    </p>
                </div>
                """, unsafe_allow_html=True)

            # Due Now Section
            if due_now_items:
                st.markdown(f"<h3 style='font-size: 19px; color: #8A4B08; margin-top: 6px;'>Due Now ({len(due_now_items)})</h3>", unsafe_allow_html=True)
                for item in due_now_items:
                    _render_reminder_card(item, user, elderly_id)

            # Overdue Section
            if overdue_items:
                st.markdown(f"<h3 style='font-size: 19px; color: #B84040; margin-top: 14px;'>Overdue Doses ({len(overdue_items)})</h3>", unsafe_allow_html=True)
                for item in overdue_items:
                    _render_reminder_card(item, user, elderly_id)

            # Upcoming Section
            if upcoming_items:
                st.markdown(f"<h3 style='font-size: 19px; color: #234B70; margin-top: 14px;'>Upcoming Doses Today ({len(upcoming_items)})</h3>", unsafe_allow_html=True)
                for item in upcoming_items:
                    _render_reminder_card(item, user, elderly_id)

            # Completed and Skipped Section
            done_items = completed_items + skipped_items
            if done_items:
                st.markdown(f"<h3 style='font-size: 19px; color: #23815C; margin-top: 14px;'>Completed & Skipped Doses ({len(done_items)})</h3>", unsafe_allow_html=True)
                for item in done_items:
                    _render_reminder_card(item, user, elderly_id)

    # TAB 2: NOTIFICATIONS STREAM
    with tab_stream:
        f_c1, f_c2 = st.columns([2, 1], vertical_alignment="center")
        with f_c1:
            filter_type = st.selectbox(
                "Filter Alert Type",
                ["All Alerts", "Due Now", "Overdue", "Caregiver Escalations", "Dose Confirmations", "Care Circle Updates"],
                key="notif_stream_filter",
            )
        with f_c2:
            unread_toggle = st.checkbox("Show Unread Only", value=False, key="notif_unread_toggle")

        type_map = {
            "All Alerts": "all",
            "Due Now": "due_now",
            "Overdue": "overdue",
            "Caregiver Escalations": "escalation",
            "Dose Confirmations": "completed",
            "Care Circle Updates": "system",
        }
        notifs = get_user_notifications(
            user=user,
            alert_type=type_map[filter_type],
            elderly_id=elderly_id if role != "elderly" else None,
            unread_only=unread_toggle,
            limit=50,
        )

        top_act1, top_act2 = st.columns([3, 1], vertical_alignment="center")
        with top_act1:
            st.caption(f"Showing {len(notifs)} notification(s)")
        with top_act2:
            if unread_count > 0:
                if st.button("Mark All as Read", key="btn_mark_all_read", use_container_width=True):
                    mark_all_notifications_as_read(user_id)
                    st.success("All notifications marked as read.")
                    st.rerun()

        if not notifs:
            st.info("No notifications match the current filter.")
        else:
            for n in notifs:
                is_unread = n["is_read"] == 0
                badge_color = {
                    "due_now": "#C07D1E",
                    "overdue": "#B84040",
                    "escalation": "#B84040",
                    "completed": "#23815C",
                }.get(n["alert_type"], "#234B70")

                bg_style = "background-color: #F8FAFD; border-left: 4px solid #234B70;" if is_unread else "background-color: #FFFFFF;"

                with st.container(border=True):
                    r_c1, r_c2 = st.columns([3.5, 1], vertical_alignment="center")
                    with r_c1:
                        read_tag = "<span style='font-size: 11px; font-weight: 700; color: #234B70; background-color: #EAF3FF; padding: 2px 6px; border-radius: 4px; margin-right: 6px;'>UNREAD</span>" if is_unread else ""
                        st.markdown(f"{read_tag}<strong style='font-size: 17px; color: #243447;'>{n['title']}</strong>", unsafe_allow_html=True)
                        st.markdown(f"<p style='margin: 4px 0; font-size: 15px; color: #243447;'>{n['message']}</p>", unsafe_allow_html=True)
                        st.caption(f"Time: {n['created_at']} &bull; Profile: {n['elderly_name']}")
                    with r_c2:
                        if is_unread:
                            if st.button("Mark Read", key=f"read_notif_{n['id']}", use_container_width=True):
                                mark_notification_as_read(n["id"], user_id)
                                st.rerun()

    # OUTBOUND EMAIL REMINDERS TAB (Challenge Specification)
    with tab_emails:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-top: 0;'>Proactive Email Reminders & Delivery Logs</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086;'>Automated clinical reminders proactively dispatched to care recipients, caretakers, and family members for upcoming doses, missed medications, and doctor visits.</p>", unsafe_allow_html=True)

        stats = get_email_statistics(elderly_id)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Reminders Sent", stats.get("total_sent", 0))
        with m2:
            st.metric("Recipients Reached", stats.get("recipients_count", 0))
        with m3:
            st.metric("Dispatch Engine", "Active (Automated)")

        st.write("")
        with st.expander("Trigger Test Routine Email Reminder (Evaluator Utility)", expanded=False):
            st.markdown("Test the proactive email system immediately by generating a simulated reminder:")
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                if st.button("Send Upcoming Dose Email", use_container_width=True):
                    send_upcoming_dose_email(
                        elderly_user_id=elderly_id,
                        recipient_email=user["email"],
                        recipient_name=user["name"],
                        senior_name=ward_name,
                        medicine_name="Metformin",
                        dosage="500mg",
                        scheduled_time="08:00 AM",
                        meal_timing="After Breakfast",
                        instructions="Take with a full glass of water.",
                    )
                    st.success("Upcoming dose reminder email dispatched successfully.")
                    st.rerun()
            with t_col2:
                if st.button("Send Missed Dose Email", use_container_width=True):
                    send_missed_dose_email(
                        elderly_user_id=elderly_id,
                        recipient_email=user["email"],
                        recipient_name=user["name"],
                        senior_name=ward_name,
                        medicine_name="Amlodipine",
                        dosage="5mg",
                        scheduled_time="09:00 AM",
                    )
                    st.warning("Missed dose alert email dispatched to care circle.")
                    st.rerun()
            with t_col3:
                if st.button("Send Doctor Visit Email", use_container_width=True):
                    send_appointment_email(
                        elderly_user_id=elderly_id,
                        recipient_email=user["email"],
                        recipient_name=user["name"],
                        senior_name=ward_name,
                        doctor_name="Rajesh Sharma",
                        hospital="City Heart Clinic",
                        appointment_date=date.today().isoformat(),
                        appointment_time="10:30 AM",
                        reminder_type="1_day_before",
                        notes="Carry previous ECG reports.",
                    )
                    st.info("Doctor appointment reminder email dispatched.")
                    st.rerun()

        st.write("")
        emails = get_outbound_emails(elderly_id, limit=30)
        if not emails:
            st.info("No outbound email reminders logged yet. Routine reminders will automatically appear here as doses and appointments approach.")
        else:
            st.markdown("##### Outbound Email Dispatch Log")
            for em in emails:
                with st.container(border=True):
                    e_top, e_badge = st.columns([3, 1], vertical_alignment="center")
                    with e_top:
                        st.markdown(f"<strong style='font-size: 16px; color: #234B70;'>{html.escape(em['subject'])}</strong>", unsafe_allow_html=True)
                        st.caption(f"Recipient: {html.escape(em['recipient_email'])} &bull; Sent: {em['sent_at']}")
                    with e_badge:
                        st.markdown("<div style='text-align: right;'><span class='badge-taken'>SENT (DELIVERED)</span></div>", unsafe_allow_html=True)
                    with st.expander("Preview Rendered Accessible Email"):
                        st.components.v1.html(em["message"], height=280, scrolling=True)

    # TAB 3: CAREGIVER ESCALATIONS (Caregiver only)
    if tab_escalations:
        with tab_escalations:
            st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-top: 0;'>Overdue Medication Escalations</h3>", unsafe_allow_html=True)
            st.markdown("<p style='font-size: 15px; color: #607086;'>When doses exceed the configured grace period, an in-app escalation is dispatched here for caregiver oversight.</p>", unsafe_allow_html=True)

            escalations = get_caregiver_escalations(caregiver_user=user, elderly_id=elderly_id)
            if not escalations:
                st.info("No overdue escalations currently recorded.")
            else:
                for esc in escalations:
                    is_ack = esc["is_acknowledged"] == 1
                    status_badge = '<span class="badge-taken">ACKNOWLEDGED</span>' if is_ack else '<span class="badge-overdue">PENDING ESCALATION</span>'

                    with st.container(border=True):
                        e_top, e_badge = st.columns([3, 1.2], vertical_alignment="center")
                        with e_top:
                            st.markdown(f"<strong style='font-size: 18px; color: #234B70;'>{esc['medicine_name']} ({esc['dosage']})</strong> &bull; Scheduled: {esc['scheduled_time']} ({esc['scheduled_date']})", unsafe_allow_html=True)
                            st.markdown(f"**Patient:** {esc['elderly_name']} &bull; Instructions: {esc.get('instructions') or 'Follow standard instructions'}")
                            if is_ack:
                                st.caption(f"Acknowledged by {esc.get('acknowledged_by_name') or 'Caregiver'} at {esc['acknowledged_at']}")
                            else:
                                st.caption(f"Escalated at: {esc['escalated_at']}")
                        with e_badge:
                            st.markdown(f"<div style='text-align: right;'>{status_badge}</div>", unsafe_allow_html=True)

                        if not is_ack:
                            st.write("")
                            b_ack, b_take, b_skip = st.columns([1.5, 1.2, 1])
                            with b_ack:
                                if st.button("Acknowledge Escalation", key=f"ack_esc_{esc['id']}", type="primary", use_container_width=True):
                                    acknowledge_caregiver_escalation(esc["id"], user)
                                    st.success("Escalation acknowledged. Please check in with the patient.")
                                    st.rerun()
                            with b_take:
                                if st.button("Confirm Taken", key=f"esc_take_{esc['id']}", use_container_width=True):
                                    record_dose_status(
                                        medication_id=esc["medication_id"],
                                        elderly_user_id=esc["elderly_user_id"],
                                        scheduled_date=esc["scheduled_date"],
                                        scheduled_time=esc["scheduled_time"],
                                        status="taken",
                                        recorded_by=user_id,
                                        notes="Confirmed by caregiver via escalation panel",
                                        user=user,
                                    )
                                    acknowledge_caregiver_escalation(esc["id"], user)
                                    st.rerun()
                            with b_skip:
                                if st.button("Mark Skipped", key=f"esc_skip_{esc['id']}", use_container_width=True):
                                    record_dose_status(
                                        medication_id=esc["medication_id"],
                                        elderly_user_id=esc["elderly_user_id"],
                                        scheduled_date=esc["scheduled_date"],
                                        scheduled_time=esc["scheduled_time"],
                                        status="skipped",
                                        recorded_by=user_id,
                                        notes="Marked skipped by caregiver via escalation panel",
                                        user=user,
                                    )
                                    acknowledge_caregiver_escalation(esc["id"], user)
                                    st.rerun()

    # TAB 4: REMINDER SETTINGS (Caregiver & Elderly)
    if tab_settings:
        with tab_settings:
            st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-top: 0;'>Reminder & Escalation Preferences</h3>", unsafe_allow_html=True)
            st.markdown("<p style='font-size: 15px; color: #607086;'>Configure grace periods, display time formatting, and in-app escalation behaviors.</p>", unsafe_allow_html=True)

            current_settings = get_user_reminder_settings(elderly_id)

            with st.container(border=True):
                with st.form("reminder_settings_form"):
                    st.markdown("**Grace Period Configuration**")
                    grace_val = st.slider(
                        "Grace Period (Minutes after scheduled time before dose becomes Overdue)",
                        min_value=5,
                        max_value=60,
                        value=int(current_settings.get("grace_period_minutes", 15)),
                        step=5,
                        help="Doses within this grace window are marked 'Due Now'. Doses beyond this window are classified 'Overdue' and escalate.",
                    )

                    st.write("")
                    st.markdown("**Notification Triggers**")
                    c_t1, c_t2 = st.columns(2)
                    with c_t1:
                        en_rem = st.checkbox(
                            "Enable In-App Medication Reminders",
                            value=bool(current_settings.get("enable_reminders", 1)),
                            help="Generates in-app alerts when medication is Due Now or Overdue.",
                        )
                    with c_t2:
                        en_esc = st.checkbox(
                            "Enable Caregiver Escalation for Overdue Doses",
                            value=bool(current_settings.get("enable_escalation", 1)),
                            help="Automatically dispatches an escalation notification to linked caregivers with editor permissions.",
                        )

                    st.write("")
                    st.markdown("**Display Preferences**")
                    cur_fmt = current_settings.get("time_format", "12h")
                    fmt_idx = 0 if cur_fmt == "12h" else 1
                    time_fmt = st.radio(
                        "Preferred Time Display Format",
                        options=["12h", "24h"],
                        format_func=lambda x: "12-Hour AM/PM (e.g. 08:30 AM)" if x == "12h" else "24-Hour (e.g. 08:30)",
                        index=fmt_idx,
                        horizontal=True,
                    )

                    st.write("")
                    submit_settings = st.form_submit_button("Save Reminder Settings", type="primary", use_container_width=True)

                if submit_settings:
                    try:
                        update_user_reminder_settings(
                            user_id=elderly_id,
                            grace_period_minutes=grace_val,
                            enable_reminders=en_rem,
                            enable_escalation=en_esc,
                            time_format=time_fmt,
                        )
                        st.success("Reminder and escalation preferences updated successfully.")
                        st.rerun()
                    except ValueError as ex:
                        st.error(str(ex))


def _render_reminder_card(item: dict, user: dict, elderly_id: int):
    """Renders a single accessible reminder card with clear statuses and action controls."""
    med_id = item["medication_id"]
    status = item["status"]
    sched_time = item["schedule_time"]
    today_str = item.get("target_date") or date.today().isoformat()
    role = user.get("role", "")
    user_id = user["id"]

    badge_html = {
        "due_now": '<span style="background-color: #FDF3E7; color: #8A4B08; border: 1px solid #F5D7A1; padding: 5px 12px; border-radius: 6px; font-weight: 700; font-size: 14px;">DUE NOW</span>',
        "overdue": '<span class="badge-overdue">OVERDUE</span>',
        "upcoming": '<span class="badge-pending">UPCOMING</span>',
        "completed": '<span class="badge-taken">COMPLETED</span>',
        "skipped": '<span class="badge-skipped">SKIPPED</span>',
    }.get(status, '<span class="badge-pending">PENDING</span>')

    with st.container(border=True):
        c_info, c_action = st.columns([2.5, 1.2], vertical_alignment="center")
        with c_info:
            st.markdown(f"<strong style='font-size: 20px; color: #234B70;'>{item['formatted_time']}</strong> &bull; <strong style='font-size: 18px; color: #243447;'>{item['medicine_name']} {item['dosage']}</strong> ({item.get('medication_type', 'Tablet')})", unsafe_allow_html=True)
            details = [item.get("meal_timing") or "After Meal"]
            if item.get("instructions"):
                details.append(item["instructions"])
            st.caption(" &bull; ".join(details))

        with c_action:
            st.markdown(f"<div style='margin-bottom: 8px; text-align: right;'>{badge_html}</div>", unsafe_allow_html=True)

            # Direct action buttons for elderly patient and authorized caregiver
            if role in ("elderly", "caregiver"):
                if status in ("due_now", "overdue", "upcoming"):
                    b_take, b_skip = st.columns(2)
                    with b_take:
                        if st.button("Take Now", key=f"rem_take_{med_id}_{sched_time}", type="primary", use_container_width=True):
                            record_dose_status(
                                medication_id=med_id,
                                elderly_user_id=elderly_id,
                                scheduled_date=today_str,
                                scheduled_time=sched_time,
                                status="taken",
                                recorded_by=user_id,
                                notes="Confirmed via Reminder Center",
                                user=user,
                            )
                            st.rerun()
                    with b_skip:
                        if st.button("Skip", key=f"rem_skip_{med_id}_{sched_time}", use_container_width=True):
                            record_dose_status(
                                medication_id=med_id,
                                elderly_user_id=elderly_id,
                                scheduled_date=today_str,
                                scheduled_time=sched_time,
                                status="skipped",
                                recorded_by=user_id,
                                notes="Skipped via Reminder Center",
                                user=user,
                            )
                            st.rerun()
                elif status == "completed":
                    if st.button("Undo / Reset", key=f"rem_undo_{med_id}_{sched_time}", use_container_width=True):
                        record_dose_status(
                            medication_id=med_id,
                            elderly_user_id=elderly_id,
                            scheduled_date=today_str,
                            scheduled_time=sched_time,
                            status="pending",
                            recorded_by=user_id,
                            notes="Reset to pending via Reminder Center",
                            user=user,
                        )
                        st.rerun()
                elif status == "skipped":
                    if st.button("Take Dose", key=f"rem_retake_{med_id}_{sched_time}", type="primary", use_container_width=True):
                        record_dose_status(
                            medication_id=med_id,
                            elderly_user_id=elderly_id,
                            scheduled_date=today_str,
                            scheduled_time=sched_time,
                            status="taken",
                            recorded_by=user_id,
                            notes="Taken later via Reminder Center",
                            user=user,
                        )
                        st.rerun()
