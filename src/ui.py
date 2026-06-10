import time

import streamlit as st

from src.config import (
    MAX_IMAGES,
    DELAY_SECONDS,
    DEFAULT_PDF_NAME,
    PDF_THEMES,
)

from src.groq_service import extract_mcq_with_groq
from src.pdf_service import create_pdf
from src.file_utils import (
    save_uploaded_file_to_temp,
    cleanup_temp_files,
    get_temp_pdf_path,
)


def initialize_session_state():
    if "extraction_results" not in st.session_state:
        st.session_state.extraction_results = []


def run_app():
    st.set_page_config(
        page_title="Batch MCQ Extractor",
        layout="wide"
    )

    initialize_session_state()

    st.title("Batch MCQ Extractor")
    st.write("Groq Vision")

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
            run_extraction(uploaded_files)

    if st.session_state.extraction_results:
        render_pdf_download_section()


def run_extraction(uploaded_files):
    results = []
    temp_paths = []

    progress = st.progress(0)
    status = st.empty()

    try:
        for idx, uploaded_file in enumerate(uploaded_files, start=1):
            image_path = save_uploaded_file_to_temp(uploaded_file)
            temp_paths.append(image_path)

            status.write(
                f"Processing image {idx}/{len(uploaded_files)}: {uploaded_file.name}"
            )

            output = extract_mcq_with_groq(
                image_path=image_path,
                image_number=idx
            )

            results.append(
                {
                    "image_number": idx,
                    "file_name": uploaded_file.name,
                    "output": output,
                }
            )

            progress.progress(idx / len(uploaded_files))

            if idx < len(uploaded_files):
                time.sleep(DELAY_SECONDS)

        st.session_state.extraction_results = results
        st.success("Extraction completed.")

    except Exception as e:
        st.error("Error occurred during extraction.")
        st.exception(e)

    finally:
        cleanup_temp_files(temp_paths)


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