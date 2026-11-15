import streamlit as st
from database import init_db, create_demo_users, authenticate_user
from views.common import inject_custom_styles
from views.auth_view import render_auth_view
from views.elderly_view import render_elderly_view
from views.caregiver_view import render_caregiver_view
from views.family_view import render_family_view

# Initialize database schema and demo data
init_db()
create_demo_users()

# Page configuration
st.set_page_config(
    page_title="Dearly — Care that stays close",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply accessible design system styles
inject_custom_styles()

# Initialize session state
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = None

# Sidebar navigation & role management
st.sidebar.markdown("""
<div style="padding: 4px 0 16px 0;">
    <h2 style="margin: 0; font-size: 24px; color: #234B70; font-weight: 700;">Dearly</h2>
    <p style="margin: 2px 0 0 0; font-size: 14px; color: #607086; font-weight: 500;">Care that stays close.</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.user:
    user = st.session_state.user
    role = user["role"]
    role_label = role.title()

    st.sidebar.markdown(f"""
    <div style="background-color: #FFFFFF; border: 1px solid #DFE6EE; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px;">
        <div style="font-size: 12px; color: #607086; font-weight: 700; text-transform: uppercase;">Signed in as</div>
        <div style="font-size: 17px; font-weight: 700; color: #243447; margin-top: 2px;">{user['name']}</div>
        <div style="font-size: 14px; color: #234B70; font-weight: 600; margin-top: 4px;">Role: {role_label}</div>
    </div>
    """, unsafe_allow_html=True)

    # Role-specific navigation options as per Phase 1 spec
    if role == "elderly":
        nav_options = ["Home", "My Medicines", "Appointments", "My Health", "Emergency Contacts"]
        default_page = "Home"
    elif role == "caregiver":
        nav_options = ["Overview", "Elderly Profiles", "Medication Monitoring", "Appointments", "Health Records", "Activity History"]
        default_page = "Overview"
    elif role == "family":
        nav_options = ["Overview", "Care Updates", "Medicines", "Appointments", "Health Summary"]
        default_page = "Overview"
    else:
        nav_options = ["Home"]
        default_page = "Home"

    if st.session_state.current_page not in nav_options:
        st.session_state.current_page = default_page

    selected_page = st.sidebar.radio(
        "Navigation",
        options=nav_options,
        index=nav_options.index(st.session_state.current_page),
        key="role_navigation_radio",
    )
    st.session_state.current_page = selected_page

    st.sidebar.divider()

    # Evaluator Role Switcher
    st.sidebar.markdown("##### Switch Role for Evaluation")
    role_switch_options = {
        "elderly@dearly.demo": "Asha Patil (Elderly)",
        "caregiver@dearly.demo": "Rahul Patil (Caregiver)",
        "family@dearly.demo": "Neha Patil (Family)",
    }
    
    current_email = user["email"]
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
        st.session_state.user = None
        st.session_state.pop("selected_ward_id", None)
        st.session_state.pop("family_ward_id", None)
        st.session_state.current_page = None
        st.rerun()

    # Route to role view with selected page
    if role == "elderly":
        render_elderly_view(user, page=selected_page)
    elif role == "caregiver":
        render_caregiver_view(user, page=selected_page)
    elif role == "family":
        render_family_view(user, page=selected_page)
    else:
        st.error(f"Unrecognized role: {role}")
else:
    st.sidebar.markdown("""
    <div style="background-color: #F0F6FC; border: 1px solid #C8DAEB; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
        <div style="font-weight: 700; font-size: 14px; color: #234B70; margin-bottom: 6px;">Pre-configured Accounts:</div>
        <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #243447;">
            <li style="margin-bottom: 4px;"><code>elderly@dearly.demo</code></li>
            <li style="margin-bottom: 4px;"><code>caregiver@dearly.demo</code></li>
            <li style="margin-bottom: 4px;"><code>family@dearly.demo</code></li>
        </ul>
        <div style="margin-top: 8px; font-size: 12px; color: #607086;">Click the Demo Account buttons on the login screen for instant access.</div>
    </div>
    """, unsafe_allow_html=True)
    render_auth_view()

st.sidebar.divider()
st.sidebar.caption("Dearly Prototype • Healthcare Coordination • Informational tool, not a medical device")
