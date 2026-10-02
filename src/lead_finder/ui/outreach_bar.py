from __future__ import annotations

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.outreach_sender import normalize_sender
from lead_finder.ui.layout import OUTREACH_COLUMNS
from lead_finder.ui.outreach_preview import focus_outreach_preview, render_outreach_preview
from lead_finder.use_company_search import SearchResult
from lead_finder.use_outreach import generate_outreach, resolve_outreach_selection


def render_outreach_bar(
    result: SearchResult,
    selected_indices: list[int],
    *,
    session_key: str,
    widget_key: str,
) -> SearchResult:
    settings = get_settings()
    stored_key = f"{session_key}_outreach_orgs"
    current = [
        result.companies[index].company.organization_number
        for index in selected_indices
        if 0 <= index < len(result.companies)
    ]
    stored = list(st.session_state.get(stored_key) or [])
    usable = current or stored
    capped = usable[: settings.outreach_max_selected]
    sender_choice = st.radio(
        "From",
        ["Norrpoint", "Metricop"],
        index=None,
        horizontal=True,
        key=f"outreach_sender_{widget_key}",
        help="Whose request this is. The email is written in that brand's voice.",
    )
    button_column, count_column, _spacer = st.columns(OUTREACH_COLUMNS)
    with button_column:
        clicked = st.button(
            "Generate outreach",
            type="primary",
            disabled=not capped or not sender_choice,
            key=f"outreach_{widget_key}",
            help="Select Norrpoint or Metricop, tick a row, then generate.",
        )
    with count_column:
        st.caption(str(len(capped)))
    if current:
        focus_outreach_preview(result, current, widget_key=widget_key)
    chosen, persist = resolve_outreach_selection(current, stored, clicked=clicked)
    st.session_state[stored_key] = persist
    if clicked:
        result = _run_outreach(
            result,
            chosen[: settings.outreach_max_selected],
            session_key=session_key,
            widget_key=widget_key,
            sender=normalize_sender(sender_choice),
        )
    return render_outreach_preview(
        result,
        session_key=session_key,
        widget_key=widget_key,
        sender=sender_choice,
    )


def _run_outreach(
    result: SearchResult,
    org_numbers: list[str],
    *,
    session_key: str,
    widget_key: str,
    sender: str,
) -> SearchResult:
    if not org_numbers:
        st.error("Select at least one company with the row checkbox, then generate.")
        return result
    progress = st.progress(0, text="Starting outreach...")

    def on_progress(done: int, total: int, message: str) -> None:
        progress.progress(min(done / total, 1.0), text=message)

    try:
        result = generate_outreach(
            result, org_numbers, sender=sender, on_progress=on_progress
        )
        st.session_state[session_key] = result
        focus_outreach_preview(result, org_numbers, widget_key=widget_key)
        nonce_key = f"{session_key}_nonce"
        st.session_state[nonce_key] = int(st.session_state.get(nonce_key) or 0) + 1
        drafted = sum(
            1
            for scored in result.companies
            if scored.outreach is not None and scored.outreach.body
        )
        if drafted:
            progress.progress(1.0, text=f"Drafted {drafted} email(s) — see below.")
        else:
            progress.progress(1.0, text="Outreach finished, but no email could be drafted.")
            st.warning("No draft was created. Check the Outreach preview for the reason.")
        st.rerun()
    except Exception as error:
        st.error(f"Outreach failed: {error}")
    return result
