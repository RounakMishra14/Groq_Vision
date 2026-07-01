from __future__ import annotations

import time
from typing import Any, Callable

import streamlit as st

from src.config import DELAY_SECONDS, MODEL_NAME
from src.database import save_token_usage
from src.file_utils import cleanup_temp_files, save_uploaded_file_to_temp
from src.groq_service import extract_mcq_with_groq_result
from src.groq_usage import build_friendly_groq_error_message
from src.image_processor import GroqImagePrepConfig, prepare_image_for_groq
from src.usage_store import add_api_daily_usage


def run_extraction(
    uploaded_files,
    prep_config: GroqImagePrepConfig,
    max_completion_tokens: int,
    usage_placeholder: Any,
    groq_api_key: str,
    username: str,
    refresh_usage_panel: Callable[[Any, str], None],
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

            add_api_daily_usage(groq_api_key, groq_result.total_tokens)

            results.append(
                {
                    "image_number": idx,
                    "file_name": uploaded_file.name,
                    "output": groq_result.output,
                    "original_output": groq_result.output,
                    "edited": False,
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
