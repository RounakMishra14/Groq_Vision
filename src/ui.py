from __future__ import annotations

import time
import sqlite3
import hashlib
from datetime import date

import streamlit as st

from src.auth import init_auth_state, logout, render_login_page
from src.config import (
    DELAY_SECONDS,
    DEFAULT_PDF_NAME,
    MAX_IMAGES,
    MODEL_NAME,
    PDF_THEMES,
)
from src.database import (
    get_groq_key,
    get_user_token_summary,
    init_db,
    save_groq_key,
    save_token_usage,
)
from src.encryption import decrypt, encrypt
from src.file_utils import cleanup_temp_files, get_temp_pdf_path, save_uploaded_file_to_temp
from src.groq_service import extract_mcq_with_groq_result
from src.groq_usage import (
    GroqLimitConfig,
    GroqUsageTracker,
    build_friendly_groq_error_message,
)
from src.image_processor import GroqImagePrepConfig, prepare_image_for_groq
from src.pdf_service import create_pdf


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
GROQ_KEYS_URL = "https://console.groq.com/keys"


# -----------------------------------------------------------------------------
# Local API-key daily usage tracking
# -----------------------------------------------------------------------------

DAILY_USAGE_DB_NAME = "users.db"


def _hash_api_key(api_key: str) -> str:
    """Hash the API key so raw keys are never used as database identifiers."""
    return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()


def init_api_daily_usage_table() -> None:
    """Create a small app-side daily usage table for each Groq API key."""
    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_daily_usage (
            api_key_hash TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            total_tokens INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            PRIMARY KEY (api_key_hash, usage_date)
        )
        """
    )
    conn.commit()
    conn.close()


def add_api_daily_usage(api_key: str, tokens: int) -> None:
    """Add successful request tokens to today's usage for this API key."""
    api_key_hash = _hash_api_key(api_key)
    today = date.today().isoformat()

    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    conn.execute(
        """
        INSERT INTO api_daily_usage (
            api_key_hash,
            usage_date,
            total_tokens,
            total_requests
        )
        VALUES (?, ?, ?, 1)
        ON CONFLICT(api_key_hash, usage_date)
        DO UPDATE SET
            total_tokens = total_tokens + excluded.total_tokens,
            total_requests = total_requests + 1
        """,
        (api_key_hash, today, int(tokens or 0)),
    )
    conn.commit()
    conn.close()


def get_api_daily_usage(api_key: str) -> dict:
    """Return today's app-side usage for this Groq API key."""
    init_api_daily_usage_table()

    api_key_hash = _hash_api_key(api_key)
    today = date.today().isoformat()

    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    row = conn.execute(
        """
        SELECT total_tokens, total_requests
        FROM api_daily_usage
        WHERE api_key_hash=? AND usage_date=?
        """,
        (api_key_hash, today),
    ).fetchone()
    conn.close()

    if not row:
        return {"tokens": 0, "requests": 0}

    return {"tokens": int(row[0] or 0), "requests": int(row[1] or 0)}


# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------


