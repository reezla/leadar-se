from __future__ import annotations

import logging

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.models import ScoredCompany
from lead_finder.outreach_sender import normalize_sender
from lead_finder.ui.email_upload import render_saved_upload
from lead_finder.ui.notices import push_notice, show_notices
from lead_finder.ui.outreach_preview import focus_outreach_preview, render_outreach_preview
from lead_finder.ui.result_rows import crawled_table, score_explanation
from lead_finder.ui.result_table import render_result_table
from lead_finder.use_company_search import SearchResult
from lead_finder.use_email_desk import (
    desk_companies,
    draft_status,
    seed_email_selection,
    selected_org_numbers,
    source_entries,
)
from lead_finder.use_outreach import generate_outreach
from lead_finder.use_result_columns import use_result_columns

logger = logging.getLogger(__name__)


def render_email_page() -> None:
    st.title("Write emails")
    st.caption(
        "Upload a saved companies file, or use a list from Find companies. "
        "Drafts use saved website text when the file has it, and company details when it does not. "
        "This page does not search or crawl."
    )
    render_saved_upload()
    entries = source_entries(st.session_state)
    if not entries:
        st.info("Search for companies on Find companies, or upload a saved companies JSON.")
        return
    session_key, result = _choose_source(entries)
    show_notices(session_key)
    companies = desk_companies(result)
    _metrics(companies)
    _write_desk(result, companies, session_key=session_key)


def _choose_source(entries: list[tuple[str, str, SearchResult]]) -> tuple[str, SearchResult]:
    if len(entries) == 1:
        key, _label, result = entries[0]
        return key, result
    labels = [label for _key, label, _result in entries]
    choice = st.radio("Company list", labels, horizontal=True, key="email_source")
    for key, label, result in entries:
        if label == choice:
            return key, result
    key, _label, result = entries[0]
    return key, result


def _metrics(companies: list[ScoredCompany]) -> None:
    with_website = sum(_has_website(scored) for scored in companies)
    drafted = sum(draft_status(scored) == "Drafted" for scored in companies)
    companies_col, website_col, drafted_col = st.columns(3)
    companies_col.metric("Companies", len(companies))
    website_col.metric("With website", with_website)
    drafted_col.metric("Drafts", drafted)


def _write_desk(
    result: SearchResult,
    companies: list[ScoredCompany],
    *,
    session_key: str,
) -> None:
    st.subheader("Choose companies")
    seed_email_selection(st.session_state, session_key, result, companies)
    rows, available = crawled_table(companies)
    state_key = f"email_columns_{session_key}"
    selected = render_result_table(
        rows,
        available=available,
        order=use_result_columns(available, state_key=state_key),
        widget_key=f"email_pick_{session_key}",
        state_key=state_key,
        explanations=[score_explanation(scored) for scored in companies],
    )
    settings = get_settings()
    chosen = selected_org_numbers(companies, selected)
    capped = chosen[: settings.outreach_max_selected]
    sender_choice = st.radio(
        "From",
        ["Norrpoint", "Metricop"],
        index=None,
        horizontal=True,
        key=f"email_sender_{session_key}",
        help="Whose request this is. The email is written in that brand's voice.",
    )
    clicked = st.button(
        "Write emails",
        type="primary",
        disabled=not capped or not sender_choice,
        key=f"write_emails_{session_key}",
        help="Draft with OpenAI from saved text, or company details if there is no website.",
    )
    if len(chosen) > settings.outreach_max_selected:
        st.caption(f"The first {settings.outreach_max_selected} selected companies are drafted.")
    elif chosen:
        st.caption(f"{len(chosen)} selected")
    if clicked:
        _run_drafts(result, capped, session_key=session_key, sender=normalize_sender(sender_choice))
    note = st.session_state.get(f"{session_key}_email_note")
    if note:
        st.warning(note)
    fresh = st.session_state.get(session_key)
    if not isinstance(fresh, SearchResult):
        fresh = result
    if any(scored.outreach is not None for scored in fresh.companies):
        st.subheader("Review")
        render_outreach_preview(
            fresh,
            session_key=session_key,
            widget_key=session_key,
            sender=sender_choice,
        )
    else:
        st.caption("Drafts show up here after you write emails.")


def _run_drafts(
    result: SearchResult,
    org_numbers: list[str],
    *,
    session_key: str,
    sender: str,
) -> None:
    progress = st.progress(0, text="Starting drafts...")

    def on_progress(done: int, total: int, message: str) -> None:
        progress.progress(min(done / total, 1.0), text=message)

    try:
        updated = generate_outreach(
            result,
            org_numbers,
            sender=sender,
            on_progress=on_progress,
            on_notice=lambda message: push_notice(session_key, message),
        )
    except Exception as error:
        logger.exception("Email drafting failed")
        push_notice(session_key, f"Email drafting failed: {error}")
        st.error(f"Email drafting failed: {error}")
        return
    st.session_state[session_key] = updated
    focus_outreach_preview(updated, org_numbers, widget_key=session_key)
    nonce_key = f"{session_key}_nonce"
    st.session_state[nonce_key] = int(st.session_state.get(nonce_key) or 0) + 1
    drafted = sum(1 for scored in updated.companies if draft_status(scored) == "Drafted")
    missing = sum(
        1
        for scored in updated.companies
        if scored.company.organization_number in set(org_numbers)
        and draft_status(scored) == "No website"
    )
    note = _finish_note(drafted, missing)
    progress.progress(1.0, text=_finish_progress(drafted, missing))
    st.session_state[f"{session_key}_email_note"] = note
    st.rerun()


def _has_website(scored: ScoredCompany) -> bool:
    if scored.company.domain:
        return True
    return scored.website is not None and bool(scored.website.url)


def _finish_progress(drafted: int, missing: int) -> str:
    if drafted:
        return f"Drafted {drafted} email(s)."
    if missing:
        return "Those companies could not be drafted."
    return "No email could be drafted."


def _finish_note(drafted: int, missing: int) -> str:
    if drafted and missing:
        return f"{missing} selected companies were left without a draft."
    if not drafted:
        return "No draft was created. Check Review for the reason."
    return ""
