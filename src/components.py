from __future__ import annotations

import streamlit as st

from src.auth import login_user, logout, register_user
from src.config import DEFAULT_PDF_NAME, GROQ_KEYS_URL, PDF_THEMES
from src.database import get_user_token_summary, save_groq_key
from src.encryption import encrypt
from src.file_utils import get_temp_pdf_path
from src.groq_usage import GroqUsageTracker
from src.pdf_service import create_pdf
from src.usage_store import get_api_daily_usage


def apply_login_css() -> None:
    st.markdown(
        """
<style>
.stApp {
    background:
        radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.14), transparent 28%),
        linear-gradient(135deg, #02070b 0%, #03151b 52%, #010507 100%) !important;
    color: #eafcff !important;
}
.block-container {
    max-width: 760px !important;
    padding-top: 1.4rem !important;
    padding-bottom: 2rem !important;
}
header, footer {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}
h1, h2, h3, h4, h5, h6, p, label, span, div {
    color: #eafcff;
}
a { color: #00e5ff !important; }
.groq-hero {
    border: 1px solid rgba(0, 229, 255, 0.42);
    border-radius: 18px;
    padding: 30px 26px 24px 26px;
    background: linear-gradient(180deg, rgba(1, 23, 31, 0.92), rgba(1, 12, 18, 0.92));
    box-shadow: 0 0 45px rgba(0, 229, 255, 0.08);
    text-align: center;
    margin-bottom: 18px;
}
.groq-title {
    color: #00e5ff !important;
    font-size: 50px;
    font-weight: 900;
    line-height: 1;
    margin: 0;
    text-shadow: 0 0 24px rgba(0, 229, 255, 0.55);
}
.groq-subtitle {
    color: #ffffff !important;
    font-size: 17px;
    font-weight: 750;
    margin-top: 10px;
}
.groq-line {
    height: 1px;
    width: 84%;
    margin: 22px auto 0 auto;
    background: linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.85), transparent);
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: rgba(0, 229, 255, 0.42) !important;
    background: linear-gradient(180deg, rgba(1, 23, 31, 0.84), rgba(1, 11, 17, 0.92)) !important;
    box-shadow: 0 0 32px rgba(0, 229, 255, 0.06) !important;
}
.stTextInput label, .stTabs [data-baseweb="tab"] p {
    color: #eafcff !important;
    font-weight: 750 !important;
}
.stTextInput input {
    background-color: rgba(0, 0, 0, 0.25) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.55) !important;
    border-radius: 10px !important;
}
.stTextInput input:focus {
    border-color: #00e5ff !important;
    box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.35) !important;
}
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    width: 100% !important;
    border-radius: 10px !important;
    border: 1px solid rgba(0, 229, 255, 0.72) !important;
    background: linear-gradient(135deg, #00e5ff, #009bb8) !important;
    color: #001014 !important;
    font-weight: 900 !important;
    box-shadow: 0 0 20px rgba(0, 229, 255, 0.25) !important;
    text-decoration: none !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stLinkButton > a:hover {
    transform: translateY(-1px);
    box-shadow: 0 0 28px rgba(0, 229, 255, 0.40) !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 22px;
    border-bottom: 1px solid rgba(0, 229, 255, 0.22);
}
.stTabs [aria-selected="true"] p {
    color: #00e5ff !important;
    font-weight: 900 !important;
}
.stAlert {
    background: rgba(0, 229, 255, 0.08) !important;
    color: #eafcff !important;
    border: 1px solid rgba(0, 229, 255, 0.28) !important;
}
.login-footer {
    text-align: center;
    color: rgba(234, 252, 255, 0.70) !important;
    font-weight: 700;
    margin-top: 16px;
    font-size: 14px;
}
</style>
        """,
        unsafe_allow_html=True,
    )


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

        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            background-color: rgba(0,0,0,0.22) !important;
            color: #eafcff !important;
            border-color: rgba(0, 229, 255, 0.55) !important;
        }
        .stTextArea textarea {
            min-height: 260px !important;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
            font-size: 13px !important;
            line-height: 1.45 !important;
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


def render_login_hero() -> None:
    st.markdown(
        """
<div class="groq-hero">
    <div class="groq-title">Groq Vision</div>
    <div class="groq-subtitle">Batch MCQ Extractor</div>
    <div class="groq-line"></div>
</div>
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


def render_login_page() -> None:
    apply_login_css()
    render_login_hero()
    render_login_api_key_card()
    render_login_register_card()
    render_login_security_card()
    st.markdown('<div class="login-footer">Secure. Fast. Powered by Groq.</div>', unsafe_allow_html=True)


def render_login_api_key_card() -> None:
    with st.container(border=True):
        st.markdown("### Need a Groq API Key?")
        st.write("Generate your free Groq API key here:")
        st.link_button("Get Free Groq API Key", GROQ_KEYS_URL)
        st.caption(
            "After creating the key, return here and log in. "
            "Your Groq key will be requested after successful login."
        )


def render_login_register_card() -> None:
    with st.container(border=True):
        tabs = st.tabs(["Login", "Create New Account"])

        with tabs[0]:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login")

                if submitted:
                    if not username.strip() or not password:
                        st.error("Email and password required")
                    elif login_user(username, password):
                        st.rerun()
                    else:
                        st.error("Invalid login")

        with tabs[1]:
            with st.form("register_form", clear_on_submit=False):
                username = st.text_input("Email", key="register_email")
                password = st.text_input("Password", type="password", key="register_password")
                confirm = st.text_input("Confirm Password", type="password", key="register_confirm")
                submitted = st.form_submit_button("Create Account")

                if submitted:
                    if not username.strip() or not password:
                        st.error("Email and password required")
                    elif password != confirm:
                        st.error("Passwords do not match")
                    elif register_user(username, password):
                        st.success("Account created. Please login now.")
                    else:
                        st.error("User already exists")


def render_login_security_card() -> None:
    with st.container(border=True):
        st.markdown("### Secure. Fast. Powered by Groq.")
        st.caption(
            "Your API key is encrypted and stored securely. "
            "It is only used to process your uploaded MCQ images."
        )


def render_profile_menu(username: str) -> None:
    if hasattr(st, "popover"):
        with st.popover("Profile", use_container_width=True):
            render_profile_actions(username)
    else:
        with st.expander("Profile Actions", expanded=False):
            render_profile_actions(username)


def render_profile_actions(username: str) -> None:
    summary = get_user_token_summary(username)

    st.caption("Signed in as")
    st.code(username, language=None)

    st.success("Groq API key saved")

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
        <div class="gv-usage-left">{_format_number(remaining)} left</div>
    </div>
    """


def render_groq_usage_panel(groq_api_key: str) -> None:
    tracker: GroqUsageTracker = st.session_state.groq_usage_tracker
    limits = tracker.limits
    daily_usage = get_api_daily_usage(groq_api_key)

    st.markdown(
        f"""
        <div class="gv-card">
            <div class="gv-section-title">Session Usage</div>
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
            <div class="gv-section-title">Extracted Results</div>
            <div class="gv-caption">
                Preview extracted MCQs below. Open an image, click Edit, correct the extracted text,
                and press Save. The saved edited text will be used in the generated PDF.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for index, item in enumerate(st.session_state.extraction_results):
        image_number = item.get("image_number", index + 1)
        file_name = item.get("file_name", f"Image_{image_number}")
        output_text = item.get("output", "")

        edit_mode_key = f"edit_mode_result_{index}"
        edit_text_key = f"edit_text_result_{index}"

        if edit_mode_key not in st.session_state:
            st.session_state[edit_mode_key] = False

        if edit_text_key not in st.session_state:
            st.session_state[edit_text_key] = output_text

        edited_badge = "  Edited" if item.get("edited") else ""

        with st.expander(
            f"Image {image_number}: {file_name}{edited_badge}",
            expanded=False,
        ):
            usage = item.get("usage", {})

            if st.session_state[edit_mode_key]:
                edited_text = st.text_area(
                    "Edit extracted MCQ text",
                    value=st.session_state[edit_text_key],
                    height=360,
                    key=f"edit_area_result_{index}",
                    help="Edit the extracted question/options/answer text here, then click Save. The PDF will use the saved version.",
                )

                save_col, cancel_col, _ = st.columns([1, 1, 4], gap="small")

                with save_col:
                    save_clicked = st.button(
                        "Save",
                        key=f"save_edit_result_{index}",
                        use_container_width=True,
                    )

                with cancel_col:
                    cancel_clicked = st.button(
                        "Cancel",
                        key=f"cancel_edit_result_{index}",
                        use_container_width=True,
                    )

                if save_clicked:
                    st.session_state.extraction_results[index]["output"] = edited_text
                    st.session_state.extraction_results[index]["edited"] = True
                    st.session_state[edit_text_key] = edited_text
                    st.session_state[edit_mode_key] = False
                    st.success("Edited text saved. PDF export will use this saved version.")
                    st.rerun()

                if cancel_clicked:
                    st.session_state[edit_text_key] = st.session_state.extraction_results[index].get("output", "")
                    st.session_state[edit_mode_key] = False
                    st.rerun()

            else:
                view_col, edit_col = st.columns([5.3, 1], gap="small")

                with view_col:
                    if item.get("edited"):
                        st.success("Saved edited version will be used in the PDF.")

                with edit_col:
                    if st.button(
                        "Edit",
                        key=f"edit_result_{index}",
                        use_container_width=True,
                    ):
                        st.session_state[edit_text_key] = output_text
                        st.session_state[edit_mode_key] = True
                        st.rerun()

                st.markdown(output_text.replace("\n", "  \n"))

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
            <div class="gv-section-title">Generate PDF</div>
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
