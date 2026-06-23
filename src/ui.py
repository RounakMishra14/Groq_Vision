import time

import pandas as pd
import streamlit as st

from src.config import (
    MAX_IMAGES,
    DELAY_SECONDS,
    DEFAULT_PDF_NAME,
    PDF_THEMES,
    MODEL_NAME,
)
from src.groq_service import extract_mcq_with_groq_result
from src.groq_usage import GroqLimitConfig, GroqUsageTracker
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


def initialize_session_state():
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = []

    if "groq_usage_tracker" not in st.session_state:
        st.session_state.groq_usage_tracker = GroqUsageTracker(
            limits=DEFAULT_GROQ_LIMITS
        )


def run_app():
    st.set_page_config(
        page_title="Batch MCQ Extractor",
        layout="wide"
    )

    initialize_session_state()

    st.title("Batch MCQ Extractor")
    st.write("Groq Vision")

    with st.sidebar:
        st.header("Image Processing")

        enable_crop = st.checkbox(
            "Enable v7 screen crop",
            value=True,
            help="Crops the bright laptop screen before sending to Groq."
        )

        enable_compression = st.checkbox(
            "Enable safe compression",
            value=True,
            help="Resizes after crop to reduce Groq vision tokens."
        )

        target_width = st.number_input(
            "Target width",
            min_value=600,
            max_value=1600,
            value=900,
            step=50,
            help="Safe default: 900. Use 1000 if text becomes unclear."
        )

        jpeg_quality = st.slider(
            "JPEG quality",
            min_value=30,
            max_value=95,
            value=50,
            step=5,
            help="Safe default: 50."
        )

        max_completion_tokens = st.number_input(
            "Max completion tokens",
            min_value=512,
            max_value=4096,
            value=2048,
            step=256,
            help="Lower value reduces requested output token budget. Use 2048 for MCQ extraction."
        )

        with st.expander("Advanced crop settings"):
            brightness_threshold = st.slider(
                "Brightness threshold",
                min_value=130,
                max_value=230,
                value=170,
                step=5,
            )
            max_saturation = st.slider(
                "Max saturation",
                min_value=40,
                max_value=180,
                value=110,
                step=5,
            )
            safety_expand_ratio = st.slider(
                "Safety expand ratio",
                min_value=0.00,
                max_value=0.08,
                value=0.03,
                step=0.01,
            )

        render_groq_usage_panel(location="sidebar")

    uploaded_files = st.file_uploader(
        "Upload up to 30 MCQ images",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        if len(uploaded_files) > MAX_IMAGES:
            st.error(f"Please upload maximum {MAX_IMAGES} images only.")
            return

        st.success(f"{len(uploaded_files)} image(s) uploaded.")

        if st.button("Extract MCQs"):
            prep_config = GroqImagePrepConfig(
                crop_enabled=enable_crop,
                compression_enabled=enable_compression,
                brightness_threshold=brightness_threshold,
                max_saturation=max_saturation,
                safety_expand_ratio=safety_expand_ratio,
                target_width=int(target_width),
                jpeg_quality=int(jpeg_quality),
            )
            run_extraction(
                uploaded_files=uploaded_files,
                prep_config=prep_config,
                max_completion_tokens=int(max_completion_tokens),
            )

    render_groq_usage_panel(location="main")

    if st.session_state.extraction_results:
        render_results_preview()
        render_pdf_download_section()


def run_extraction(
    uploaded_files,
    prep_config: GroqImagePrepConfig,
    max_completion_tokens: int,
):
    results = []
    temp_paths = []

    # Preserve old partial results until a new successful item arrives.
    if st.session_state.extraction_results:
        results = list(st.session_state.extraction_results)

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, uploaded_file in enumerate(uploaded_files, start=1):
            status.write(
                f"Preparing image {idx}/{len(uploaded_files)}: {uploaded_file.name}"
            )

            image_path = save_uploaded_file_to_temp(uploaded_file)
            temp_paths.append(image_path)

            prep_result = prepare_image_for_groq(
                image_path,
                prep_config,
            )
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
                error_text = str(groq_error)
                st.session_state.groq_usage_tracker.add_error(
                    image_number=idx,
                    file_name=uploaded_file.name,
                    error_message=error_text,
                    model=MODEL_NAME,
                )
                st.session_state.extraction_results = results
                st.error("Groq request failed. Partial results are kept below if available.")
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

            if idx < len(uploaded_files):
                time.sleep(DELAY_SECONDS)

        if results:
            st.success("Extraction completed or stopped with partial results available.")

    except Exception as e:
        if results:
            st.session_state.extraction_results = results
            st.warning("Stopped early, but partial results are available below.")

        st.error("Error occurred during extraction.")
        st.exception(e)

    finally:
        cleanup_temp_files(temp_paths)


def render_groq_usage_panel(location: str = "main"):
    tracker: GroqUsageTracker = st.session_state.groq_usage_tracker
    limits = tracker.limits

    title = "Groq Usage & Limits"

    container = st.sidebar if location == "sidebar" else st

    if location == "sidebar":
        with container.expander(title, expanded=True):
            _render_usage_metrics(tracker, limits, compact=True)
    else:
        with container.expander(title, expanded=False):
            _render_usage_metrics(tracker, limits, compact=False)


def _render_usage_metrics(
    tracker: GroqUsageTracker,
    limits: GroqLimitConfig,
    compact: bool,
):
    st.caption(
        "This shows usage tracked in this app session. Groq org-level remaining quota "
        "is only visible here after Groq returns a rate-limit error."
    )

    st.write(f"**Model:** `{limits.model_name}`")

    c1, c2 = st.columns(2)
    c1.metric(
        "Requests / min",
        f"{tracker.requests_last_minute}/{limits.rpm_limit}",
        f"{tracker.remaining_session_rpm} left"
    )
    c2.metric(
        "Tokens / min",
        f"{tracker.tokens_last_minute}/{limits.tpm_limit}",
        f"{tracker.remaining_session_tpm} left"
    )

    c3, c4 = st.columns(2)
    c3.metric(
        "Session requests",
        f"{tracker.total_requests}/{limits.rpd_limit}",
        f"{tracker.remaining_session_rpd} left vs daily limit"
    )
    c4.metric(
        "Session tokens",
        f"{tracker.total_tokens}/{limits.tpd_limit}",
        f"{tracker.remaining_session_tpd} left vs daily limit"
    )

    if tracker.total_requests:
        avg_tokens = round(tracker.total_tokens / tracker.total_requests)
        st.info(f"Average tokens per successful image: **{avg_tokens}**")

    if tracker.last_limit_error:
        err = tracker.last_limit_error
        st.error(
            f"Last Groq limit hit: **{err.limit_type}** | "
            f"Limit: **{err.limit}**, Used: **{err.used}**, "
            f"Requested: **{err.requested}**, "
            f"Remaining before request: **{err.remaining_before_request}**"
        )
        if err.retry_after_text:
            st.warning(f"Groq suggested retry after: **{err.retry_after_text}**")

    rows = tracker.as_rows()
    if rows and not compact:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Groq usage CSV",
            data=csv,
            file_name="groq_usage_session.csv",
            mime="text/csv",
        )

    if st.button("Reset usage counters", key=f"reset_usage_{'compact' if compact else 'main'}"):
        st.session_state.groq_usage_tracker = GroqUsageTracker(limits=DEFAULT_GROQ_LIMITS)
        st.rerun()


