import html
import streamlit as st
from services.user_service import get_user_profile, update_user_profile, update_user_passcode
from views.common import render_clinical_disclaimer

def render_profile_view(user: dict):
    user_id = user["id"]
    profile = get_user_profile(user_id) or user

    st.markdown("<h1 style='font-size: 24px; color: #234B70; margin-bottom: 6px;'>My Profile & Account Details</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 16px; color: #607086; margin-bottom: 20px;'>Manage your personal contact details, security passcode, and view account attributes.</p>", unsafe_allow_html=True)

    with st.container(border=True):
        esc_name = html.escape(str(profile.get("name", "")))
        esc_role = html.escape(str(profile.get("role", "")).title())
        esc_created = html.escape(str(profile.get("created_at", "Recorded in database")))

        st.markdown(f"""
        <div style="background-color: #F0F6FC; border-left: 4px solid #234B70; padding: 14px 18px; border-radius: 6px; margin-bottom: 20px;">
            <div style="font-size: 20px; font-weight: 700; color: #243447;">{esc_name}</div>
            <div style="font-size: 15px; color: #607086; margin-top: 2px;">Registered Role: <strong>{esc_role}</strong></div>
            <div style="font-size: 13px; color: #607086; margin-top: 4px;">Account Created: {esc_created}</div>
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

    st.write("")
    with st.container(border=True):
        st.markdown("<h3 style='margin: 0 0 6px 0; font-size: 18px; color: #234B70;'>Passcode / PIN Security</h3>", unsafe_allow_html=True)
        st.markdown("<p style='font-size: 15px; color: #607086; margin-bottom: 14px;'>Set a 4-to-6 digit numeric passcode to sign in without typing passwords. Ideal for seniors and quick access.</p>", unsafe_allow_html=True)

        current_pin = profile.get("passcode") or "1234"
        st.info(f"Current Configured Passcode: **{current_pin}**")

        with st.form("update_passcode_form"):
            new_pin = st.text_input("New 4-Digit Passcode (PIN)", max_chars=6, placeholder="e.g. 5678", type="password")
            pin_submit = st.form_submit_button("Update Passcode", type="primary", use_container_width=True)

        if pin_submit:
            ok, msg = update_user_passcode(user_id, new_pin)
            if ok:
                st.session_state.user["passcode"] = new_pin.strip()
                st.success(f"Passcode successfully updated to '{new_pin.strip()}'. You can now use this PIN to sign in.")
                st.rerun()
            else:
                st.error(msg)

    render_clinical_disclaimer()
