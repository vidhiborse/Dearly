import html
import time
import streamlit as st
from database import init_db, create_demo_users, authenticate_user
from views.common import inject_custom_styles
from views.auth_view import render_auth_view
from views.elderly_view import render_elderly_view
from views.caregiver_view import render_caregiver_view
from views.family_view import render_family_view
from views.profile_view import render_profile_view
from views.notification_view import render_notification_view
from views.care_circle_view import render_care_circle_view
from views.appointment_view import render_appointment_view
from views.health_view import render_health_view
from views.emergency_view import render_emergency_view
from views.analytics_view import render_analytics_view
from services.permissions import can_view_page
from services.reminder_service import sync_reminders_and_escalations, get_unread_notification_count
from services.appointment_service import sync_appointment_reminders
from services.care_circle_service import get_user_pending_invitations
from services.auth_service import get_accessible_elderly_wards
from services.emergency_service import get_active_emergency

# Initialize database schema and demo data safely
try:
    init_db()
    create_demo_users()
except Exception as e:
    import logging
    logging.getLogger("dearly").exception("Startup DB initialization warning: %s", e)

# Page configuration
st.set_page_config(
    page_title="Dearly — Care that stays close",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply accessible design system styles
inject_custom_styles()

# Initialize session state securely
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = None

# Sidebar branding
st.sidebar.markdown("""
<div style="padding: 4px 0 16px 0;">
    <h2 style="margin: 0; font-size: 24px; color: #234B70; font-weight: 700;">Dearly</h2>
    <p style="margin: 2px 0 0 0; font-size: 14px; color: #607086; font-weight: 500;">Care that stays close.</p>
</div>
""", unsafe_allow_html=True)

# Protected Route Guard
if st.session_state.user:
    user = st.session_state.user
    role = user.get("role", "")
    role_label = role.title()

    # Idempotent synchronization of reminders and overdue escalations on application load
    # Throttled to at most once every 30 seconds to optimize runtime efficiency and minimize database locks
    now_ts = time.time()
    last_sync = st.session_state.get("_last_sync_timestamp", 0)
    should_sync = (now_ts - last_sync) > 30

    if role == "elderly":
        primary_ward_id = user["id"]
        if should_sync:
            sync_reminders_and_escalations(user["id"], user=user)
            sync_appointment_reminders(user["id"], user=user)
            st.session_state["_last_sync_timestamp"] = now_ts
    else:
        accessible_wards = get_accessible_elderly_wards(user)
        primary_ward_id = accessible_wards[0]["id"] if accessible_wards else None
        if should_sync:
            for w in accessible_wards:
                sync_reminders_and_escalations(w["id"], user=user)
                sync_appointment_reminders(w["id"], user=user)
            st.session_state["_last_sync_timestamp"] = now_ts

    unread_notifs = get_unread_notification_count(user["id"])
    notif_nav_title = f"Reminders & Alerts ({unread_notifs})" if unread_notifs > 0 else "Reminders & Alerts"
    my_invites_count = len(get_user_pending_invitations(user))

    esc_name = html.escape(str(user['name']))
    esc_role = html.escape(str(role_label))

    st.sidebar.markdown(f"""
    <div style="background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px;">
        <div style="font-size: 12px; color: #607086; font-weight: 700; text-transform: uppercase;">Signed in as</div>
        <div style="font-size: 17px; font-weight: 700; color: #243447; margin-top: 2px;">{esc_name}</div>
        <div style="font-size: 14px; color: #234B70; font-weight: 600; margin-top: 4px;">Role: {esc_role}</div>
    </div>
    """, unsafe_allow_html=True)

    # Role-based navigation whitelist
    if role == "elderly":
        nav_options = ["Home", "My Medicines", "Reminders & Alerts", "Care Circle", "Appointments", "My Health", "Emergency Contacts", "Analytics & Reports", "My Profile"]
        default_page = "Home"
    elif role == "caregiver":
        nav_options = ["Overview", "Reminders & Alerts", "Elderly Profiles", "Care Circle", "Medication Monitoring", "Appointments", "Health Records", "Emergency SOS", "Analytics & Reports", "Activity History", "My Profile"]
        default_page = "Overview"
    elif role == "family":
        nav_options = ["Overview", "Reminders & Alerts", "Care Circle", "Care Updates", "Medicines", "Appointments", "Health Summary", "Emergency SOS", "Analytics & Reports", "My Profile"]
        default_page = "Overview"
    else:
        nav_options = ["Home", "My Profile"]
        default_page = "Home"

    # Enforce current page validity
    if st.session_state.current_page not in nav_options:
        st.session_state.current_page = default_page

    active_alert = get_active_emergency(primary_ward_id) if primary_ward_id else None

    def format_nav_item(opt_name: str) -> str:
        if opt_name == "Reminders & Alerts" and unread_notifs > 0:
            return f"Reminders & Alerts [{unread_notifs} new]"
        elif opt_name == "Care Circle" and my_invites_count > 0:
            return f"Care Circle [{my_invites_count} new]"
        elif opt_name in ("Emergency Contacts", "Emergency SOS") and active_alert:
            return f"{opt_name} [ACTIVE ALERT]"
        return opt_name

    selected_page = st.sidebar.radio(
        "Navigation",
        options=nav_options,
        index=nav_options.index(st.session_state.current_page),
        format_func=format_nav_item,
        key="role_navigation_radio",
    )
    st.session_state.current_page = selected_page

    # Backend Permission Enforcement
    if not can_view_page(user, selected_page):
        st.error(f"Unauthorized: Your role ({role}) does not have access to '{selected_page}'.")
        st.session_state.current_page = default_page
        st.rerun()

    st.sidebar.divider()

    # Evaluator Role Switcher
    st.sidebar.markdown("##### Switch Role for Evaluation")
    role_switch_options = {
        "elderly@dearly.demo": "Asha Patil (Elderly)",
        "caregiver@dearly.demo": "Rahul Patil (Caregiver)",
        "family@dearly.demo": "Neha Patil (Family)",
    }
    
    current_email = user.get("email", "")
    available_switches = {k: v for k, v in role_switch_options.items() if k != current_email}
    for target_email, target_label in available_switches.items():
        if st.sidebar.button(f"Switch to {target_label}", use_container_width=True):
            switched_user = authenticate_user(target_email, "demo123")
            if switched_user:
                st.session_state.user = switched_user
                st.session_state.selected_ward_id = switched_user["id"] if switched_user["role"] == "elderly" else None
                st.session_state.current_page = "Home" if switched_user["role"] == "elderly" else "Overview"
                st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # Page Routing
    if selected_page == "My Profile":
        render_profile_view(user)
    elif selected_page == "Reminders & Alerts":
        render_notification_view(user)
    elif selected_page == "Care Circle":
        render_care_circle_view(user)
    elif selected_page == "Appointments":
        render_appointment_view(user)
    elif selected_page in ("Health Records", "My Health", "Health Summary"):
        render_health_view(user, page=selected_page)
    elif selected_page in ("Emergency SOS", "Emergency Contacts"):
        render_emergency_view(user)
    elif selected_page in ("Analytics & Reports", "Reports & Analytics"):
        render_analytics_view(user)
    elif role == "elderly":
        render_elderly_view(user, page=selected_page)
    elif role == "caregiver":
        render_caregiver_view(user, page=selected_page)
    elif role == "family":
        render_family_view(user, page=selected_page)
    else:
        st.error(f"Unrecognized role: {role}")
else:
    # Public unauthenticated view
    st.sidebar.markdown("""
    <div style="background-color: #F0F6FC; border: 1px solid #C8DAEB; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
        <div style="font-weight: 700; font-size: 14px; color: #234B70; margin-bottom: 6px;">Evaluation Accounts:</div>
        <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #243447;">
            <li style="margin-bottom: 4px;"><code>elderly@dearly.demo</code></li>
            <li style="margin-bottom: 4px;"><code>caregiver@dearly.demo</code></li>
            <li style="margin-bottom: 4px;"><code>family@dearly.demo</code></li>
        </ul>
        <div style="margin-top: 8px; font-size: 12px; color: #607086;">Use the Demo Account buttons on the sign-in screen for instant access.</div>
    </div>
    """, unsafe_allow_html=True)
    render_auth_view()

st.sidebar.divider()
st.sidebar.caption("Dearly Prototype • Healthcare Coordination • Informational tool, not a medical device")