def render_results_preview():
    with st.expander("Processing summary", expanded=False):
        for item in st.session_state.extraction_results:
            meta = item.get("processing_meta", {})
            usage = item.get("usage", {})
            st.write(
                f"Image {item['image_number']} - {item['file_name']} | "
                f"{meta.get('original_dimensions')} / {meta.get('original_size_kb')} KB "
                f"→ {meta.get('final_dimensions')} / {meta.get('final_size_kb')} KB | "
                f"Tokens: {usage.get('total_tokens', 'N/A')} "
                f"(input {usage.get('prompt_tokens', 'N/A')}, output {usage.get('completion_tokens', 'N/A')})"
            )


def render_pdf_download_section():
    pdf_name = st.text_input(
        "File Name",
        value=DEFAULT_PDF_NAME
    )

    pdf_theme = st.selectbox(
        "PDF Theme",
        PDF_THEMES
    )

    pdf_path = get_temp_pdf_path(pdf_name)

    create_pdf(
        st.session_state.extraction_results,
        pdf_path,
        pdf_name,
        pdf_theme
    )

    with open(pdf_path, "rb") as f:
        st.download_button(
            label="Generate & Download PDF",
            data=f.read(),
            file_name=f"{pdf_name}.pdf",
            mime="application/pdf",
        )
