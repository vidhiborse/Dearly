import streamlit as st
from services.auth_service import authenticate
from views.common import render_clinical_disclaimer

def render_auth_view():
    st.markdown("""
    <div class="dearly-auth-hero">
        <span class="tag">Dearly Healthcare</span>
        <h1>Care that stays close.</h1>
        <p>A connected care space for older adults, family members, and caregivers.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_signin, tab_about = st.tabs(["Sign In", "About the Platform"])

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
                            st.error("Invalid credentials. Please verify your email or password.")

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
