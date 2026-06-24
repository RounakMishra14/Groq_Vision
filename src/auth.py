from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.database import create_user, validate_user

ASSET_PATH = Path(__file__).parent / "assets" / "groq_api_key_instruction.png"
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
.stApp {
    background:
        radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.14), transparent 30%),
        linear-gradient(135deg, #02070b 0%, #03151b 50%, #010507 100%) !important;
    color: #eafcff !important;
}

.block-container {
    max-width: 1280px !important;
    padding-top: 1.4rem !important;
    padding-bottom: 2rem !important;
}

header, footer {
    visibility: hidden;
}

[data-testid="stSidebar"] {
    display: none;
}

h1 {
    color: #00e5ff !important;
    text-align: center !important;
    font-size: 4.2rem !important;
    font-weight: 900 !important;
    line-height: 1.05 !important;
    margin-bottom: 0 !important;
    text-shadow: 0 0 22px rgba(0, 229, 255, 0.45);
}

h2, h3, h4 {
    color: #00e5ff !important;
}

p, li, label, span {
    color: #eafcff !important;
}

a {
    color: #00e5ff !important;
    font-weight: 800 !important;
    text-decoration: none !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(0, 229, 255, 0.35) !important;
    border-radius: 18px !important;
    background: rgba(1, 16, 23, 0.78) !important;
    box-shadow: 0 0 35px rgba(0, 229, 255, 0.08) !important;
}

.stTextInput input {
    background-color: rgba(0, 0, 0, 0.25) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.45) !important;
    border-radius: 10px !important;
}

.stTextInput input:focus {
    border-color: #00e5ff !important;
    box-shadow: 0 0 0 1px #00e5ff !important;
}

.stButton > button,
.stFormSubmitButton > button {
    width: 100%;
    border-radius: 10px !important;
    border: 1px solid rgba(0, 229, 255, 0.75) !important;
    background: linear-gradient(135deg, #00e5ff, #009ab8) !important;
    color: #001014 !important;
    font-weight: 900 !important;
    box-shadow: 0 0 18px rgba(0, 229, 255, 0.30);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 18px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.20);
}

.stTabs [aria-selected="true"] p {
    color: #00e5ff !important;
    font-weight: 900 !important;
}

[data-testid="stImage"] img {
    border-radius: 14px;
    border: 1px solid rgba(0, 229, 255, 0.45);
    box-shadow: 0 0 24px rgba(0, 229, 255, 0.12);
}

.stAlert {
    background: rgba(0, 229, 255, 0.08) !important;
    border: 1px solid rgba(0, 229, 255, 0.35) !important;
    color: #eafcff !important;
}

hr {
    border-color: rgba(0, 229, 255, 0.22) !important;
}

.small-center {
    text-align: center;
    color: rgba(234, 252, 255, 0.68) !important;
    font-weight: 700;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    with st.container(border=True):
        st.title("Groq Vision")
        st.markdown(
            "<p class='small-center'>Batch MCQ Extractor</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")


def _render_left_instructions() -> None:
    with st.container(border=True):
        st.subheader("🔑 Get Your Groq API Key")
        st.write("You need a Groq API Key to use this application.")

        st.markdown("### 1. Navigate to Groq Console")
        st.write("Go to the Groq API Keys page:")
        st.markdown(f"[{GROQ_KEYS_URL}]({GROQ_KEYS_URL})")
        st.markdown("---")

        st.markdown("### 2. Create Your API Key")
        st.write('Click on **"Create API Key"** to generate a new API key.')
        st.markdown("---")

        st.markdown("### 3. Use in This App")
        st.write("After logging in, this application will ask you to enter your Groq API Key.")

        st.info("🛡 Your API key is encrypted before saving. Do not share your key with anyone.")


def _login_form() -> None:
    tabs = st.tabs(["Login", "Create New Account"])

    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                if not username or not password:
                    st.error("Email and password required")
                elif validate_user(username.strip().lower(), password):
                    st.session_state.logged_in = True
                    st.session_state.username = username.strip().lower()
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
                if not username or not password:
                    st.error("Email and password required")
                elif password != confirm:
                    st.error("Passwords do not match")
                elif create_user(username.strip().lower(), password):
                    st.success("Account created. Please login now.")
                else:
                    st.error("User already exists")


def _render_right_login() -> None:
    with st.container(border=True):
        st.markdown("### How to get your API Key")

        if ASSET_PATH.exists():
            st.image(str(ASSET_PATH), use_container_width=True)
        else:
            st.warning("Instruction image not found: src/assets/groq_api_key_instruction.png")

        st.markdown("#### Navigate to Groq Console")
        st.markdown(f"[🌐 {GROQ_KEYS_URL}]({GROQ_KEYS_URL})")
        st.markdown("---")

        _login_form()

        st.info("🔒 Secure. Fast. Powered by Groq. Your Groq key will be requested only after successful login.")


def render_login_page() -> None:
    apply_dark_login_css()
    _render_header()

    left, right = st.columns([1.05, 1.25], gap="large")

    with left:
        _render_left_instructions()

    with right:
        _render_right_login()

    st.markdown(
        "<p class='small-center'>🔒 Secure. Fast. Powered by Groq.</p>",
        unsafe_allow_html=True,
    )


def logout() -> None:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.groq_api_key = None
    st.rerun()
