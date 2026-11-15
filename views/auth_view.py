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
                st.markdown("<h3 style='margin: 0 0 4px 0; font-size: 18px; color: #234B70;'>Quick Demo Sign-in</h3>", unsafe_allow_html=True)
                st.caption("Select a role to inspect the personalized care workflow:")
                st.write("")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Sign in as Elderly\n(Asha Patil)", use_container_width=True, type="primary"):
                        user = authenticate("elderly@dearly.demo", "demo123")
                        if user:
                            st.session_state.user = user
                            st.session_state.selected_ward_id = user["id"]
                            st.rerun()

                with c2:
                    if st.button("Sign in as Caregiver\n(Rahul Patil)", use_container_width=True):
                        user = authenticate("caregiver@dearly.demo", "demo123")
                        if user:
                            st.session_state.user = user
                            st.rerun()

                st.write("")
                if st.button("Sign in as Family Member (Neha Patil)", use_container_width=True):
                    user = authenticate("family@dearly.demo", "demo123")
                    if user:
                        st.session_state.user = user
                        st.rerun()

                st.write("")
                st.info("Demo Accounts Password: **demo123**")

        with col_form:
            with st.container(border=True):
                st.markdown("<h3 style='margin: 0 0 4px 0; font-size: 18px; color: #234B70;'>Standard Credentials</h3>", unsafe_allow_html=True)
                st.caption("Sign in with your registered email and password.")
                st.write("")

                with st.form("standard_login_form"):
                    email_input = st.text_input("Email Address", placeholder="elderly@dearly.demo")
                    password_input = st.text_input("Password", type="password", placeholder="demo123")
                    submit_btn = st.form_submit_button("Sign In to Dearly", use_container_width=True, type="primary")

                if submit_btn:
                    if not email_input or not password_input:
                        st.error("Please enter both email and password.")
                    else:
                        user = authenticate(email_input, password_input)
                        if user:
                            st.session_state.user = user
                            st.session_state.selected_ward_id = user["id"] if user["role"] == "elderly" else None
                            st.rerun()
                        else:
                            st.error("Invalid credentials. Please verify your email and password.")

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
