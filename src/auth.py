from __future__ import annotations

import streamlit as st

from src.database import create_user, validate_user

GROQ_KEYS_URL = "https://console.groq.com/keys"


def init_auth_state() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None


def apply_dark_login_css() -> None:
    st.markdown(
        """
<style>
/* Main page */
.stApp {
    background:
        radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.14), transparent 28%),
        linear-gradient(135deg, #02070b 0%, #03151b 52%, #010507 100%) !important;
    color: #eafcff !important;
}
.block-container {
    max-width: 760px !important;
    padding-top: 1.4rem !important;
    padding-bottom: 2rem !important;
}
header, footer {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}

/* Text */
h1, h2, h3, h4, h5, h6, p, label, span, div {
    color: #eafcff;
}
a { color: #00e5ff !important; }

/* Hero */
.groq-hero {
    border: 1px solid rgba(0, 229, 255, 0.42);
    border-radius: 18px;
    padding: 30px 26px 24px 26px;
    background: linear-gradient(180deg, rgba(1, 23, 31, 0.92), rgba(1, 12, 18, 0.92));
    box-shadow: 0 0 45px rgba(0, 229, 255, 0.08);
    text-align: center;
    margin-bottom: 18px;
}
.groq-title {
    color: #00e5ff !important;
    font-size: 50px;
    font-weight: 900;
    line-height: 1;
    margin: 0;
    text-shadow: 0 0 24px rgba(0, 229, 255, 0.55);
}
.groq-subtitle {
    color: #ffffff !important;
    font-size: 17px;
    font-weight: 750;
    margin-top: 10px;
}
.groq-line {
    height: 1px;
    width: 84%;
    margin: 22px auto 0 auto;
    background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.85), transparent);
}

/* Native Streamlit cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: rgba(0, 229, 255, 0.42) !important;
    background: linear-gradient(180deg, rgba(1, 23, 31, 0.84), rgba(1, 11, 17, 0.92)) !important;
    box-shadow: 0 0 32px rgba(0, 229, 255, 0.06) !important;
}

/* Inputs */
.stTextInput label, .stTabs [data-baseweb="tab"] p {
    color: #eafcff !important;
    font-weight: 750 !important;
}
.stTextInput input {
    background-color: rgba(0, 0, 0, 0.25) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.55) !important;
    border-radius: 10px !important;
}
.stTextInput input:focus {
    border-color: #00e5ff !important;
    box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.35) !important;
}

/* Buttons */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    width: 100% !important;
    border-radius: 10px !important;
    border: 1px solid rgba(0, 229, 255, 0.72) !important;
    background: linear-gradient(135deg, #00e5ff, #009bb8) !important;
    color: #001014 !important;
    font-weight: 900 !important;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.25) !important;
    text-decoration: none !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stLinkButton > a:hover {
    transform: translateY(-1px);
    box-shadow: 0 0 28px rgba(0, 229, 255, 0.40) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 22px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.22);
}
.stTabs [aria-selected="true"] p {
    color: #00e5ff !important;
    font-weight: 900 !important;
}

/* Alerts */
.stAlert {
    background: rgba(0, 229, 255, 0.08) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.28) !important;
}

/* Footer */
.login-footer {
    text-align: center;
    color: rgba(234, 252, 255, 0.70) !important;
    font-weight: 700;
    margin-top: 16px;
    font-size: 14px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
<div class="groq-hero">
    <div class="groq-title">Groq Vision</div>
    <div class="groq-subtitle">Batch MCQ Extractor</div>
    <div class="groq-line"></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_api_key_card() -> None:
    with st.container(border=True):
        st.markdown("### 🔑 Need a Groq API Key?")
        st.write("Generate your free Groq API key here:")
        st.link_button("🚀 Get Free Groq API Key", GROQ_KEYS_URL)
        st.caption(
            "After creating the key, return here and log in. "
            "Your Groq key will be requested after successful login."
        )


def _render_login_register_card() -> None:
    with st.container(border=True):
        tabs = st.tabs(["Login", "Create New Account"])

        with tabs[0]:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login")

                if submitted:
                    clean_username = username.strip().lower()

                    if not clean_username or not password:
                        st.error("Email and password required")
                    elif validate_user(clean_username, password):
                        st.session_state.logged_in = True
                        st.session_state.username = clean_username
                        st.rerun()
                    else:
                        st.error("Invalid login")

        with tabs[1]:
            with st.form("register_form", clear_on_submit=False):
                username = st.text_input("Email", key="register_email")
                password = st.text_input("Password", type="password", key="register_password")
                confirm = st.text_input("Confirm Password", type="password", key="register_confirm")
                submitted = st.form_submit_button("Create Account")

                if submitted:
                    clean_username = username.strip().lower()

                    if not clean_username or not password:
                        st.error("Email and password required")
                    elif password != confirm:
                        st.error("Passwords do not match")
                    elif create_user(clean_username, password):
                        st.success("Account created. Please login now.")
                    else:
                        st.error("User already exists")


def _render_security_card() -> None:
    with st.container(border=True):
        st.markdown("### 🔒 Secure. Fast. Powered by Groq.")
        st.caption(
            "Your API key is encrypted and stored securely. "
            "It is only used to process your uploaded MCQ images."
        )


def render_login_page() -> None:
    apply_dark_login_css()
    _render_hero()
    _render_api_key_card()
    _render_login_register_card()
    _render_security_card()
    st.markdown('<div class="login-footer">🔒 Secure. Fast. Powered by Groq.</div>', unsafe_allow_html=True)


def logout() -> None:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.groq_api_key = None
    st.rerun()
