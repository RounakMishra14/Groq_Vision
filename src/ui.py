import time

import streamlit as st

from src.config import (
    MAX_IMAGES,
    DELAY_SECONDS,
    DEFAULT_PDF_NAME,
    PDF_THEMES,
    MODEL_NAME,
)
from src.groq_service import extract_mcq_with_groq_result
from src.groq_usage import (
    GroqLimitConfig,
    GroqUsageTracker,
    build_friendly_groq_error_message,
)
from src.pdf_service import create_pdf
from src.file_utils import (
    save_uploaded_file_to_temp,
    cleanup_temp_files,
    get_temp_pdf_path,
)
from src.image_processor import prepare_image_for_groq, GroqImagePrepConfig


# Groq free/on-demand limits for meta-llama/llama-4-scout-17b-16e-instruct.
# Keep these editable because Groq can change plan/model limits.
DEFAULT_GROQ_LIMITS = GroqLimitConfig(
    model_name=MODEL_NAME,
    rpm_limit=30,
    rpd_limit=1000,
    tpm_limit=30000,
    tpd_limit=500000,
)


# --------------------------------------------------
# PRODUCTION IMAGE SETTINGS
# --------------------------------------------------
# These values are intentionally hardcoded for the clean production UI.
# Your previous debug sliders/checkboxes are removed from the visible app.
# Current stable pipeline:
#   original image -> v7 bright screen crop -> width 900 -> JPEG quality 50 -> Groq
PRODUCTION_PREP_CONFIG = GroqImagePrepConfig(
    crop_enabled=True,
    compression_enabled=True,
    brightness_threshold=170,
    max_saturation=110,
    safety_expand_ratio=0.03,
    target_width=900,
    jpeg_quality=50,
    debug=False,
)

# Keep output token budget fixed in production UI.
PRODUCTION_MAX_COMPLETION_TOKENS = 2048


# --------------------------------------------------
# HIDDEN DEBUG SETTINGS - NOT SHOWN IN UI
# --------------------------------------------------
# If you need debugging again later, you can temporarily expose these controls:
# - crop enabled / disabled
# - compression enabled / disabled
# - brightness threshold
# - saturation threshold
# - safety expand ratio
# - target width
# - JPEG quality
# - max completion tokens
# They are deliberately commented out from the visible UI to keep the app clean.


def initialize_session_state():
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = []

    if "groq_usage_tracker" not in st.session_state:
        st.session_state.groq_usage_tracker = GroqUsageTracker(
            limits=DEFAULT_GROQ_LIMITS
        )

    # Used to clear only the upload widget without resetting token counters.
    if "upload_widget_key" not in st.session_state:
        st.session_state.upload_widget_key = 0


def run_app():
    st.set_page_config(
        page_title="Batch MCQ Extractor",
        layout="wide"
    )

    initialize_session_state()

    st.title("Batch MCQ Extractor")
    st.write("Groq Vision")

    # Usage panel is intentionally placed at the top of the main page.
    # It is refreshed during extraction after every successful or failed Groq call.
    usage_placeholder = st.empty()
    refresh_usage_panel(usage_placeholder)

    uploaded_files = st.file_uploader(
        "Upload up to 30 MCQ images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"uploaded_images_{st.session_state.upload_widget_key}",
    )

    col_extract, col_clear = st.columns([1, 1])

    with col_extract:
        extract_clicked = st.button("Extract MCQs", type="primary")

    with col_clear:
        clear_clicked = st.button("Clear Uploaded Images")

    if clear_clicked:
        # Only clears attached/uploaded images.
        # It does NOT reset Groq usage counters or previous extraction results.
        st.session_state.upload_widget_key += 1
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
            )

    if st.session_state.extraction_results:
        render_pdf_download_section()


# --------------------------------------------------
# EXTRACTION PIPELINE
# --------------------------------------------------

