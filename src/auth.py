from __future__ import annotations

import streamlit as st

from src.database import create_user, validate_user


def init_auth_state() -> None:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = None


def login_user(username: str, password: str) -> bool:
    clean_username = username.strip().lower()
    if not clean_username or not password:
        return False

    if not validate_user(clean_username, password):
        return False

    st.session_state.logged_in = True
    st.session_state.username = clean_username
    return True


def register_user(username: str, password: str) -> bool:
    clean_username = username.strip().lower()
    if not clean_username or not password:
        return False

    return create_user(clean_username, password)


def logout() -> None:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.groq_api_key = None
    st.rerun()
