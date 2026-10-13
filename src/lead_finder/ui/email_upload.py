from __future__ import annotations

import streamlit as st

from lead_finder.use_email_desk import UPLOADED_LABEL, load_saved_leads

UPLOAD_TOKEN = "email_upload_token"


def render_saved_upload() -> None:
    uploaded = st.file_uploader(
        "Saved companies",
        type=["json"],
        key="email_upload",
        help="A companies JSON exported from this app, or a list of company records.",
    )
    if uploaded is None:
        return
    token = f"{uploaded.name}:{uploaded.size}"
    if st.session_state.get(UPLOAD_TOKEN) == token:
        return
    try:
        loaded = load_saved_leads(uploaded.getvalue())
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state["uploaded_result"] = loaded
    st.session_state["email_source"] = UPLOADED_LABEL
    st.session_state[UPLOAD_TOKEN] = token
    st.rerun()
