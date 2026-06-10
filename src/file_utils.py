import os
import tempfile


def save_uploaded_file_to_temp(uploaded_file) -> str:
    """
    Save Streamlit uploaded file to a temporary file
    and return the temp file path.
    """

    suffix = os.path.splitext(uploaded_file.name)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        return tmp.name


def cleanup_temp_files(file_paths: list[str]) -> None:
    """
    Delete temporary files safely.
    """

    for path in file_paths:
        if path and os.path.exists(path):
            os.remove(path)


def get_temp_pdf_path(pdf_name: str) -> str:
    """
    Create temporary PDF path.
    """

    return os.path.join(
        tempfile.gettempdir(),
        f"{pdf_name}.pdf"
    )