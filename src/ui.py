from __future__ import annotations

import streamlit as st

from src.auth import init_auth_state
from src.components import (
    apply_dashboard_css,
    refresh_usage_panel,
    render_hero_header,
    render_login_page,
    render_pdf_download_section,
    render_profile_menu,
    render_results_section,
)
from src.config import GROQ_KEYS_URL, MAX_IMAGES, MODEL_NAME
from src.database import get_groq_key, init_db, save_groq_key
from src.encryption import decrypt, encrypt
from src.extraction_runner import run_extraction
from src.groq_usage import GroqLimitConfig, GroqUsageTracker
from src.image_processor import GroqImagePrepConfig
from src.usage_store import init_api_daily_usage_table


DEFAULT_GROQ_LIMITS = GroqLimitConfig(
    model_name=MODEL_NAME,
    rpm_limit=30,
    rpd_limit=1000,
    tpm_limit=30000,
    tpd_limit=500000,
)

PRODUCTION_PREP_CONFIG = GroqImagePrepConfig(
    crop_enabled=True,
    compression_enabled=True,
    brightness_threshold=170,
    max_saturation=110,
    safety_expand_ratio=0.07,
    target_width=900,
    jpeg_quality=50,
    debug=False,
)

PRODUCTION_MAX_COMPLETION_TOKENS = 2048


def initialize_session_state() -> None:
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = []

    if "groq_usage_tracker" not in st.session_state:
        st.session_state.groq_usage_tracker = GroqUsageTracker(limits=DEFAULT_GROQ_LIMITS)

    if "upload_widget_key" not in st.session_state:
        st.session_state.upload_widget_key = 0

    if "groq_api_key" not in st.session_state:
        st.session_state.groq_api_key = None

    if "show_change_key" not in st.session_state:
        st.session_state.show_change_key = False


def run_app() -> None:
    st.set_page_config(page_title="Groq Vision", layout="wide")

    init_db()
    init_api_daily_usage_table()
    init_auth_state()
    initialize_session_state()

    if not st.session_state.logged_in:
        render_login_page()
        st.stop()

    apply_dashboard_css()

    username = st.session_state.username
    groq_api_key = load_or_request_groq_key(username)
    if not groq_api_key:
        st.stop()

    render_main_app(username=username, groq_api_key=groq_api_key)


def load_or_request_groq_key(username: str) -> str | None:
    saved_key = get_groq_key(username)

    if saved_key:
        try:
            groq_api_key = decrypt(saved_key)
            st.session_state.groq_api_key = groq_api_key
            return groq_api_key
        except Exception:
            st.session_state.groq_api_key = None
            st.error("Saved Groq key could not be decrypted. Please save it again.")

    render_api_key_required_page(username)
    return None


def render_api_key_required_page(username: str) -> None:
    render_hero_header()

    st.markdown(
        """
        <div class="gv-card">
            <div class="gv-section-title">Groq API Key Required</div>
            <div class="gv-caption">
                Generate your Groq API key once, paste it below, and this app will remember it for your account.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button("Get Free Groq API Key", GROQ_KEYS_URL, use_container_width=True)

    with st.form("save_groq_key_form"):
        user_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
        submitted = st.form_submit_button("Save Groq Key", use_container_width=True)

    if submitted:
        if not user_key.strip():
            st.error("Please enter your Groq API key.")
        else:
            save_groq_key(username, encrypt(user_key.strip()))
            st.success("Groq key saved. Loading app...")
            st.rerun()

    st.markdown(
        """
        <div class="gv-average">Your API key is encrypted before saving and is only used for extraction requests.</div>
        """,
        unsafe_allow_html=True,
    )


def render_main_app(username: str, groq_api_key: str) -> None:
    header_col, profile_col = st.columns([5.4, 1.0], gap="large", vertical_alignment="top")

    with header_col:
        render_hero_header()

    with profile_col:
        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
        render_profile_menu(username)

    usage_placeholder = st.empty()
    refresh_usage_panel(usage_placeholder, groq_api_key)

    st.markdown("<br/>", unsafe_allow_html=True)
    render_upload_and_results(username=username, groq_api_key=groq_api_key, usage_placeholder=usage_placeholder)


def render_upload_and_results(username: str, groq_api_key: str, usage_placeholder) -> None:
    st.markdown(
        """
        <div class="gv-card">
            <div class="gv-section-title">Upload MCQ Images</div>
            <div class="gv-caption">
                Upload up to 30 images. The app will crop/compress them, extract visible MCQs, and keep token usage per user.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Upload PNG, JPG, or JPEG files",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"uploaded_images_{st.session_state.upload_widget_key}",
    )

    uploaded_count = len(uploaded_files) if uploaded_files else 0
    if uploaded_count > MAX_IMAGES:
        st.error(f"Please upload maximum {MAX_IMAGES} images only.")
    elif uploaded_count:
        st.success(f"{uploaded_count} image(s) ready.")

    action_col_1, action_col_2, _ = st.columns([1, 1.35, 2.2], gap="large")

    with action_col_1:
        extract_clicked = st.button("Extract MCQs", type="primary", use_container_width=True)

    with action_col_2:
        clear_clicked = st.button("Clear Uploaded Images", use_container_width=True)

    if clear_clicked:
        st.session_state.upload_widget_key += 1
        st.session_state.extraction_results = []
        st.rerun()

    if extract_clicked:
        if not uploaded_files:
            st.warning("Please upload at least one image first.")
        elif len(uploaded_files) > MAX_IMAGES:
            st.error(f"Please upload maximum {MAX_IMAGES} images only.")
        else:
            run_extraction(
                uploaded_files=uploaded_files,
                prep_config=PRODUCTION_PREP_CONFIG,
                max_completion_tokens=PRODUCTION_MAX_COMPLETION_TOKENS,
                usage_placeholder=usage_placeholder,
                groq_api_key=groq_api_key,
                username=username,
                refresh_usage_panel=refresh_usage_panel,
            )

    if st.session_state.extraction_results:
        render_results_section()
        render_pdf_download_section()
