import streamlit as st

DEARLY_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    /* Global canvas & typography */
    .stApp {
        background-color: #F5F8FC !important;
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    /* Protect Streamlit icon ligatures from font-family override */
    [data-testid*="Icon"],
    [data-testid*="stIcon"],
    .material-symbols-rounded,
    [class*="material-symbols"],
    [class*="css"] span:empty {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* Base text colors and sizes: 18px default as per Section 6 */
    p, li, label, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
        color: #243447;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 18px !important;
        line-height: 1.55 !important;
    }

    h1 {
        color: #234B70 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }

    h2 {
        color: #234B70 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 22px !important;
        font-weight: 700 !important;
    }

    h3 {
        color: #234B70 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 19px !important;
        font-weight: 700 !important;
    }

    /* Important elderly instruction text: 20px or larger */
    .elderly-instruction {
        font-size: 21px !important;
        font-weight: 700 !important;
        color: #243447 !important;
        line-height: 1.4 !important;
    }

    /* Main layout container */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1180px;
    }

    /* Native container borders (cards) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1px solid #DFE6EE !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(36, 52, 71, 0.04) !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #DFE6EE !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #243447 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        font-size: 17px !important;
        font-weight: 500 !important;
        padding: 5px 0 !important;
    }

    /* Hero Header for Auth & Dashboards */
    .dearly-auth-hero {
        background-color: #234B70 !important;
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 24px;
        border: 1px solid #193B5A;
    }
    .dearly-auth-hero h1 {
        color: #FFFFFF !important;
        margin: 8px 0 6px 0 !important;
        font-size: 28px !important;
    }
    .dearly-auth-hero p {
        color: #E2E8F0 !important;
        margin: 0 !important;
        font-size: 18px !important;
    }
    .dearly-auth-hero .tag {
        background-color: #193B5A !important;
        color: #FFFFFF !important;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
        display: inline-block;
    }

    .dearly-hero-header {
        background-color: #234B70 !important;
        border-radius: 12px;
        padding: 22px 26px;
        margin-bottom: 20px;
        border: 1px solid #193B5A;
    }
    .dearly-hero-header h1 {
        color: #FFFFFF !important;
        margin: 0 !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    .dearly-hero-header p {
        color: #E2E8F0 !important;
        margin: 4px 0 0 0 !important;
        font-size: 16px !important;
    }
    .dearly-hero-header .role-tag {
        background-color: #193B5A !important;
        color: #FFFFFF !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
    }

    /* Buttons: Beautiful, clean, single-bordered design */
    div.stButton > button {
        min-height: 48px !important;
        border-radius: 8px !important;
        padding: 0.55rem 1.3rem !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        border: 1px solid #234B70 !important;
        background-color: #FFFFFF !important;
        color: #234B70 !important;
        box-shadow: none !important;
        outline: none !important;
        transition: all 0.15s ease-in-out !important;
        text-align: center !important;
    }

    /* Ensure NO child elements inside buttons have borders, outlines, or extra backgrounds */
    div.stButton > button * {
        border: none !important;
        outline: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: inherit !important;
        font-size: 16px !important;
    }

    /* Hover for default/secondary */
    div.stButton > button:hover {
        background-color: #F0F6FC !important;
        border-color: #193B5A !important;
        color: #193B5A !important;
    }

    /* Primary Button */
    div.stButton > button[kind="primary"] {
        background-color: #234B70 !important;
        border: 1px solid #234B70 !important;
        color: #FFFFFF !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background-color: #193B5A !important;
        border-color: #193B5A !important;
        color: #FFFFFF !important;
    }

    div.stButton > button[kind="primary"] * {
        color: #FFFFFF !important;
    }

    /* Form labels & inputs */
    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] p {
        color: #243447 !important;
        font-weight: 600 !important;
        font-size: 17px !important;
    }
    .stTextInput input, .stSelectbox select, .stTextArea textarea, .stDateInput input, .stTimeInput input {
        background-color: #FFFFFF !important;
        color: #243447 !important;
        border: 1px solid #DFE6EE !important;
        font-size: 17px !important;
        border-radius: 8px !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] p,
    .stTabs [data-baseweb="tab"] span {
        color: #607086 !important;
        font-size: 17px !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span {
        color: #234B70 !important;
        font-weight: 700 !important;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #234B70 !important;
    }

    /* Metric displays */
    [data-testid="stMetricValue"] {
        color: #234B70 !important;
        font-size: 26px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] p {
        color: #607086 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
    }

    /* Status Badges */
    .badge-taken {
        background-color: #EBF8F2;
        color: #23815C;
        border: 1px solid #A8E5CB;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        text-align: center;
    }
    .badge-pending {
        background-color: #FEF7ED;
        color: #A66B16;
        border: 1px solid #FCD9A8;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        text-align: center;
    }
    .badge-overdue {
        background-color: #FDF2F2;
        color: #B84040;
        border: 1px solid #F8C3C3;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        text-align: center;
    }
    .badge-skipped {
        background-color: #EDF2F7;
        color: #607086;
        border: 1px solid #DFE6EE;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        text-align: center;
    }
    .badge-missed {
        background-color: #FDF2F2;
        color: #B84040;
        border: 1px solid #F8C3C3;
        padding: 5px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        text-align: center;
    }
</style>
"""

def inject_custom_styles():
    st.markdown(DEARLY_CSS, unsafe_allow_html=True)

def render_hero_header(title: str, subtitle: str, role_badge: str = None):
    badge_html = f'<span class="role-tag">{role_badge}</span>' if role_badge else ''
    st.markdown(f"""
    <div class="dearly-hero-header">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <div>
                {badge_html}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_clinical_disclaimer():
    st.markdown("""
    <div style="background-color: #EDF2F7; border: 1px solid #DFE6EE; border-radius: 8px; padding: 12px 16px; margin: 20px 0; font-size: 15px; color: #607086;">
        <strong style="color: #243447;">Clinical & Safety Notice:</strong> Dearly is an informational coordination tool. It does not provide medical diagnosis, prescribe drugs, or substitute licensed medical care or municipal emergency dispatch. In a life-threatening emergency, call local emergency services (112 or 911) immediately.
    </div>
    """, unsafe_allow_html=True)

def render_unfinished_module(module_name: str, description: str, next_phase: str = "Phase 2"):
    with st.container(border=True):
        st.markdown(f"<h2 style='color: #234B70; margin-top: 0;'>{module_name}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 18px; color: #243447;'>{description}</p>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background-color: #EDF2F7; border: 1px solid #DFE6EE; border-radius: 8px; padding: 14px 18px; margin-top: 14px;">
            <span style="font-size: 14px; font-weight: 700; color: #234B70; text-transform: uppercase;">Upcoming in {next_phase}</span>
            <p style="margin: 6px 0 0 0; font-size: 16px; color: #607086;">
                The architectural foundation and data models for this module are established. Full interactive workflow will be integrated in {next_phase}.
            </p>
        </div>
        """, unsafe_allow_html=True)
