from __future__ import annotations

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.providers.serper_search import SerperSearchError
from lead_finder.ui.lead_queue import (
    continue_lead_queue,
    render_lead_queue_status,
    start_lead_queue,
)
from lead_finder.ui.notices import push_notice, show_notices
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_queue import (
    companies_to_crawl,
    estimate_crawl_seconds,
    format_crawl_estimate,
)
from lead_finder.use_outreach import resolve_outreach_selection
from lead_finder.use_website_find import assign_serper_websites, miss_notice


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
    find_column, leads_column, count_column = st.columns([2, 2, 4])
    with find_column:
        find_clicked = st.button(
            "Find websites",
            disabled=not usable,
            key=f"find_sites_{widget_key}",
            help="Serper looks up one website per selected company and saves it on that row.",
        )
    with leads_column:
        leads_clicked = st.button(
            "Generate leads",
            type="primary",
            disabled=not usable,
            key=f"leads_{widget_key}",
            help="Crawl the selection, 20 at a time. Google still finds a missing website.",
        )
    with count_column:
        st.caption(_selection_caption(result, usable, batch_size=settings.outreach_max_selected))
    chosen, persist = resolve_outreach_selection(
        current,
        stored,
        clicked=leads_clicked or find_clicked,
    )
    st.session_state[stored_key] = persist
    if find_clicked:
        result = _find_websites(result, chosen, session_key=session_key)
    if leads_clicked:
        start_lead_queue(result, chosen, session_key=session_key)
        st.rerun()
    render_lead_queue_status(session_key)
    return result


def _find_websites(
    result: SearchResult,
    org_numbers: list[str],
    *,
    session_key: str,
) -> SearchResult:
    try:
        outcome = assign_serper_websites(result, org_numbers)
    except SerperSearchError as error:
        st.error(str(error))
        return result
    if outcome.found == 0 and not outcome.missed:
        st.toast("Those rows already have a website.", icon=":material/info:")
        return result
    st.session_state[session_key] = outcome.result
    if outcome.missed:
        push_notice(session_key, miss_notice(outcome.missed))
    st.rerun()
    return outcome.result


def _selection_caption(result: SearchResult, selected: list[str], *, batch_size: int) -> str:
    if not selected:
        return "Select rows, then gather websites. Draft emails on the Write emails page."
    pending = len(companies_to_crawl(result, selected))
    if pending <= 0:
        return f"{len(selected)} selected · website text is ready for Write emails"
    estimate = format_crawl_estimate(
        estimate_crawl_seconds(pending, batch_size=batch_size, pause_seconds=0)
    )
    return f"{len(selected)} selected · {estimate}"
