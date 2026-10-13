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


def push_success(session_key: str, message: str) -> None:
    key = f"{session_key}_success_toasts"
    current = list(st.session_state.get(key) or [])
    if message not in current:
        current.append(message)
    st.session_state[key] = current


def show_successes(session_key: str) -> None:
    key = f"{session_key}_success_toasts"
    messages = list(st.session_state.get(key) or [])
    if not messages:
        return
    st.session_state[key] = []
    for message in messages:
        toast_success(message)


def toast_success(message: str) -> None:
    st.toast(message, icon=":material/check_circle:", duration="long")
    _paint_success_icon()


def _paint_success_icon() -> None:
    st.html(
        """
        <script>
        (function () {
          function paint() {
            var icons = document.querySelectorAll('[data-testid="stToastDynamicIcon"]');
            for (var i = 0; i < icons.length; i++) {
              var name = (icons[i].textContent || "").trim();
              if (name === "check_circle") {
                icons[i].style.color = "#3cba6a";
              }
            }
          }
          paint();
          setTimeout(paint, 60);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )
