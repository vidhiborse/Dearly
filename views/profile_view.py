import streamlit as st
from services.user_service import get_user_profile, update_user_profile
from views.common import render_clinical_disclaimer

def render_profile_view(user: dict):
    user_id = user["id"]
    profile = get_user_profile(user_id) or user

    st.markdown("<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>My Profile & Account Details</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 20px;'>Manage your personal contact details and view account attributes.</p>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"""
        <div style="background-color: #F0F6FC; border-left: 4px solid #234B70; padding: 14px 18px; border-radius: 6px; margin-bottom: 20px;">
            <div style="font-size: 20px; font-weight: 700; color: #243447;">{profile['name']}</div>
            <div style="font-size: 15px; color: #607086; margin-top: 2px;">Registered Role: <strong>{profile['role'].title()}</strong></div>
            <div style="font-size: 13px; color: #607086; margin-top: 4px;">Account Created: {profile.get('created_at', 'Recorded in database')}</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("edit_user_account_profile"):
            st.markdown("<h3 style='margin: 0 0 12px 0; font-size: 18px; color: #234B70;'>Personal Information</h3>", unsafe_allow_html=True)
            
            name_input = st.text_input("Full Name", value=profile.get("name", ""))
            phone_input = st.text_input("Phone Number", value=profile.get("phone", ""))
            
            col_ro1, col_ro2 = st.columns(2)
            with col_ro1:
                st.text_input("Registered Email (Cannot be changed)", value=profile.get("email", ""), disabled=True)
            with col_ro2:
                st.text_input("Account Role (System Managed)", value=profile.get("role", "").title(), disabled=True)

            st.caption("Account roles are established during registration and cannot be modified through profile settings.")
            st.write("")
            submit_btn = st.form_submit_button("Save Profile Changes", type="primary", use_container_width=True)

        if submit_btn:
            ok, msg = update_user_profile(user_id=user_id, name=name_input, phone=phone_input)
            if ok:
                st.session_state.user["name"] = name_input.strip()
                st.session_state.user["phone"] = phone_input.strip()
                st.success("Profile details updated successfully in SQLite.")
                st.rerun()
            else:
                st.error(msg)

    render_clinical_disclaimer()