def apply_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 18% 8%, rgba(0, 229, 255, 0.10), transparent 28%),
                radial-gradient(circle at 76% 20%, rgba(0, 160, 190, 0.08), transparent 30%),
                linear-gradient(135deg, #02070b 0%, #03151b 48%, #010507 100%) !important;
            color: #eafcff !important;
        }
        header, footer {visibility: hidden;}
        [data-testid="stSidebar"] {display: none !important;}
        .block-container {
            max-width: 1180px !important;
            padding-top: 1rem !important;
            padding-bottom: 3rem !important;
        }
        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: #eafcff;
        }
        h1, h2, h3 { color: #00e5ff !important; }
        a { color: #00e5ff !important; }

        .gv-hero {
            border: 1px solid rgba(0, 229, 255, 0.42);
            border-radius: 15px;
            background: linear-gradient(180deg, rgba(1, 20, 28, 0.96), rgba(1, 10, 15, 0.90));
            box-shadow: 0 0 42px rgba(0, 229, 255, 0.09);
            padding: 30px 26px 24px 26px;
            margin-bottom: 16px;
        }
        .gv-title {
            color: #00e5ff;
            text-align: center;
            font-size: 44px;
            font-weight: 900;
            line-height: 1;
            margin: 0;
            text-shadow: 0 0 20px rgba(0, 229, 255, 0.55);
        }
        .gv-subtitle {
            text-align: center;
            color: #ffffff;
            font-weight: 800;
            margin-top: 10px;
            font-size: 14px;
        }
        .gv-line {
            height: 1px;
            margin: 22px auto 0 auto;
            width: 92%;
            background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.85), transparent);
        }

        .gv-card {
            border: 1px solid rgba(0, 229, 255, 0.36);
            border-radius: 13px;
            background: rgba(1, 13, 19, 0.80);
            box-shadow: 0 0 28px rgba(0, 229, 255, 0.055);
            padding: 20px;
            margin-bottom: 16px;
        }
        .gv-section-title {
            color: #00e5ff;
            font-size: 24px;
            font-weight: 900;
            margin: 0 0 14px 0;
        }
        .gv-caption {
            color: rgba(234, 252, 255, 0.82);
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 10px;
        }
        .gv-model-pill {
            display: inline-block;
            max-width: 100%;
            color: #0effa4;
            background: rgba(0, 255, 170, 0.09);
            border: 1px solid rgba(0, 255, 170, 0.20);
            border-radius: 6px;
            padding: 2px 7px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 11px;
            overflow-wrap: anywhere;
        }
        .gv-usage-tile {
            border: 1px solid rgba(0, 229, 255, 0.42);
            border-radius: 12px;
            background: rgba(0, 25, 34, 0.78);
            padding: 12px 12px;
            min-height: 88px;
            box-sizing: border-box;
            overflow: hidden;
        }
        .gv-usage-label {
            color: #ffffff;
            font-size: 11px;
            font-weight: 850;
            margin-bottom: 7px;
        }
        .gv-usage-value {
            color: #ffffff;
            font-size: 17px;
            line-height: 1.18;
            font-weight: 900;
            white-space: nowrap;
            letter-spacing: -0.45px;
            font-variant-numeric: tabular-nums;
        }
        .gv-usage-left {
            display: inline-block;
            color: #dffff5;
            background: rgba(0, 155, 100, 0.42);
            border-radius: 999px;
            padding: 3px 7px;
            font-size: 10px;
            font-weight: 800;
            margin-top: 8px;
            white-space: nowrap;
        }
        .gv-average {
            border: 1px solid rgba(0, 229, 255, 0.36);
            border-radius: 9px;
            padding: 10px 13px;
            background: rgba(0, 90, 125, 0.30);
            font-weight: 750;
            margin-top: 10px;
        }
        .gv-profile-box {
            border: 1px solid rgba(0, 229, 255, 0.32);
            border-radius: 13px;
            background: rgba(1, 12, 18, 0.78);
            padding: 16px;
            min-height: 100%;
        }
        .gv-profile-email {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            color: #0effa4;
            background: rgba(0, 255, 170, 0.08);
            border-radius: 6px;
            padding: 3px 6px;
            overflow-wrap: anywhere;
            display: inline-block;
            max-width: 100%;
        }
        .gv-saved-row {
            display: flex;
            gap: 18px;
            margin: 14px 0 8px 0;
        }
        .gv-saved-stat {
            flex: 1;
        }
        .gv-saved-label {
            font-size: 12px;
            font-weight: 800;
            opacity: .86;
            margin-bottom: 3px;
        }
        .gv-saved-number {
            font-size: 26px;
            font-weight: 900;
        }

        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            background-color: rgba(0,0,0,0.22) !important;
            color: #eafcff !important;
            border-color: rgba(0, 229, 255, 0.55) !important;
        }
        .stFileUploader section {
            background: rgba(1, 11, 17, 0.64) !important;
            border: 1px dashed rgba(0, 229, 255, 0.72) !important;
            border-radius: 12px !important;
        }
        .stButton > button, .stDownloadButton > button, [data-testid="stPopoverButton"] {
            border-radius: 9px !important;
            border: 1px solid rgba(0, 229, 255, 0.72) !important;
            background: linear-gradient(135deg, #00d8f5, #0099b6) !important;
            color: #001014 !important;
            font-weight: 850 !important;
            box-shadow: 0 0 18px rgba(0, 229, 255, 0.20) !important;
        }
        [data-testid="stPopoverButton"] {
            min-width: 145px !important;
            width: 100% !important;
        }
        .stProgress > div > div > div > div {
            background-color: #00e5ff !important;
        }
        .stAlert {
            border-radius: 10px !important;
        }
        .stExpander {
            border: 1px solid rgba(0, 229, 255, 0.26) !important;
            border-radius: 10px !important;
            background: rgba(1, 13, 19, 0.62) !important;
        }
        @media (max-width: 900px) {
            .gv-title {font-size: 34px;}
            .gv-usage-value {font-size: 16px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero_header() -> None:
    st.markdown(
        """
        <div class="gv-hero">
            <div class="gv-title">Groq Vision</div>
            <div class="gv-subtitle">Batch MCQ Extractor</div>
            <div class="gv-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# API key flow
# -----------------------------------------------------------------------------


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
            <div class="gv-section-title">🔑 Groq API Key Required</div>
            <div class="gv-caption">
                Generate your Groq API key once, paste it below, and this app will remember it for your account.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button("🚀 Get Free Groq API Key", GROQ_KEYS_URL, use_container_width=True)

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
        <div class="gv-average">🔒 Your API key is encrypted before saving and is only used for extraction requests.</div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Main app layout
# -----------------------------------------------------------------------------


def render_main_app(username: str, groq_api_key: str) -> None:
    # Top row: header on the left, profile menu on the top-right.
    header_col, profile_col = st.columns([5.4, 1.0], gap="large", vertical_alignment="top")

    with header_col:
        render_hero_header()

    with profile_col:
        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
        render_profile_menu(username)

    # Session Usage should be full-width below the header, not inside a side column.
    usage_placeholder = st.empty()
    refresh_usage_panel(usage_placeholder, groq_api_key)

    st.markdown("<br/>", unsafe_allow_html=True)
    render_upload_and_results(username=username, groq_api_key=groq_api_key, usage_placeholder=usage_placeholder)


def render_profile_menu(username: str) -> None:
    if hasattr(st, "popover"):
        with st.popover("👤 Profile ▾", use_container_width=True):
            render_profile_actions(username)
    else:
        with st.expander("👤 Profile Actions", expanded=False):
            render_profile_actions(username)

def render_profile_actions(username: str) -> None:
    summary = get_user_token_summary(username)

    st.caption("Signed in as")
    st.code(username, language=None)

    st.success("Groq API key saved ✅")

    st.markdown("**Lifetime Usage**")
    usage_a, usage_b = st.columns(2)
    with usage_a:
        st.metric("Requests", f"{summary['total_requests']:,}")
    with usage_b:
        st.metric("Tokens", f"{summary['total_tokens']:,}")

    st.caption(
        f"Input: {summary['prompt_tokens']:,} | "
        f"Output: {summary['completion_tokens']:,} | "
        f"Errors: {summary['failed_requests']:,}"
    )

    st.divider()

    with st.form("change_groq_key_form"):
        new_key = st.text_input("Change Groq API Key", type="password", placeholder="Paste new gsk_... key")
        save_clicked = st.form_submit_button("Save New API Key", use_container_width=True)

    if save_clicked:
        if not new_key.strip():
            st.error("Please enter a new Groq API key.")
        else:
            save_groq_key(username, encrypt(new_key.strip()))
            st.session_state.groq_api_key = new_key.strip()
            st.success("Groq API key updated.")
            st.rerun()

    if st.button("Logout", use_container_width=True):
        logout()


def render_upload_and_results(username: str, groq_api_key: str, usage_placeholder) -> None:
    st.markdown(
        """
        <div class="gv-card">
            <div class="gv-section-title">📤 Upload MCQ Images</div>
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

    action_col_1, action_col_2, action_col_3 = st.columns([1, 1.35, 2.2], gap="large")

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
            )

    if st.session_state.extraction_results:
        render_results_section()
        render_pdf_download_section()


# -----------------------------------------------------------------------------
# Extraction logic
# -----------------------------------------------------------------------------


def run_extraction(
    uploaded_files,
    prep_config: GroqImagePrepConfig,
    max_completion_tokens: int,
    usage_placeholder,
    groq_api_key: str,
    username: str,
) -> None:
    results = []
    temp_paths = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(f"Preparing image {idx}/{len(uploaded_files)}: {uploaded_file.name}")

            image_path = save_uploaded_file_to_temp(uploaded_file)
            temp_paths.append(image_path)

            try:
                prep_result = prepare_image_for_groq(image_path, prep_config)
            except Exception as prep_error:
                st.warning(f"Image preparation failed for `{uploaded_file.name}`. This image was skipped.")
                with st.expander("Show image preparation error"):
                    st.exception(prep_error)
                continue

            processed_image_path = prep_result.output_path
            temp_paths.append(processed_image_path)

            status.write(f"Extracting MCQs from image {idx}/{len(uploaded_files)}: {uploaded_file.name}")

            try:
                groq_result = extract_mcq_with_groq_result(
                    image_path=processed_image_path,
                    image_number=idx,
                    groq_api_key=groq_api_key,
                    max_completion_tokens=max_completion_tokens,
                )
            except Exception as groq_error:
                raw_error_text = str(groq_error)

                st.session_state.groq_usage_tracker.add_error(
                    image_number=idx,
                    file_name=uploaded_file.name,
                    error_message=raw_error_text,
                    model=MODEL_NAME,
                )

                save_token_usage(
                    username=username,
                    image_number=idx,
                    file_name=uploaded_file.name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    duration_seconds=0,
                    model=MODEL_NAME,
                    status="error",
                    error_message=raw_error_text,
                )

                st.session_state.extraction_results = results
                refresh_usage_panel(usage_placeholder, groq_api_key)

                clean_message = build_friendly_groq_error_message(raw_error_text)
                st.error(clean_message)
                st.info("Extraction stopped safely. Already extracted MCQs are kept below for PDF download.")
                with st.expander("Show technical error"):
                    st.exception(groq_error)
                break

            st.session_state.groq_usage_tracker.add_success(
                image_number=idx,
                file_name=uploaded_file.name,
                prompt_tokens=groq_result.prompt_tokens,
                completion_tokens=groq_result.completion_tokens,
                total_tokens=groq_result.total_tokens,
                duration_seconds=groq_result.duration_seconds,
                model=groq_result.model,
            )

            save_token_usage(
                username=username,
                image_number=idx,
                file_name=uploaded_file.name,
                prompt_tokens=groq_result.prompt_tokens,
                completion_tokens=groq_result.completion_tokens,
                total_tokens=groq_result.total_tokens,
                duration_seconds=groq_result.duration_seconds,
                model=groq_result.model,
                status="success",
            )

            add_api_daily_usage(
                groq_api_key,
                groq_result.total_tokens,
            )

            results.append(
                {
                    "image_number": idx,
                    "file_name": uploaded_file.name,
                    "output": groq_result.output,
                    "processing_meta": prep_result.meta,
                    "usage": {
                        "prompt_tokens": groq_result.prompt_tokens,
                        "completion_tokens": groq_result.completion_tokens,
                        "total_tokens": groq_result.total_tokens,
                        "duration_seconds": round(groq_result.duration_seconds, 2),
                        "model": groq_result.model,
                    },
                }
            )

            st.session_state.extraction_results = results
            progress.progress(idx / len(uploaded_files))
            refresh_usage_panel(usage_placeholder, groq_api_key)

            if idx < len(uploaded_files):
                time.sleep(DELAY_SECONDS)

        if results:
            st.success("Extraction completed or stopped with partial results available.")
        else:
            st.warning("No MCQs were extracted in this run.")

    except Exception as app_error:
        if results:
            st.session_state.extraction_results = results
            st.warning("Stopped early, but partial results are available for PDF download.")
        st.error("Something went wrong during extraction. The app handled it safely without losing completed results.")
        with st.expander("Show technical error"):
            st.exception(app_error)

    finally:
        cleanup_temp_files(temp_paths)


# -----------------------------------------------------------------------------
# Usage + Results
# -----------------------------------------------------------------------------


def refresh_usage_panel(usage_placeholder, groq_api_key: str) -> None:
    with usage_placeholder.container():
        render_groq_usage_panel(groq_api_key)


def _format_number(value: int) -> str:
    return f"{int(value or 0):,}"


def _usage_tile(label: str, used: int, limit: int, remaining: int) -> str:
    return f"""
    <div class="gv-usage-tile">
        <div class="gv-usage-label">{label}</div>
        <div class="gv-usage-value">{_format_number(used)} / {_format_number(limit)}</div>
        <div class="gv-usage-left">↑ {_format_number(remaining)} left</div>
    </div>
    """


def render_groq_usage_panel(groq_api_key: str) -> None:
    tracker: GroqUsageTracker = st.session_state.groq_usage_tracker
    limits = tracker.limits
    daily_usage = get_api_daily_usage(groq_api_key)

    st.markdown(
        f"""
        <div class="gv-card">
            <div class="gv-section-title">⚡ Session Usage</div>
            <div class="gv-caption">Live usage for this current browser session.</div>
            <div class="gv-caption"><b>Model:</b> <span class="gv-model-pill">{limits.model_name}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    daily_tokens = daily_usage["tokens"]
    daily_remaining_tokens = max(0, limits.tpd_limit - daily_tokens)

    usage_items = [
        ("Requests / min", tracker.requests_last_minute, limits.rpm_limit, tracker.remaining_session_rpm),
        ("Tokens / min", tracker.tokens_last_minute, limits.tpm_limit, tracker.remaining_session_tpm),
        ("Session requests", tracker.total_requests, limits.rpd_limit, tracker.remaining_session_rpd),
        ("Tokens / day", daily_tokens, limits.tpd_limit, daily_remaining_tokens),
    ]

    cols = st.columns(4, gap="small")
    for col, (label, used, limit, remaining) in zip(cols, usage_items):
        with col:
            st.markdown(_usage_tile(label, used, limit, remaining), unsafe_allow_html=True)

    if tracker.total_requests:
        avg_tokens = round(tracker.total_tokens / tracker.total_requests)
        st.markdown(
            f'<div class="gv-average">Average tokens per successful image: {_format_number(avg_tokens)}</div>',
            unsafe_allow_html=True,
        )


    if tracker.failed_requests:
        st.warning(f"Failed Groq requests in this session: **{tracker.failed_requests}**")

    if tracker.last_limit_error:
        err = tracker.last_limit_error
        st.error(
            f"Last limit hit: **{err.limit_type}** | Limit: **{err.limit:,}** | "
            f"Used: **{err.used:,}** | Requested: **{err.requested:,}** | "
            f"Remaining before request: **{err.remaining_before_request:,}**"
        )
        if err.retry_after_text:
            st.warning(f"Groq suggested retry after: **{err.retry_after_text}**")


def render_results_section() -> None:
    st.markdown(
        """
        <div class="gv-card">
            <div class="gv-section-title">✅ Extracted Results</div>
            <div class="gv-caption">Preview of extracted MCQs. You can download everything as a formatted PDF below.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for item in st.session_state.extraction_results:
        with st.expander(f"Image {item['image_number']}: {item['file_name']}", expanded=True):
            st.markdown(item["output"].replace("\n", "  \n"))
            usage = item.get("usage", {})
            if usage:
                st.caption(
                    f"Tokens: {usage.get('total_tokens', 0):,} | "
                    f"Input: {usage.get('prompt_tokens', 0):,} | "
                    f"Output: {usage.get('completion_tokens', 0):,} | "
                    f"Time: {usage.get('duration_seconds', 0)}s"
                )


def render_pdf_download_section() -> None:
    st.markdown(
        """
        <div class="gv-card">
            <div class="gv-section-title">📄 Generate PDF</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_name, col_theme = st.columns([1.2, 0.8], gap="large")

    with col_name:
        pdf_name = st.text_input("File Name", value=DEFAULT_PDF_NAME)

    with col_theme:
        pdf_theme = st.selectbox("PDF Theme", PDF_THEMES)

    pdf_path = get_temp_pdf_path(pdf_name)
    create_pdf(st.session_state.extraction_results, pdf_path, pdf_name, pdf_theme)

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="Generate & Download PDF",
            data=f.read(),
            file_name=f"{pdf_name}.pdf",
            mime="application/pdf",
            key=f"download_pdf_{pdf_name}_{pdf_theme}",
            use_container_width=True,
        )