def run_extraction(
    uploaded_files,
    prep_config: GroqImagePrepConfig,
    max_completion_tokens: int,
    usage_placeholder,
):
    results = []
    temp_paths = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(
                f"Preparing image {idx}/{len(uploaded_files)}: {uploaded_file.name}"
            )

            image_path = save_uploaded_file_to_temp(uploaded_file)
            temp_paths.append(image_path)

            try:
                prep_result = prepare_image_for_groq(
                    image_path,
                    prep_config,
                )
            except Exception as prep_error:
                clean_message = (
                    f"Image preparation failed for `{uploaded_file.name}`. "
                    "This image was skipped. Partial results are kept if available."
                )
                st.warning(clean_message)

                # Debug trace intentionally hidden from production UI.
                # To debug locally, temporarily uncomment this line:
                # st.exception(prep_error)

                continue

            processed_image_path = prep_result.output_path
            temp_paths.append(processed_image_path)

            status.write(
                f"Extracting MCQs from image {idx}/{len(uploaded_files)}: {uploaded_file.name}"
            )

            try:
                groq_result = extract_mcq_with_groq_result(
                    image_path=processed_image_path,
                    image_number=idx,
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

                st.session_state.extraction_results = results
                refresh_usage_panel(usage_placeholder)

                clean_message = build_friendly_groq_error_message(raw_error_text)
                st.error(clean_message)
                st.info("Extraction stopped safely. Any already extracted MCQs are kept below for PDF download.")

                # Raw traceback intentionally hidden from production UI.
                # To debug locally, temporarily uncomment this line:
                # st.exception(groq_error)

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

            # Real-time usage update after each completed Groq call.
            refresh_usage_panel(usage_placeholder)

            if idx < len(uploaded_files):
                time.sleep(DELAY_SECONDS)

        if results:
            st.success("Extraction completed or stopped with partial results available.")
        else:
            st.warning("No MCQs were extracted in this run.")

    except Exception as e:
        # This catches unexpected app-side failures without showing a traceback.
        if results:
            st.session_state.extraction_results = results
            st.warning("Stopped early, but partial results are available for PDF download.")

        st.error("Something went wrong during extraction. The app handled it safely without losing completed results.")

        # Raw traceback intentionally hidden from production UI.
        # To debug locally, temporarily uncomment this line:
        # st.exception(e)

    finally:
        cleanup_temp_files(temp_paths)


# --------------------------------------------------
# GROQ USAGE PANEL
# --------------------------------------------------

def refresh_usage_panel(usage_placeholder):
    with usage_placeholder.container():
        render_groq_usage_panel()


def render_groq_usage_panel():
    tracker: GroqUsageTracker = st.session_state.groq_usage_tracker
    limits = tracker.limits

    with st.expander("Groq Usage & Limits", expanded=True):
        st.caption(
            "Session usage is tracked live inside this app. Groq org-level remaining quota "
            "is only known exactly when Groq returns a rate-limit error."
        )

        st.write(f"**Model:** `{limits.model_name}`")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Requests / min",
            f"{tracker.requests_last_minute}/{limits.rpm_limit}",
            f"{tracker.remaining_session_rpm} left",
        )
        c2.metric(
            "Tokens / min",
            f"{tracker.tokens_last_minute}/{limits.tpm_limit}",
            f"{tracker.remaining_session_tpm} left",
        )
        c3.metric(
            "Session requests",
            f"{tracker.total_requests}/{limits.rpd_limit}",
            f"{tracker.remaining_session_rpd} left",
        )
        c4.metric(
            "Session tokens",
            f"{tracker.total_tokens}/{limits.tpd_limit}",
            f"{tracker.remaining_session_tpd} left",
        )

        if tracker.total_requests:
            avg_tokens = round(tracker.total_tokens / tracker.total_requests)
            st.info(f"Average tokens per successful image: **{avg_tokens}**")

        if tracker.failed_requests:
            st.warning(f"Failed Groq requests in this session: **{tracker.failed_requests}**")

        if tracker.last_limit_error:
            err = tracker.last_limit_error
            st.error(
                f"Last limit hit: **{err.limit_type}** | "
                f"Limit: **{err.limit:,}** | "
                f"Used: **{err.used:,}** | "
                f"Requested: **{err.requested:,}** | "
                f"Remaining before request: **{err.remaining_before_request:,}**"
            )
            if err.retry_after_text:
                st.warning(f"Groq suggested retry after: **{err.retry_after_text}**")

        # Usage CSV/table download was intentionally removed from the live panel.
        # It caused duplicate Streamlit element IDs during real-time refresh.
        # If needed later, add it in a separate non-refreshing section with a unique key.

        # Reset button intentionally hidden from production UI because user asked for a clean UI.
        # To enable later, uncomment:
        # if st.button("Reset usage counters", key="reset_usage_main"):
        #     st.session_state.groq_usage_tracker = GroqUsageTracker(limits=DEFAULT_GROQ_LIMITS)
        #     st.rerun()


# --------------------------------------------------
# PDF DOWNLOAD
# --------------------------------------------------

def render_pdf_download_section():
    pdf_name = st.text_input(
        "File Name",
        value=DEFAULT_PDF_NAME,
    )

    pdf_theme = st.selectbox(
        "PDF Theme",
        PDF_THEMES,
    )

    pdf_path = get_temp_pdf_path(pdf_name)

    create_pdf(
        st.session_state.extraction_results,
        pdf_path,
        pdf_name,
        pdf_theme,
    )

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="Generate & Download PDF",
            data=f.read(),
            file_name=f"{pdf_name}.pdf",
            mime="application/pdf",
            key=f"download_pdf_{pdf_name}_{pdf_theme}",
        )


# --------------------------------------------------
# HIDDEN / REMOVED DEBUG UI
# --------------------------------------------------
# The old processing summary was removed from production UI.
# Keeping this commented reference for future debugging only.
#
# def render_results_preview():
#     with st.expander("Processing summary", expanded=False):
#         for item in st.session_state.extraction_results:
#             meta = item.get("processing_meta", {})
#             usage = item.get("usage", {})
#             st.write(
#                 f"Image {item['image_number']} - {item['file_name']} | "
#                 f"{meta.get('original_dimensions')} / {meta.get('original_size_kb')} KB "
#                 f"→ {meta.get('final_dimensions')} / {meta.get('final_size_kb')} KB | "
#                 f"Tokens: {usage.get('total_tokens', 'N/A')} "
#                 f"(input {usage.get('prompt_tokens', 'N/A')}, output {usage.get('completion_tokens', 'N/A')})"
#             )
