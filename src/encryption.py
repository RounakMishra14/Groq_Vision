from __future__ import annotations

import streamlit as st
from cryptography.fernet import Fernet


def _get_cipher() -> Fernet:
    key = st.secrets.get("FERNET_KEY")
    if not key:
        raise RuntimeError(
            "FERNET_KEY is missing. Add it to .streamlit/secrets.toml locally "
            "or Streamlit Cloud Secrets in production."
        )
    return Fernet(str(key).encode())


def encrypt(text: str) -> str:
    return _get_cipher().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    return _get_cipher().decrypt(text.encode()).decode()
