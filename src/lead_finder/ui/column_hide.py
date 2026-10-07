from __future__ import annotations

import streamlit as st

from lead_finder.use_result_columns import hide_column

_PENDING_KEY = "column_hide_pending"


def render_column_hide_controls(
    available: list[str],
    order: list[str],
    *,
    state_key: str,
) -> None:
    pending = st.session_state.get(_PENDING_KEY)
    if pending and pending.get("state_key") == state_key:
        _confirm_hide(pending["name"], pending["state_key"])

    hidden = [name for name in available if name not in order]
    if hidden and st.button(
        "Show all columns",
        key=f"restore_cols_{state_key}",
        type="tertiary",
        help="Show columns hidden in this session.",
    ):
        st.session_state[state_key] = list(available)
        st.rerun()

    slots = st.columns(hide_slot_weights(order))
    last_column = len(order) <= 1
    for slot, name in zip(slots[1:], order, strict=True):
        with slot:
            help_text = "At least one column must stay visible." if last_column else f"Hide {name}"
            if st.button(
                "×",
                key=_hide_key(state_key, name),
                type="tertiary",
                help=help_text,
                disabled=last_column,
            ):
                st.session_state[_PENDING_KEY] = {"name": name, "state_key": state_key}
                st.rerun()


def _clear_pending_hide() -> None:
    st.session_state[_PENDING_KEY] = None


@st.dialog("Hide column?", on_dismiss=_clear_pending_hide)
def _confirm_hide(name: str, state_key: str) -> None:
    st.write(f"Are you sure you want to hide **{name}**?")
    cancel, confirm = st.columns(2)
    if cancel.button("Cancel", key=f"hide_cancel_{_slug(name)}"):
        _clear_pending_hide()
        st.rerun()
    if confirm.button("Hide", type="primary", key=f"hide_ok_{_slug(name)}"):
        current = list(st.session_state.get(state_key) or [])
        st.session_state[state_key] = hide_column(current, name)
        _clear_pending_hide()
        st.rerun()


_CHECKBOX_SLOT = 0.38
_COLUMN_WIDTHS = {
    "Score": 0.55,
    "Company": 1.8,
    "Analyzed": 0.7,
    "Website": 1.5,
    "Email": 1.3,
    "Email body": 1.5,
    "Evidence": 1.3,
    "Subject": 1.2,
    "Fit": 0.55,
}


def hide_slot_weights(order: list[str]) -> list[float]:
    return [_CHECKBOX_SLOT, *(_COLUMN_WIDTHS.get(name, 0.85) for name in order)]


def _hide_key(state_key: str, name: str) -> str:
    return f"hide_col_{state_key}_{_slug(name)}"


def _slug(name: str) -> str:
    return name.replace(" ", "_").replace(".", "")
