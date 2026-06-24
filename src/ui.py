from __future__ import annotations

import time

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


def apply_dark_app_css() -> None:
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
header, footer { visibility: hidden; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(1, 19, 26, 0.98), rgba(0, 7, 11, 0.98)) !important;
    border-right: 1px solid rgba(0, 229, 255, 0.22) !important;
}
[data-testid="stSidebar"] * { color: #eafcff !important; }
h1 {
    color: #00e5ff !important;
    text-align: center !important;
    font-size: 4rem !important;
    font-weight: 900 !important;
    line-height: 1.05 !important;
    margin-bottom: 0 !important;
    text-shadow: 0 0 22px rgba(0, 229, 255, 0.45);
}
h2, h3, h4 { color: #00e5ff !important; }
p, li, label, span, div { color: #eafcff; }
a { color: #00e5ff !important; font-weight: 800 !important; text-decoration: none !important; }
.small-center {
    text-align: center;
    color: rgba(234, 252, 255, 0.78) !important;
    font-weight: 700;
}
.hero-shell, div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(0, 229, 255, 0.35) !important;
    border-radius: 18px !important;
    background: rgba(1, 16, 23, 0.78) !important;
    box-shadow: 0 0 35px rgba(0, 229, 255, 0.08) !important;
}
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
    background-color: rgba(0, 0, 0, 0.25) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.45) !important;
    border-radius: 10px !important;
}
.stTextInput input:focus {
    border-color: #00e5ff !important;
    box-shadow: 0 0 0 1px #00e5ff !important;
}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    width: 100%;
    border-radius: 10px !important;
    border: 1px solid rgba(0, 229, 255, 0.75) !important;
    background: linear-gradient(135deg, #00e5ff, #009ab8) !important;
    color: #001014 !important;
    font-weight: 900 !important;
    box-shadow: 0 0 18px rgba(0, 229, 255, 0.30);
}
.stFileUploader {
    border: 1px dashed rgba(0, 229, 255, 0.45) !important;
    border-radius: 16px !important;
    padding: 18px !important;
    background: rgba(0, 229, 255, 0.035) !important;
}
.stMetric {
    background: rgba(0, 229, 255, 0.035) !important;
    border: 1px solid rgba(0, 229, 255, 0.22) !important;
    border-radius: 14px !important;
    padding: 12px !important;
}
.stMetric [data-testid="stMetricValue"] { color: #00e5ff !important; }
.stAlert, .stExpander {
    background: rgba(0, 229, 255, 0.06) !important;
    border: 1px solid rgba(0, 229, 255, 0.28) !important;
    color: #eafcff !important;
    border-radius: 14px !important;
}
hr { border-color: rgba(0, 229, 255, 0.22) !important; }
.progress-bar, [data-testid="stProgress"] > div > div > div > div {
    background-color: #00e5ff !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_dark_header(subtitle: str = "Batch MCQ Extractor") -> None:
    with st.container(border=True):
        st.title("Groq Vision")
        st.markdown(f"<p class='small-center'>{subtitle}</p>", unsafe_allow_html=True)
        st.markdown("---")


def initialize_session_state() -> None:
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = []

    if "groq_usage_tracker" not in st.session_state:
        st.session_state.groq_usage_tracker = GroqUsageTracker(limits=DEFAULT_GROQ_LIMITS)

    if "upload_widget_key" not in st.session_state:
        st.session_state.upload_widget_key = 0

    if "groq_api_key" not in st.session_state:
        st.session_state.groq_api_key = None


def run_app() -> None:
    st.set_page_config(page_title="Groq Vision", layout="wide")

    init_db()
    init_auth_state()
    initialize_session_state()

    if not st.session_state.logged_in:
        render_login_page()
        st.stop()

    username = st.session_state.username
    groq_api_key = load_or_request_groq_key(username)
    if not groq_api_key:
        st.stop()

    render_main_app(username=username, groq_api_key=groq_api_key)


def load_or_request_groq_key(username: str) -> str | None:
    saved_key = get_groq_key(username)

    st.sidebar.title("Groq Vision")
    st.sidebar.success(f"Logged in as {username}")

    if st.sidebar.button("Logout"):
        logout()

    if saved_key:
        try:
            groq_api_key = decrypt(saved_key)
            st.session_state.groq_api_key = groq_api_key
            st.sidebar.info("Groq API key saved ✅")
            render_persistent_usage_sidebar(username)
            return groq_api_key
        except Exception:
            st.sidebar.error("Saved Groq key could not be decrypted. Please save it again.")

    apply_dark_app_css()
    render_dark_header("Save your Groq API Key")

    left, right = st.columns([1, 1.2], gap="large")
    with left:
        with st.container(border=True):
            st.subheader("🔑 API Key Required")
            st.write("Paste your Groq API key once. It will be encrypted and remembered for your account.")
            st.markdown("[Open Groq API Keys Page](https://console.groq.com/keys)")
            st.info("Your key is stored encrypted and is only used to call Groq for your own extractions.")
    with right:
        with st.container(border=True):
            with st.form("save_groq_key_form"):
                user_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
                submitted = st.form_submit_button("Save Groq Key")

                if submitted:
                    if not user_key.strip():
                        st.error("Please enter your Groq API key.")
                    else:
                        save_groq_key(username, encrypt(user_key.strip()))
                        st.success("Groq key saved. Loading app...")
                        st.rerun()

    st.stop()


def render_main_app(username: str, groq_api_key: str) -> None:
    apply_dark_app_css()
    render_dark_header("Batch MCQ Extractor")

    render_persistent_usage_sidebar(username)

    top_left, top_right = st.columns([1.25, 1], gap="large")

    with top_left:
        with st.container(border=True):
            st.subheader("📤 Upload MCQ Images")
            st.write(f"Upload up to **{MAX_IMAGES}** images. The app will crop/compress them, extract visible MCQs, and keep token usage per user.")
            uploaded_files = st.file_uploader(
                "Upload PNG, JPG, or JPEG files",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=f"uploaded_images_{st.session_state.upload_widget_key}",
            )
            if uploaded_files:
                st.success(f"{len(uploaded_files)} image(s) ready.")

            col_extract, col_clear = st.columns([1, 1])
            with col_extract:
                extract_clicked = st.button("Extract MCQs", type="primary")
            with col_clear:
                clear_clicked = st.button("Clear Uploaded Images")

    with top_right:
        usage_placeholder = st.empty()
        refresh_usage_panel(usage_placeholder)

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


def render_persistent_usage_sidebar(username: str) -> None:
    summary = get_user_token_summary(username)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Saved Usage")
    st.sidebar.metric("Total Requests", summary["total_requests"])
    st.sidebar.metric("Total Tokens", summary["total_tokens"])
    st.sidebar.caption(
        f"Input: {summary['prompt_tokens']} | Output: {summary['completion_tokens']} | Errors: {summary['failed_requests']}"
    )


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
            except Exception:
                st.warning(f"Image preparation failed for `{uploaded_file.name}`. This image was skipped.")
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
                refresh_usage_panel(usage_placeholder)

                clean_message = build_friendly_groq_error_message(raw_error_text)
                st.error(clean_message)
                st.info("Extraction stopped safely. Already extracted MCQs are kept below for PDF download.")
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
            refresh_usage_panel(usage_placeholder)

            if idx < len(uploaded_files):
                time.sleep(DELAY_SECONDS)

        if results:
            st.success("Extraction completed or stopped with partial results available.")
        else:
            st.warning("No MCQs were extracted in this run.")

    except Exception:
        if results:
            st.session_state.extraction_results = results
            st.warning("Stopped early, but partial results are available for PDF download.")
        st.error("Something went wrong during extraction. The app handled it safely without losing completed results.")

    finally:
        cleanup_temp_files(temp_paths)


def refresh_usage_panel(usage_placeholder) -> None:
    with usage_placeholder.container():
        render_groq_usage_panel()


def render_groq_usage_panel() -> None:
    tracker: GroqUsageTracker = st.session_state.groq_usage_tracker
    limits = tracker.limits

    with st.container(border=True):
        st.subheader("⚡ Session Usage")
        st.caption("Live usage for this current browser session.")
        st.write(f"**Model:** `{limits.model_name}`")

        c1, c2 = st.columns(2)
        c1.metric("Requests / min", f"{tracker.requests_last_minute}/{limits.rpm_limit}", f"{tracker.remaining_session_rpm} left")
        c2.metric("Tokens / min", f"{tracker.tokens_last_minute}/{limits.tpm_limit}", f"{tracker.remaining_session_tpm} left")

        c3, c4 = st.columns(2)
        c3.metric("Session requests", f"{tracker.total_requests}/{limits.rpd_limit}", f"{tracker.remaining_session_rpd} left")
        c4.metric("Session tokens", f"{tracker.total_tokens}/{limits.tpd_limit}", f"{tracker.remaining_session_tpd} left")

        if tracker.total_requests:
            avg_tokens = round(tracker.total_tokens / tracker.total_requests)
            st.info(f"Average tokens per successful image: **{avg_tokens}**")

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
    with st.container(border=True):
        st.subheader("✅ Extracted Results")
        st.caption("Preview of extracted MCQs. You can download everything as a formatted PDF below.")
        for item in st.session_state.extraction_results:
            with st.expander(f"Image {item['image_number']}: {item['file_name']}", expanded=False):
                st.text(item.get("output", ""))
                usage = item.get("usage") or {}
                if usage:
                    st.caption(
                        f"Tokens: {usage.get('total_tokens', 0)} | "
                        f"Input: {usage.get('prompt_tokens', 0)} | "
                        f"Output: {usage.get('completion_tokens', 0)} | "
                        f"Time: {usage.get('duration_seconds', 0)}s"
                    )


def render_pdf_download_section() -> None:
    with st.container(border=True):
        st.subheader("📄 Export PDF")
        pdf_name = st.text_input("File Name", value=DEFAULT_PDF_NAME)
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
            )
