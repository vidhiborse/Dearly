import streamlit as st
from datetime import date, datetime
from services.care_circle_service import (
    get_care_circle_dashboard,
    get_care_circle_members,
    get_elderly_profile,
    send_care_invitation,
    get_user_pending_invitations,
    get_elderly_pending_invitations,
    respond_to_invitation,
    revoke_invitation,
    remove_care_circle_member,
    set_primary_caregiver,
    add_care_note,
    get_care_notes,
    update_care_note,
    archive_care_note,
    delete_care_note,
)
from services.activity_service import get_care_activity_timeline
from services.auth_service import get_accessible_elderly_wards
from services.permissions import can_manage_care_circle, can_write_notes
from views.common import render_clinical_disclaimer


def render_care_circle_view(user: dict):
    role = user.get("role", "")
    user_id = user["id"]

    # Determine elderly ward context
    if role == "elderly":
        elderly_id = user_id
        ward_name = user["name"]
    else:
        wards = get_accessible_elderly_wards(user)
        if not wards:
            st.warning("No linked care recipients found in your care circle.")
            _render_my_invitations_only(user)
            render_clinical_disclaimer()
            return

        ward_options = {w["id"]: f"{w['name']} (ID: #{w['id']})" for w in wards}
        if "circle_selected_ward" not in st.session_state or st.session_state.circle_selected_ward not in ward_options:
            st.session_state.circle_selected_ward = wards[0]["id"]

        c_w1, c_w2 = st.columns([1.5, 2], vertical_alignment="center")
        with c_w1:
            selected_ward_id = st.selectbox(
                "Select Care Recipient",
                options=list(ward_options.keys()),
                format_func=lambda x: ward_options[x],
                index=list(ward_options.keys()).index(st.session_state.circle_selected_ward),
                key="circle_ward_selector",
            )
            st.session_state.circle_selected_ward = selected_ward_id
        elderly_id = st.session_state.circle_selected_ward
        cur_ward = next((w for w in wards if w["id"] == elderly_id), wards[0])
        ward_name = cur_ward["name"]

    # Fetch dashboard data
    try:
        dashboard = get_care_circle_dashboard(elderly_id, user=user)
    except PermissionError as pe:
        st.error(str(pe))
        render_clinical_disclaimer()
        return

    primary_cg = dashboard.get("primary_caregiver")
    caregivers = dashboard.get("caregivers", [])
    family_members = dashboard.get("family_members", [])
    pending_invites = dashboard.get("pending_invitations", [])
    counts = dashboard.get("counts", {})
    my_received_invites = get_user_pending_invitations(user)

    can_manage = can_manage_care_circle(user, elderly_id)
    can_note = can_write_notes(user, elderly_id)

    # Page Header
    st.markdown(f"<h1 style='font-size: 26px; color: #234B70; margin-bottom: 4px;'>Care Circle & Support Network &bull; {ward_name}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 16px;'>Coordinated care team connecting seniors, family members, and primary caregivers.</p>", unsafe_allow_html=True)

    # Summary KPI row
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total Connected", f"{counts.get('total_active', 0)} members")
    with k2:
        st.metric("Caregivers", f"{counts.get('caregivers_count', 0)}")
    with k3:
        st.metric("Family Members", f"{counts.get('family_count', 0)}")
    with k4:
        st.metric("Pending Invites", f"{counts.get('pending_count', 0)}")

    st.write("")

    # Global Notification of pending received invites
    if my_received_invites:
        st.markdown(f"""
        <div style="background-color: #EAF3FF; border: 1px solid #B8D5FA; border-left: 5px solid #234B70; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px;">
            <strong style="font-size: 16px; color: #234B70;">You have {len(my_received_invites)} pending care circle invitation(s)!</strong>
            <p style="margin: 4px 0 0 0; font-size: 14px; color: #243447;">Review your received invitations under the 'My Invitations' tab below to accept or decline access.</p>
        </div>
        """, unsafe_allow_html=True)

    # Tab Setup
    tab_network, tab_invite, tab_received, tab_notes, tab_timeline = st.tabs([
        f"Care Circle ({counts.get('total_active', 0)})",
        "Invite Member",
        f"My Invitations ({len(my_received_invites)})",
        "Shared Care Notes",
        "Care Activity Timeline",
    ])

    # ==========================================
    # TAB 1: CARE CIRCLE NETWORK
    # ==========================================
    with tab_network:
        # Primary Caregiver Highlight
        if primary_cg:
            st.markdown(f"""
            <div style="background-color: #EBF8F2; border: 1px solid #A8E5CB; border-radius: 8px; padding: 16px; margin-bottom: 18px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 12px; font-weight: 700; color: #23815C; text-transform: uppercase; letter-spacing: 0.5px;">Designated Primary Caregiver</span>
                        <div style="font-size: 20px; font-weight: 700; color: #243447; margin-top: 2px;">{primary_cg['name']}</div>
                        <div style="font-size: 15px; color: #23815C; font-weight: 600;">Relationship: {primary_cg['relationship']} &bull; Permission: {primary_cg['permission_level'].title()} Access</div>
                        <div style="font-size: 14px; color: #607086; margin-top: 4px;">Email: {primary_cg['email']} &bull; Phone: {primary_cg.get('phone') or 'Not recorded'}</div>
                    </div>
                    <div style="background-color: #23815C; color: #FFFFFF; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px;">
                        PRIMARY LEAD
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No primary caregiver currently designated. An authorized caregiver or senior can designate one below.")

        col_cg, col_fam = st.columns(2, gap="large")

        # Column 1: Caregivers
        with col_cg:
            st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 8px;'>Authorized Caregivers</h3>", unsafe_allow_html=True)
            if not caregivers:
                st.caption("No professional or family caregivers currently linked.")
            else:
                for cg in caregivers:
                    is_prim = cg.get("is_primary") == 1
                    with st.container(border=True):
                        top_l, top_r = st.columns([3, 1], vertical_alignment="center")
                        with top_l:
                            st.markdown(f"<strong style='font-size: 17px; color: #243447;'>{cg['name']}</strong>", unsafe_allow_html=True)
                            st.markdown(f"**Role:** {cg['relationship']} &bull; <span style='color: #234B70; font-weight: 600;'>{cg['permission_level'].title()} Access</span>", unsafe_allow_html=True)
                            st.caption(f"Email: {cg['email']} | Phone: {cg.get('phone') or 'N/A'}")
                            st.caption(f"Joined: {cg.get('created_at', 'Active')}")
                        with top_r:
                            if is_prim:
                                st.markdown("<span style='font-size: 11px; font-weight: 700; color: #23815C; background: #EBF8F2; padding: 3px 6px; border-radius: 4px;'>PRIMARY</span>", unsafe_allow_html=True)

                        # Management controls for authorized users
                        if can_manage:
                            st.write("")
                            b_c1, b_c2 = st.columns(2)
                            with b_c1:
                                if not is_prim:
                                    if st.button("Set as Primary", key=f"set_prim_{cg['user_id']}", use_container_width=True):
                                        ok, msg = set_primary_caregiver(elderly_id, cg["user_id"], user)
                                        if ok:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                            with b_c2:
                                with st.expander("Remove"):
                                    st.caption(f"Confirm removing {cg['name']}?")
                                    if st.button("Confirm Remove", key=f"del_cg_{cg['user_id']}", use_container_width=True):
                                        ok, msg = remove_care_circle_member(elderly_id, cg["user_id"], user)
                                        if ok:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)

        # Column 2: Family Members
        with col_fam:
            st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 8px;'>Family Members</h3>", unsafe_allow_html=True)
            if not family_members:
                st.caption("No family members currently linked.")
            else:
                for fm in family_members:
                    with st.container(border=True):
                        st.markdown(f"<strong style='font-size: 17px; color: #243447;'>{fm['name']}</strong>", unsafe_allow_html=True)
                        st.markdown(f"**Relationship:** {fm['relationship']} &bull; <span style='color: #607086;'>{fm['permission_level'].title()} Access</span>", unsafe_allow_html=True)
                        st.caption(f"Email: {fm['email']} | Phone: {fm.get('phone') or 'N/A'}")
                        st.caption(f"Joined: {fm.get('created_at', 'Active')}")

                        if can_manage:
                            with st.expander("Remove Connection"):
                                st.caption(f"Confirm removing {fm['name']} from the circle?")
                                if st.button("Confirm Remove", key=f"del_fm_{fm['user_id']}", use_container_width=True):
                                    ok, msg = remove_care_circle_member(elderly_id, fm["user_id"], user)
                                    if ok:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)

    # ==========================================
    # TAB 2: INVITE MEMBER
    # ==========================================
    with tab_invite:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Invite a Caregiver or Family Member</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Invite an existing registered user to access this elderly individual's care circle. An in-app invitation will be delivered to their dashboard for acceptance.</p>", unsafe_allow_html=True)

        if not can_manage:
            st.warning("Only the elderly individual and authorized editor caregivers can dispatch new care circle invitations.")
        else:
            with st.container(border=True):
                with st.form("invite_member_form"):
                    inv_email = st.text_input("User Email Address *", placeholder="e.g. nurse.smith@example.com")
                    
                    c_rel, c_role = st.columns(2)
                    with c_rel:
                        relationship_options = ["Son", "Daughter", "Spouse", "Relative", "Professional caregiver", "Other"]
                        inv_rel = st.selectbox("Relationship to Senior *", relationship_options)
                    with c_role:
                        inv_role = st.selectbox("Role Category *", ["caregiver", "family"], format_func=lambda x: "Caregiver (Active Care Management)" if x == "caregiver" else "Family Member (Observation & Updates)")

                    c_perm, c_space = st.columns([1, 1])
                    with c_perm:
                        perm_choices = ["viewer", "editor"]
                        inv_perm = st.selectbox("Permission Level *", perm_choices, format_func=lambda x: "Viewer (Read-only observation)" if x == "viewer" else "Editor (Can log doses, notes & manage routine)")

                    st.caption("Notice: For privacy and safety, invitations require explicit acceptance by the recipient before granting any profile access.")
                    submit_invite = st.form_submit_button("Send Care Circle Invitation", use_container_width=True, type="primary")

                if submit_invite:
                    try:
                        ok, msg, inv_id = send_care_invitation(
                            elderly_user_id=elderly_id,
                            inviter_user=user,
                            invitee_email=inv_email,
                            relationship=inv_rel,
                            connection_role=inv_role,
                            permission_level=inv_perm,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    except PermissionError as pe:
                        st.error(str(pe))

            # Outstanding invitations dispatched for this profile
            st.write("")
            st.markdown("<h4 style='font-size: 17px; color: #234B70;'>Dispatched Pending Invitations</h4>", unsafe_allow_html=True)
            if not pending_invites:
                st.caption("No pending invitations currently outstanding.")
            else:
                for inv in pending_invites:
                    with st.container(border=True):
                        pi_c1, pi_c2 = st.columns([3, 1], vertical_alignment="center")
                        with pi_c1:
                            st.markdown(f"**Invitee:** {inv['invitee_email']} &bull; Role: **{inv['connection_role'].title()}** ({inv['relationship']})")
                            st.caption(f"Permission: {inv['permission_level'].title()} | Sent: {inv['created_at']} by {inv['inviter_name']}")
                        with pi_c2:
                            if st.button("Revoke", key=f"revoke_inv_{inv['id']}", use_container_width=True):
                                ok, msg = revoke_invitation(inv["id"], user)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

    # ==========================================
    # TAB 3: MY RECEIVED INVITATIONS
    # ==========================================
    with tab_received:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Invitations Waiting for Your Approval</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Care circle invitations sent to your registered email address.</p>", unsafe_allow_html=True)

        if not my_received_invites:
            st.info("No pending invitations waiting for your approval. When a family member or caregiver invites you to a care circle, it will appear here.")
        else:
            for inv in my_received_invites:
                with st.container(border=True):
                    r_top1, r_top2 = st.columns([2.5, 1.5], vertical_alignment="center")
                    with r_top1:
                        st.markdown(f"<strong style='font-size: 18px; color: #234B70;'>Care Circle for {inv['elderly_name']}</strong>", unsafe_allow_html=True)
                        st.markdown(f"**Invited by:** {inv['inviter_name']} &bull; **Proposed Role:** {inv['relationship']} ({inv['connection_role'].title()})")
                        st.caption(f"Permission Granted: {inv['permission_level'].title()} Access &bull; Sent on: {inv['created_at']}")
                    with r_top2:
                        btn_acc, btn_rej = st.columns(2)
                        with btn_acc:
                            if st.button("Accept", key=f"acc_inv_{inv['id']}", type="primary", use_container_width=True):
                                ok, msg = respond_to_invitation(inv["id"], user, "accept")
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with btn_rej:
                            if st.button("Decline", key=f"rej_inv_{inv['id']}", use_container_width=True):
                                ok, msg = respond_to_invitation(inv["id"], user, "reject")
                                if ok:
                                    st.info(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

    # ==========================================
    # TAB 4: SHARED CARE NOTES
    # ==========================================
    with tab_notes:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Shared Everyday Care Notes</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Observations, routine updates, and diet reminders shared across the care circle.</p>", unsafe_allow_html=True)

        # Write care note form
        if can_note:
            with st.expander("Write a New Care Note"):
                with st.form("new_care_note_form"):
                    note_title = st.text_input("Note Title *", placeholder="e.g. Afternoon Routine & Hydration Check")
                    note_cat = st.selectbox("Category", ["routine", "observation", "general", "diet", "doctor_feedback"])
                    note_vis = st.selectbox(
                        "Visibility *",
                        ["circle", "caregivers_only"],
                        format_func=lambda x: "All Circle Members (Visible to Caregivers and Family)" if x == "circle" else "Caregivers Only (Private clinical note)",
                    )
                    note_body = st.text_area("Note Content *", placeholder="e.g. Senior took light walk in garden, drank 3 glasses of water. Appetite good at lunch.")
                    st.caption("Clinical safety: Care notes must record everyday observations. Never record medical diagnoses or prescription changes without physician sign-off.")
                    submit_note = st.form_submit_button("Save Care Note", use_container_width=True, type="primary")

                if submit_note:
                    try:
                        ok, msg, n_id = add_care_note(
                            elderly_user_id=elderly_id,
                            author_user=user,
                            title=note_title,
                            content=note_body,
                            category=note_cat,
                            visibility=note_vis,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    except PermissionError as pe:
                        st.error(str(pe))

        # Notes list
        all_notes = get_care_notes(elderly_id, user=user)
        if not all_notes:
            st.info("No care notes recorded yet.")
        else:
            for n in all_notes:
                is_priv = n["visibility"] == "caregivers_only"
                vis_badge = "<span style='font-size: 11px; font-weight: 700; color: #8A4B08; background: #FDF3E7; padding: 2px 6px; border-radius: 4px; margin-left: 6px;'>CAREGIVERS ONLY</span>" if is_priv else ""

                with st.container(border=True):
                    n_head1, n_head2 = st.columns([3, 1], vertical_alignment="center")
                    with n_head1:
                        st.markdown(f"<strong style='font-size: 18px; color: #234B70;'>{n['title']}</strong>{vis_badge}", unsafe_allow_html=True)
                        st.caption(f"Category: {n['category'].title()} &bull; Author: {n['author_name']} ({n['author_role'].title()}) &bull; Date: {n['created_at']}")
                    with n_head2:
                        if can_manage or n["author_id"] == user_id:
                            with st.expander("Manage"):
                                if st.button("Delete Note", key=f"del_note_{n['id']}", use_container_width=True):
                                    delete_care_note(n["id"], user)
                                    st.success("Note removed.")
                                    st.rerun()

                    st.markdown(f"<p style='font-size: 15px; color: #243447; margin-top: 6px;'>{n['content']}</p>", unsafe_allow_html=True)

    # ==========================================
    # TAB 5: CARE ACTIVITY TIMELINE
    # ==========================================
    with tab_timeline:
        st.markdown("<h3 style='font-size: 19px; color: #234B70; margin-bottom: 6px;'>Care Activity Timeline</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 16px;'>Immutable chronological audit log of all care events, medication confirmations, and relationship changes.</p>", unsafe_allow_html=True)

        tl_c1, tl_c2 = st.columns([2, 1], vertical_alignment="center")
        with tl_c1:
            action_choice = st.selectbox(
                "Filter Event Category",
                ["All Events", "Medication & Dose Confirmations", "Reminders & Alerts", "Care Circle Updates", "Care Notes"],
                key="timeline_category_filter",
            )
        with tl_c2:
            event_limit = st.selectbox("Display Limit", [20, 50, 100], index=1, key="timeline_limit_selector")

        filter_mapping = {
            "All Events": "all",
            "Medication & Dose Confirmations": "medication",
            "Reminders & Alerts": "reminder",
            "Care Circle Updates": "circle",
            "Care Notes": "notes",
        }

        try:
            timeline_events = get_care_activity_timeline(
                elderly_user_id=elderly_id,
                user=user,
                action_filter=filter_mapping[action_choice],
                limit=event_limit,
            )
        except PermissionError as pe:
            st.error(str(pe))
            timeline_events = []

        if not timeline_events:
            st.info("No activity events match the selected filter.")
        else:
            for ev in timeline_events:
                with st.container(border=True):
                    ev_c1, ev_c2 = st.columns([3, 1], vertical_alignment="center")
                    with ev_c1:
                        st.markdown(f"<strong style='font-size: 16px; color: #234B70;'>{ev['action']}</strong>", unsafe_allow_html=True)
                        st.markdown(f"<p style='margin: 4px 0; font-size: 15px; color: #243447;'>{ev['details']}</p>", unsafe_allow_html=True)
                        actor_desc = f"{ev['actor_name']} ({ev['actor_role'].title()})" if ev.get("actor_name") else "Automated System"
                        st.caption(f"Recorded by: {actor_desc}")
                    with ev_c2:
                        st.markdown(f"<div style='text-align: right; font-size: 13px; color: #607086;'>{ev['created_at']}</div>", unsafe_allow_html=True)

    render_clinical_disclaimer()


def _render_my_invitations_only(user: dict):
    """Fallback view when a user is not yet connected to any elderly ward."""
    st.markdown("<h2 style='font-size: 22px; color: #234B70;'>My Received Invitations</h2>", unsafe_allow_html=True)
    my_invites = get_user_pending_invitations(user)
    if not my_invites:
        st.info("You do not currently have any pending invitations to join a care circle. Ask a family member or senior to invite you using your registered email address.")
    else:
        for inv in my_invites:
            with st.container(border=True):
                st.markdown(f"**Invitation to Care Circle for {inv['elderly_name']}**")
                st.markdown(f"Invited by: **{inv['inviter_name']}** as **{inv['relationship']}** ({inv['connection_role'].title()} with {inv['permission_level'].title()} access)")
                st.caption(f"Sent: {inv['created_at']}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Accept Invitation", key=f"lone_acc_{inv['id']}", type="primary", use_container_width=True):
                        ok, msg = respond_to_invitation(inv["id"], user, "accept")
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with b2:
                    if st.button("Decline", key=f"lone_rej_{inv['id']}", use_container_width=True):
                        ok, msg = respond_to_invitation(inv["id"], user, "reject")
                        if ok:
                            st.info(msg)
                            st.rerun()
                        else:
                            st.error(msg)
