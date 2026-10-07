from __future__ import annotations

import logging

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.outreach_sender import normalize_sender
from lead_finder.ui.layout import OUTREACH_COLUMNS
from lead_finder.ui.lead_queue import (
    continue_lead_queue,
    render_lead_queue_status,
    start_lead_queue,
)
from lead_finder.ui.notices import push_notice, show_notices
from lead_finder.ui.outreach_preview import focus_outreach_preview, render_outreach_preview
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_queue import (
    companies_to_crawl,
    estimate_crawl_seconds,
    format_crawl_estimate,
)
from lead_finder.use_outreach import generate_outreach, resolve_outreach_selection

logger = logging.getLogger(__name__)


def render_outreach_bar(
    result: SearchResult,
    selected_indices: list[int],
    *,
    session_key: str,
    widget_key: str,
) -> SearchResult:
    show_notices(session_key)
    result = continue_lead_queue(result, session_key=session_key)
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
    leads_column, outreach_column, count_column, _spacer = st.columns(OUTREACH_COLUMNS)
    with leads_column:
        leads_clicked = st.button(
            "Generate leads",
            type="primary",
            disabled=not usable,
            key=f"leads_{widget_key}",
            help="Crawl every selected row, 20 at a time.",
        )
    with outreach_column:
        outreach_clicked = st.button(
            "Generate outreach",
            disabled=not capped or not sender_choice,
            key=f"outreach_{widget_key}",
            help="Write emails for the first 20 selected rows that already have a crawl.",
        )
    with count_column:
        st.caption(_selection_caption(result, usable, batch_size=settings.outreach_max_selected))
    if current:
        focus_outreach_preview(result, current, widget_key=widget_key)
    chosen, persist = resolve_outreach_selection(
        current,
        stored,
        clicked=leads_clicked or outreach_clicked,
    )
    st.session_state[stored_key] = persist
    selected = chosen[: settings.outreach_max_selected]
    if leads_clicked:
        start_lead_queue(result, chosen, session_key=session_key)
        st.rerun()
    elif outreach_clicked:
        result = _run_outreach(
            result,
            selected,
            session_key=session_key,
            widget_key=widget_key,
            sender=normalize_sender(sender_choice),
        )
    note = st.session_state.get(f"{session_key}_action_note")
    if note:
        st.warning(note)
    render_lead_queue_status(session_key)
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
            result,
            org_numbers,
            sender=sender,
            on_progress=on_progress,
            on_notice=lambda message: push_notice(session_key, message),
        )
        st.session_state[session_key] = result
        focus_outreach_preview(result, org_numbers, widget_key=widget_key)
        _bump_nonce(session_key)
        drafted = sum(
            1 for scored in result.companies if scored.outreach is not None and scored.outreach.body
        )
        skipped = _uncrawled(result, org_numbers)
        note = ""
        if drafted:
            progress.progress(1.0, text=f"Drafted {drafted} email(s) — see below.")
            if skipped:
                note = f"Skipped {skipped} companies with no crawl."
        elif skipped:
            progress.progress(1.0, text="Generate leads before writing emails.")
            note = "Those rows have no crawl yet. Generate leads first."
        else:
            progress.progress(1.0, text="Outreach finished, but no email could be drafted.")
            note = "No draft was created. Check the Outreach preview for the reason."
        st.session_state[f"{session_key}_action_note"] = note
        st.rerun()
    except Exception as error:
        logger.exception("Outreach failed")
        push_notice(session_key, f"Outreach failed: {error}")
        st.error(f"Outreach failed: {error}")
    return result


def _uncrawled(result: SearchResult, org_numbers: list[str]) -> int:
    wanted = set(org_numbers)
    return sum(
        1
        for scored in result.companies
        if scored.company.organization_number in wanted and scored.crawl_status is None
    )


def _bump_nonce(session_key: str) -> None:
    nonce_key = f"{session_key}_nonce"
    st.session_state[nonce_key] = int(st.session_state.get(nonce_key) or 0) + 1


def _selection_caption(
    result: SearchResult,
    selected: list[str],
    *,
    batch_size: int,
) -> str:
    if not selected:
        return ""
    pending = len(companies_to_crawl(result, selected))
    if pending <= 0:
        return str(len(selected))
    estimate = format_crawl_estimate(
        estimate_crawl_seconds(
            pending,
            batch_size=batch_size,
            pause_seconds=0,
        )
    )
    return f"{len(selected)} selected · {estimate}"
