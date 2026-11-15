import streamlit as st
from services.auth_service import authenticate, authenticate_passcode
from services.user_service import register_user
from views.common import render_clinical_disclaimer

def render_auth_view():
    st.markdown("""
    <div class="dearly-auth-hero">
        <span class="tag">Dearly Healthcare</span>
        <h1>Care that stays close.</h1>
        <p>A connected care space for older adults, family members, and caregivers.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_signin, tab_passcode, tab_register, tab_about = st.tabs([
        "Sign In (Email)",
        "Passcode Access (PIN)",
        "Create Account",
        "About the Platform",
    ])

    # 1. SIGN IN TAB
    with tab_signin:
        col_demo, col_form = st.columns([1.1, 1], gap="large")

        with col_demo:
            with st.container(border=True):
                st.markdown("<h2 style='margin: 0 0 4px 0; font-size: 20px; color: #234B70;'>Demo Account Access</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 16px;'>Select a pre-configured role to inspect the tailored care interface:</p>", unsafe_allow_html=True)

                if st.button("Sign in as Elderly (Asha Patil)", use_container_width=True, type="primary"):
                    user = authenticate("elderly@dearly.demo", "demo123")
                    if user:
                        st.session_state.user = user
                        st.session_state.selected_ward_id = user["id"]
                        st.session_state.current_page = "Home"
                        st.rerun()

                st.write("")
                if st.button("Sign in as Caregiver (Rahul Patil)", use_container_width=True):
                    user = authenticate("caregiver@dearly.demo", "demo123")
                    if user:
                        st.session_state.user = user
                        st.session_state.current_page = "Overview"
                        st.rerun()

                st.write("")
                if st.button("Sign in as Family Member (Neha Patil)", use_container_width=True):
                    user = authenticate("family@dearly.demo", "demo123")
                    if user:
                        st.session_state.user = user
                        st.session_state.current_page = "Overview"
                        st.rerun()

                st.write("")
                st.caption("Demo profiles are pre-seeded with synthetic care routines for evaluation.")

        with col_form:
            with st.container(border=True):
                st.markdown("<h2 style='margin: 0 0 4px 0; font-size: 20px; color: #234B70;'>Sign in with Credentials</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 12px;'>Enter your registered email address and password.</p>", unsafe_allow_html=True)

                with st.form("standard_login_form"):
                    email_input = st.text_input("Email Address", placeholder="name@example.com")
                    password_input = st.text_input("Password", type="password")
                    submit_btn = st.form_submit_button("Sign In", use_container_width=True, type="primary")

                if submit_btn:
                    if not email_input or not password_input:
                        st.error("Please enter both email address and password.")
                    else:
                        user = authenticate(email_input, password_input)
                        if user:
                            st.session_state.user = user
                            st.session_state.selected_ward_id = user["id"] if user["role"] == "elderly" else None
                            st.session_state.current_page = "Home" if user["role"] == "elderly" else "Overview"
                            st.rerun()
                        else:
                            st.error("Invalid email or password. Please verify your credentials.")

    # 2. PASSCODE / PIN TAB (Challenge Specification)
    with tab_passcode:
        p_c1, p_c2 = st.columns([1.1, 1], gap="large")
        with p_c1:
            with st.container(border=True):
                st.markdown("<h2 style='margin: 0 0 4px 0; font-size: 20px; color: #234B70;'>Secure Passcode / PIN Access</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 14px;'>Designed specifically for older adults and care circle members. Sign in quickly using your personal 4-digit numeric passcode without typing passwords.</p>", unsafe_allow_html=True)

                with st.form("passcode_login_form"):
                    pin_input = st.text_input("Enter 4-Digit Passcode (PIN)", type="password", max_chars=6, placeholder="e.g. 1234")
                    pin_submit = st.form_submit_button("Sign In with Passcode", use_container_width=True, type="primary")

                if pin_submit:
                    if not pin_input:
                        st.error("Please enter your 4-digit passcode.")
                    else:
                        user = authenticate_passcode(pin_input)
                        if user:
                            st.session_state.user = user
                            st.session_state.selected_ward_id = user["id"] if user["role"] == "elderly" else None
                            st.session_state.current_page = "Home" if user["role"] == "elderly" else "Overview"
                            st.rerun()
                        else:
                            st.error("Incorrect passcode. Please check your PIN or sign in with email and password.")

        with p_c2:
            with st.container(border=True):
                st.markdown("<h3 style='margin: 0 0 6px 0; font-size: 18px; color: #234B70;'>Pre-Configured Demo PINs</h3>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 12px;'>Click any test account to authenticate instantly via passcode verification:</p>", unsafe_allow_html=True)

                if st.button("Asha Patil — PIN: 1234 (Elderly)", use_container_width=True):
                    user = authenticate_passcode("1234")
                    if user:
                        st.session_state.user = user
                        st.session_state.selected_ward_id = user["id"]
                        st.session_state.current_page = "Home"
                        st.rerun()

                st.write("")
                if st.button("Rahul Patil — PIN: 2345 (Caregiver)", use_container_width=True):
                    user = authenticate_passcode("2345")
                    if user:
                        st.session_state.user = user
                        st.session_state.current_page = "Overview"
                        st.rerun()

                st.write("")
                if st.button("Neha Patil — PIN: 3456 (Family)", use_container_width=True):
                    user = authenticate_passcode("3456")
                    if user:
                        st.session_state.user = user
                        st.session_state.current_page = "Overview"
                        st.rerun()

    # 2. CREATE ACCOUNT TAB
    with tab_register:
        reg_c1, reg_c2 = st.columns([1.2, 1], gap="large")

        with reg_c1:
            with st.container(border=True):
                st.markdown("<h2 style='margin: 0 0 4px 0; font-size: 20px; color: #234B70;'>Register for Dearly</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 16px;'>Create a new account as an older adult, family member, or caregiver.</p>", unsafe_allow_html=True)

                with st.form("register_user_form"):
                    reg_name = st.text_input("Full Name", placeholder="e.g. Kamala Rao")
                    reg_email = st.text_input("Email Address", placeholder="e.g. kamala.rao@example.com")
                    reg_phone = st.text_input("Phone Number", placeholder="e.g. +91 98200 99887")
                    
                    reg_role = st.selectbox(
                        "Your Account Role",
                        options=["elderly", "caregiver", "family"],
                        format_func=lambda r: {
                            "elderly": "Elderly Individual (Managing daily routines)",
                            "caregiver": "Primary Caregiver (Coordinating care)",
                            "family": "Family Member (Staying informed)",
                        }.get(r, r),
                    )

                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        reg_pw = st.text_input("Create Password (min. 6 characters)", type="password")
                    with col_p2:
                        reg_confirm_pw = st.text_input("Confirm Password", type="password")

                    st.caption("Your password will be encrypted using bcrypt. We never store plain-text passwords.")
                    st.write("")
                    submit_reg = st.form_submit_button("Create Account", use_container_width=True, type="primary")

                if submit_reg:
                    success, res = register_user(
                        name=reg_name,
                        email=reg_email,
                        phone=reg_phone,
                        password=reg_pw,
                        confirm_password=reg_confirm_pw,
                        role=reg_role,
                    )
                    if success:
                        st.session_state.user = res
                        st.session_state.selected_ward_id = res["id"] if res["role"] == "elderly" else None
                        st.session_state.current_page = "Home" if res["role"] == "elderly" else "Overview"
                        st.success(f"Welcome to Dearly, {res['name']}! Your account has been created.")
                        st.rerun()
                    else:
                        st.error(res)

        with reg_c2:
            with st.container(border=True):
                st.markdown("<h3 style='margin: 0 0 8px 0; font-size: 18px; color: #234B70;'>Role Guidance</h3>", unsafe_allow_html=True)
                st.markdown("""
                - **Elderly Individual**:  
                  Access an accessible, simplified interface designed for tracking daily medicines, contacting caregivers, and scheduling appointments.
                - **Caregiver**:  
                  Manage care routines, view adherence metrics, coordinate appointments, and log vitals for linked older adults.
                - **Family Member**:  
                  Stay connected and receive reassurance through daily care briefings and adherence summaries.
                """)

    # 3. ABOUT TAB
    with tab_about:
        st.markdown("""
        ### Shared Healthcare Ecosystem
        Managing prescriptions, vital records, and appointments is challenging for older adults living independently. At the same time, family members worry from afar and primary caregivers require consistent coordination.

        **Dearly bridges this gap through three tailored role workflows:**
        - **Older Adults**: Clear, distraction-free view answering what medicine to take right now with large confirmation buttons.
        - **Caregivers**: Unified medication adherence oversight, overdue dose escalation, and appointment scheduling.
        - **Family Members**: Peace of mind through adherence metrics, health observation trends, and daily care briefings.
        """)
        render_clinical_disclaimer()
