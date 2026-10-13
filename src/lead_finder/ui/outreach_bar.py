from __future__ import annotations

import logging

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.models import ScoredCompany
from lead_finder.providers.serper_search import SerperSearchError
from lead_finder.ui.lead_queue import (
    continue_lead_queue,
    render_lead_queue_status,
    start_lead_queue,
)
from lead_finder.ui.notices import show_notices, show_successes, toast_success
from lead_finder.ui.result_grid import queue_grid_refresh
from lead_finder.use_company_search import SearchResult
from lead_finder.use_company_store import get_company_store
from lead_finder.use_lead_queue import (
    companies_to_crawl,
    estimate_crawl_seconds,
    format_crawl_estimate,
)
from lead_finder.use_outreach import resolve_outreach_selection
from lead_finder.use_website_find import assign_serper_websites, miss_notice

logger = logging.getLogger(__name__)


def render_outreach_bar(
    result: SearchResult,
    selected_indices: list[int],
    *,
    session_key: str,
    widget_key: str,
    button_slots: tuple[object, object, object | None, object],
) -> SearchResult:
    show_notices(session_key)
    show_successes(session_key)
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
    find_column, leads_column, save_column, count_column = button_slots
    with find_column:
        find_clicked = st.button(
            "Find websites",
            disabled=not usable,
            key=f"find_sites_{widget_key}",
            help="Look up a website and add each selected company to the database.",
        )
    with leads_column:
        leads_clicked = st.button(
            "Generate leads",
            type="primary",
            disabled=not usable,
            key=f"leads_{widget_key}",
            help=(
                "Crawl each selected company's website, recommend Norrpoint scanners, "
                "and save. Companies already crawled reuse their saved text and are "
                "only analyzed."
            ),
        )
    save_clicked = False
    if save_column is not None:
        with save_column:
            save_clicked = st.button(
                "Save selected",
                disabled=not current,
                key=f"save_selected_{widget_key}",
                help="Save the selected companies, including website and crawl data.",
            )
    with count_column:
        st.caption(
            _selection_caption(result, usable, batch_size=settings.outreach_max_selected),
            width="content",
        )
    chosen, persist = resolve_outreach_selection(
        current,
        stored,
        clicked=leads_clicked or find_clicked,
    )
    st.session_state[stored_key] = persist
    if save_clicked:
        _save_selected(result, current)
    if find_clicked:
        result = _find_websites(result, chosen, session_key=session_key)
    if leads_clicked:
        start_lead_queue(result, chosen, session_key=session_key)
        st.rerun()
    render_lead_queue_status(session_key)
    return result


def find_selected_websites(
    result: SearchResult,
    org_numbers: list[str],
    *,
    session_key: str,
) -> SearchResult:
    return _find_websites(result, org_numbers, session_key=session_key)


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
    saved = _save_message(_chosen(outcome.result, org_numbers), include_crawl=False)
    if outcome.found == 0 and not outcome.missed:
        if saved:
            _toast_save(saved)
        st.toast("Those rows already have a website.", icon=":material/info:")
        return result
    st.session_state[session_key] = outcome.result
    if saved:
        _toast_save(saved)
    if outcome.missed:
        st.toast(miss_notice(outcome.missed), icon=":material/warning:", duration="long")
    queue_grid_refresh(session_key)
    return outcome.result


def _save_selected(result: SearchResult, org_numbers: list[str]) -> None:
    message = _save_message(_chosen(result, org_numbers), include_crawl=True)
    if message:
        _toast_save(message)


def _toast_save(message: str) -> None:
    if message.startswith("Saved"):
        toast_success(message)
        return
    st.toast(message, icon=":material/warning:", duration="long")


def _chosen(result: SearchResult, org_numbers: list[str]) -> list[ScoredCompany]:
    wanted = set(org_numbers)
    return [item for item in result.companies if item.company.organization_number in wanted]


def _save_message(companies: list[ScoredCompany], *, include_crawl: bool) -> str:
    store = get_company_store()
    if store is None:
        return "Supabase is not configured, so nothing was saved."
    if not companies:
        return ""
    outcome = store.save_companies(companies, include_crawl=include_crawl)
    if outcome.error:
        logger.warning("Could not save companies: %s", outcome.error)
        return "Saving to the database failed."
    return f"Saved {len(companies)} companies."


def _selection_caption(result: SearchResult, selected: list[str], *, batch_size: int) -> str:
    if not selected:
        return "Select rows, then gather websites. Draft emails on the Write emails page."
    pending = len(companies_to_crawl(result, selected))
    if pending <= 0:
        return f"{len(selected)} selected · website text is ready for Write emails"
    estimate = format_crawl_estimate(
        estimate_crawl_seconds(
            pending,
            batch_size=batch_size,
            pause_seconds=0,
            concurrency=get_settings().website_crawl_concurrency,
        )
    )
    return f"{len(selected)} selected · {estimate}"
