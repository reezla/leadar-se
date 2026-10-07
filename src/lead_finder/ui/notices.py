from __future__ import annotations

import streamlit as st


def push_notice(session_key: str, message: str) -> None:
    key = f"{session_key}_toasts"
    current = list(st.session_state.get(key) or [])
    if message not in current:
        current.append(message)
    st.session_state[key] = current


def show_notices(session_key: str) -> None:
    key = f"{session_key}_toasts"
    messages = list(st.session_state.get(key) or [])
    if not messages:
        return
    st.session_state[key] = []
    for message in messages:
        st.toast(message, icon=":material/warning:", duration="long")
