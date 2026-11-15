from datetime import date, datetime
import streamlit as st
from services.auth_service import get_accessible_elderly_wards
from services.emergency_service import (
    EMERGENCY_SAFETY_NOTICE,
    VALID_STATUSES,
    acknowledge_emergency,
    activate_emergency_sos,
    add_emergency_contact,
    cancel_emergency,
    delete_emergency_contact,
    get_active_emergency,
    get_emergency_contacts,
    get_emergency_requests,
    get_emergency_status_history,
    resolve_emergency,
    set_primary_emergency_contact,
    update_assistance_status,
    update_emergency_contact,
)
from services.permissions import can_manage_emergency, can_view_emergency


def render_emergency_view(user: dict):
    """
    Renders the dedicated, accessible Emergency SOS Dashboard.
    Strictly follows DESIGN.md with high-contrast buttons, zero emojis, and explicit safety disclaimers.
    """
    role = user.get("role", "")
    accessible_wards = get_accessible_elderly_wards(user)

    if not accessible_wards:
        st.warning("No elderly care profiles are currently linked to your account.")
        return

    # Determine elderly ward context
    if role == "elderly":
        selected_ward = accessible_wards[0]
        elderly_id = selected_ward["id"]
        ward_name = selected_ward["name"]
    else:
        ward_options = {w["id"]: f"{w['name']} (Age {w.get('age', 'N/A')})" for w in accessible_wards}
        default_idx = 0
        if "selected_ward_id" in st.session_state and st.session_state.selected_ward_id in ward_options:
            default_idx = list(ward_options.keys()).index(st.session_state.selected_ward_id)

        col_w1, col_w2 = st.columns([2, 1], vertical_alignment="bottom")
        with col_w1:
            elderly_id = st.selectbox(
                "Select Elderly Individual",
                options=list(ward_options.keys()),
                format_func=lambda x: ward_options[x],
                index=default_idx,
                key="emergency_ward_selector",
            )
        st.session_state.selected_ward_id = elderly_id
        selected_ward = next(w for w in accessible_wards if w["id"] == elderly_id)
        ward_name = selected_ward["name"]

    can_write = can_manage_emergency(user, elderly_id)

    # Header
    st.markdown(
        f"""
        <div style="margin-bottom: 12px;">
            <h1 style="font-size: 26px; color: #234B70; margin: 0 0 4px 0; font-weight: 700;">
                Emergency SOS & Care Circle Assistance
            </h1>
            <p style="font-size: 17px; color: #607086; margin: 0;">
                Rapid assistance dispatch, emergency contacts, and response tracking for <strong>{ward_name}</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mandatory Safety Notice
    st.markdown(
        f"""
        <div style="background-color: #FEF2F2; border-left: 4px solid #B84040; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 15px; color: #991B1B; line-height: 1.5; font-weight: 500;">
                <strong>Emergency Notice:</strong> {EMERGENCY_SAFETY_NOTICE}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Check for active emergency
    active_req = get_active_emergency(elderly_id, user=user)

    if active_req:
        st_color = {
            "pending": "#B84040",
            "acknowledged": "#C07D1E",
            "assistance_in_progress": "#234B70",
        }.get(active_req["status"], "#B84040")

        status_text = active_req["status"].replace("_", " ").upper()

        st.markdown(
            f"""
            <div style="background-color: #FFF5F5; border: 2px solid {st_color}; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-size: 20px; font-weight: 800; color: {st_color};">
                        ACTIVE EMERGENCY ASSISTANCE REQUEST (#{active_req['id']})
                    </span>
                    <span style="background-color: {st_color}; color: #FFFFFF; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 4px;">
                        STATUS: {status_text}
                    </span>
                </div>
                <p style="font-size: 16px; color: #1E293B; margin: 4px 0;">
                    <strong>Patient:</strong> {ward_name} &bull; <strong>Triggered:</strong> {active_req['created_at']}
                </p>
                <p style="font-size: 15px; color: #475569; margin: 4px 0;">
                    <strong>Location / Situation:</strong> {active_req.get('location_notes') or 'Not specified (Home)'}
                </p>
                {f"<p style='font-size: 15px; color: #234B70; margin: 4px 0;'><strong>Acknowledged by:</strong> {active_req['acknowledged_by_name']} ({active_req.get('acknowledged_at', '')})</p>" if active_req.get('acknowledged_by') else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Active Emergency Action Controls
        with st.container(border=True):
            st.markdown("##### Emergency Response Controls")
            c_act1, c_act2, c_act3, c_act4 = st.columns(4)

            # 1. Acknowledge (Caregiver)
            with c_act1:
                if active_req["status"] == "pending" and role == "caregiver":
                    with st.expander("Acknowledge Alert"):
                        ack_note = st.text_input("Response Note", placeholder="e.g. Saw alert, calling now", key="ack_note_in")
                        if st.button("Confirm Acknowledge", key="btn_ack_confirm", type="primary", use_container_width=True):
                            acknowledge_emergency(active_req["id"], elderly_id, user["id"], response_note=ack_note, user=user)
                            st.success("Emergency acknowledged.")
                            st.rerun()
                else:
                    st.caption("Alert Acknowledged" if active_req.get("acknowledged_by") else "Awaiting caregiver response")

            # 2. Assistance In Progress (Caregiver)
            with c_act2:
                if active_req["status"] in ("pending", "acknowledged") and role == "caregiver":
                    with st.expander("Mark In Progress"):
                        prog_note = st.text_input("Progress Note", placeholder="e.g. En route to Asha's home", key="prog_note_in")
                        if st.button("Update to In Progress", key="btn_prog_confirm", use_container_width=True):
                            update_assistance_status(active_req["id"], elderly_id, user["id"], "assistance_in_progress", response_note=prog_note, user=user)
                            st.success("Assistance marked in progress.")
                            st.rerun()
                elif active_req["status"] == "assistance_in_progress":
                    st.caption("Caregiver assistance currently in progress")

            # 3. Resolve (Caregiver or Senior)
            with c_act3:
                if can_write:
                    with st.expander("Resolve Emergency"):
                        res_note = st.text_area("Resolution Summary (Required)", placeholder="e.g. Visited Asha, helped up, checked vitals (all normal). Safe at home.", key="res_note_in")
                        if st.button("Mark as Resolved", key="btn_res_confirm", type="primary", use_container_width=True):
                            if res_note.strip():
                                resolve_emergency(active_req["id"], elderly_id, user["id"], resolution_notes=res_note, user=user)
                                st.success("Emergency marked as resolved.")
                                st.rerun()
                            else:
                                st.error("Please enter a resolution summary.")

            # 4. Cancel (False alarm)
            with c_act4:
                if can_write:
                    with st.expander("Cancel Request"):
                        canc_reason = st.text_input("Cancellation Reason", placeholder="e.g. Pressed accidentally; all safe", key="canc_note_in")
                        if st.button("Confirm Cancel", key="btn_canc_confirm", use_container_width=True):
                            cancel_emergency(active_req["id"], elderly_id, user["id"], cancel_reason=canc_reason, user=user)
                            st.warning("Emergency request cancelled.")
                            st.rerun()

    # Three Main Tabs
    tab_sos, tab_contacts, tab_history = st.tabs([
        "Activate Emergency SOS",
        "Emergency Contacts Directory",
        "Emergency Assistance History",
    ])

    # =========================================================================
    # TAB 1: ACTIVATE EMERGENCY SOS
    # =========================================================================
    with tab_sos:
        st.write("")
        sos_box_col1, sos_box_col2 = st.columns([1.8, 1.2], gap="large")

        with sos_box_col1:
            st.markdown(
                """
                <div style="background-color: #FFFFFF; border: 2px solid #E2E8F0; border-radius: 8px; padding: 24px;">
                    <h3 style="font-size: 20px; color: #234B70; margin-top: 0; font-weight: 700;">
                        Need Immediate Assistance?
                    </h3>
                    <p style="font-size: 17px; color: #334155; line-height: 1.6;">
                        Pressing the button below dispatches a high-priority in-app alert to all active members of your Care Circle.
                        You will be asked to confirm before the alert is sent.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write("")

            # Activation / Confirmation flow
            if "sos_confirm_step" not in st.session_state:
                st.session_state.sos_confirm_step = False

            if not st.session_state.sos_confirm_step:
                # Big accessible trigger button
                if st.button(
                    "ACTIVATE EMERGENCY SOS",
                    key="initial_sos_trigger_btn",
                    type="primary",
                    use_container_width=True,
                    disabled=bool(active_req),
                ):
                    if active_req:
                        st.warning("An emergency request is already active.")
                    else:
                        st.session_state.sos_confirm_step = True
                        st.rerun()

                if active_req:
                    st.caption("SOS button disabled while an active emergency is open. Use the controls above to update or resolve it.")
            else:
                # Two-step confirmation screen
                with st.container(border=True):
                    st.markdown(
                        """
                        <div style="background-color: #FEF2F2; border-left: 4px solid #B84040; padding: 12px 16px; border-radius: 4px; margin-bottom: 16px;">
                            <h4 style="margin: 0 0 6px 0; color: #991B1B; font-size: 18px;">
                                Confirm Emergency Alert Dispatch
                            </h4>
                            <p style="margin: 0; font-size: 16px; color: #7F1D1D;">
                                Are you sure you want to dispatch an emergency alert to your Care Circle now?
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    user_loc = st.text_input(
                        "Your Current Location or Room (Optional)",
                        placeholder="e.g. Living room couch, bedroom, garden",
                        key="sos_loc_input",
                    )
                    user_urgency = st.text_input(
                        "Brief Situation Note (Optional)",
                        placeholder="e.g. Feeling dizzy, need help standing up",
                        key="sos_urgency_input",
                    )

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button(
                            "YES, SEND EMERGENCY ALERT NOW",
                            key="sos_final_confirm_btn",
                            type="primary",
                            use_container_width=True,
                        ):
                            try:
                                req_id = activate_emergency_sos(
                                    elderly_user_id=elderly_id,
                                    triggered_by_user_id=user["id"],
                                    location_notes=user_loc,
                                    urgency_reason=user_urgency,
                                    user=user,
                                )
                                st.session_state.sos_confirm_step = False
                                st.success(f"Emergency alert dispatched to your Care Circle (Request #{req_id}).")
                                st.rerun()
                            except ValueError as ve:
                                st.warning(str(ve))
                                st.session_state.sos_confirm_step = False

                    with btn_c2:
                        if st.button(
                            "Cancel / Return Safe",
                            key="sos_cancel_confirm_btn",
                            use_container_width=True,
                        ):
                            st.session_state.sos_confirm_step = False
                            st.info("Emergency alert cancelled. No notifications were sent.")
                            st.rerun()

        with sos_box_col2:
            st.markdown(
                """
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px;">
                    <h4 style="color: #234B70; margin-top: 0; font-size: 18px;">National Emergency Helplines (India)</h4>
                    <p style="font-size: 15px; color: #334155; margin-bottom: 8px;">
                        For life-threatening emergencies, call official services directly:
                    </p>
                    <ul style="font-size: 15px; color: #1E293B; padding-left: 20px; line-height: 1.8;">
                        <li><strong>National Emergency Number:</strong> 112</li>
                        <li><strong>Medical Ambulance:</strong> 108 / 102</li>
                        <li><strong>Police Assistance:</strong> 100</li>
                        <li><strong>Senior Citizen Helpline:</strong> 14567</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # =========================================================================
    # TAB 2: EMERGENCY CONTACTS DIRECTORY
    # =========================================================================
    with tab_contacts:
        st.markdown("### Emergency Contacts Directory")
        st.markdown("<p style='font-size: 16px; color: #607086;'>Authorized contacts who will be notified during an urgent health event.</p>", unsafe_allow_html=True)

        contacts = get_emergency_contacts(elderly_id, active_only=True, user=user)

        if not contacts:
            st.info("No emergency contacts registered yet.")
        else:
            for c in contacts:
                with st.container(border=True):
                    c_col1, c_col2 = st.columns([3, 1], vertical_alignment="top")
                    with c_col1:
                        primary_badge = "<span style='background-color: #ECFDF5; color: #065F46; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 700;'>PRIMARY CONTACT</span>" if c.get("is_primary") else f"<span style='background-color: #EDF2F7; color: #234B70; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;'>Priority {c.get('priority', 1)}</span>"
                        st.markdown(
                            f"<div style='font-size: 19px; font-weight: 700; color: #234B70;'>{c['contact_name']} &bull; {primary_badge}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Relationship:** {c['relationship']} &bull; **Phone:** <span style='font-size: 17px; font-weight: 600;'>{c['phone']}</span>", unsafe_allow_html=True)
                        if c.get("email"):
                            st.caption(f"Email: {c['email']}")
                        if c.get("notes"):
                            st.caption(f"Notes: {c['notes']}")

                    with c_col2:
                        if can_write and not c.get("is_primary"):
                            if st.button("Set as Primary", key=f"set_prim_{c['id']}", use_container_width=True):
                                set_primary_emergency_contact(c["id"], elderly_id, user=user)
                                st.success(f"{c['contact_name']} set as primary.")
                                st.rerun()

                    # Edit & Remove Expander (for authorized users)
                    if can_write:
                        with st.expander(f"Edit or Remove {c['contact_name']}"):
                            with st.form(f"edit_contact_form_{c['id']}"):
                                e_name = st.text_input("Full Name", value=c["contact_name"])
                                e_rel = st.text_input("Relationship", value=c["relationship"])
                                e_phone = st.text_input("Phone Number", value=c["phone"])
                                e_email = st.text_input("Email Address", value=c.get("email") or "")
                                e_prio = st.number_input("Priority Order", min_value=1, max_value=10, value=int(c.get("priority", 1)))
                                e_prim = st.checkbox("Designate as Primary Emergency Contact", value=bool(c.get("is_primary")))
                                e_notes = st.text_input("Contact Notes", value=c.get("notes") or "")

                                f_sub, f_del = st.columns([1, 1])
                                with f_sub:
                                    submit_edit = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
                                with f_del:
                                    remove_btn = st.form_submit_button("Remove Contact", use_container_width=True)

                                if submit_edit:
                                    try:
                                        update_emergency_contact(
                                            contact_id=c["id"],
                                            elderly_user_id=elderly_id,
                                            contact_name=e_name,
                                            relationship=e_rel,
                                            phone=e_phone,
                                            email=e_email,
                                            priority=e_prio,
                                            is_primary=e_prim,
                                            notes=e_notes,
                                            user=user,
                                        )
                                        st.success("Contact updated successfully.")
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(str(ex))

                                if remove_btn:
                                    delete_emergency_contact(c["id"], elderly_id, user=user)
                                    st.warning(f"Contact {c['contact_name']} removed.")
                                    st.rerun()

        # Add New Contact Form (if authorized)
        if can_write:
            st.divider()
            with st.expander("Register New Emergency Contact"):
                with st.form("add_contact_form"):
                    n_name = st.text_input("Contact Person's Name *", placeholder="e.g. Dr. Ramesh Gupta")
                    n_rel = st.text_input("Relationship *", placeholder="e.g. Neighbor, Family Physician")
                    n_phone = st.text_input("Phone Number *", placeholder="e.g. +91 98200 99887")
                    n_email = st.text_input("Email (Optional)", placeholder="e.g. neighbor@email.com")
                    n_prio = st.number_input("Contact Priority (1 = Highest)", min_value=1, max_value=10, value=len(contacts) + 1)
                    n_prim = st.checkbox("Make Primary Emergency Contact")
                    n_notes = st.text_input("Notes (Optional)", placeholder="e.g. Has spare house key")

                    submit_add = st.form_submit_button("Add Emergency Contact", type="primary")

                    if submit_add:
                        try:
                            cid = add_emergency_contact(
                                elderly_user_id=elderly_id,
                                contact_name=n_name,
                                relationship=n_rel,
                                phone=n_phone,
                                email=n_email,
                                priority=n_prio,
                                is_primary=n_prim,
                                notes=n_notes,
                                user=user,
                            )
                            st.success(f"Contact added successfully (Contact #{cid}).")
                            st.rerun()
                        except Exception as ex:
                            st.error(str(ex))

    # =========================================================================
    # TAB 3: EMERGENCY ASSISTANCE HISTORY
    # =========================================================================
    with tab_history:
        st.markdown("### Emergency Assistance History")
        st.markdown("<p style='font-size: 16px; color: #607086;'>Chronological audit of emergency alerts, status transitions, and resolution summaries.</p>", unsafe_allow_html=True)

        h_col1, h_col2 = st.columns([1.5, 1])
        with h_col1:
            h_status = st.selectbox(
                "Filter by Request Status",
                ["All Requests", "Pending", "Acknowledged", "Assistance in Progress", "Resolved", "Cancelled"],
                key="em_hist_filter_status",
            )

        filter_status = None if h_status == "All Requests" else h_status.lower().replace(" ", "_")
        requests = get_emergency_requests(elderly_id, status=filter_status, limit=50, user=user)

        if not requests:
            st.info("No emergency requests match the selected filter.")
        else:
            for req in requests:
                with st.container(border=True):
                    st_badge_color = {
                        "pending": "#B84040",
                        "acknowledged": "#C07D1E",
                        "assistance_in_progress": "#234B70",
                        "resolved": "#23815C",
                        "cancelled": "#607086",
                    }.get(req["status"], "#234B70")

                    st_lbl = req["status"].replace("_", " ").upper()

                    rh_1, rh_2 = st.columns([3, 1], vertical_alignment="top")
                    with rh_1:
                        st.markdown(
                            f"<div style='font-size: 18px; font-weight: 700; color: #234B70;'>Emergency Request #{req['id']} &bull; <span style='background-color: {st_badge_color}; color: #FFFFFF; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 4px;'>{st_lbl}</span></div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Triggered:** {req['created_at']} by **{req.get('triggered_by_name') or 'Senior'}**")
                        if req.get("location_notes"):
                            st.caption(f"Location: {req['location_notes']}")
                        if req.get("urgency_reason"):
                            st.caption(f"Reason: {req['urgency_reason']}")

                        if req.get("acknowledged_by_name"):
                            st.markdown(f"**Acknowledged by:** {req['acknowledged_by_name']} at {req.get('acknowledged_at')}")

                        if req.get("resolved_by_name"):
                            st.markdown(f"**Resolved by:** {req['resolved_by_name']} at {req.get('resolved_at')}")
                        if req.get("resolution_notes"):
                            st.markdown(f"<div style='background-color: #F8FAFD; border-left: 3px solid #23815C; padding: 6px 12px; border-radius: 4px; font-size: 14px;'>Outcome: {req['resolution_notes']}</div>", unsafe_allow_html=True)

                    with rh_2:
                        st.markdown(f"<div style='text-align: right; color: #607086; font-size: 13px;'>Updated: {req['updated_at']}</div>", unsafe_allow_html=True)

                    # View Full Status History
                    with st.expander(f"View Status History for Request #{req['id']}"):
                        history_logs = get_emergency_status_history(req["id"], user=user)
                        if not history_logs:
                            st.caption("No transition records.")
                        else:
                            for h in history_logs:
                                f_lbl = h["from_status"].replace("_", " ").title()
                                t_lbl = h["to_status"].replace("_", " ").title()
                                st.markdown(
                                    f"- **{h['created_at']}**: Transitioned from `{f_lbl}` to `{t_lbl}` by **{h['actor_name']}**. Note: *{h['response_note'] or 'None'}*"
                                )
