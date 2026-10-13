from __future__ import annotations

import logging

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.ui.results import render_results
from lead_finder.ui.sni_search_filter import render_sni_search_filter
from lead_finder.use_analyzed_companies import (
    AnalyzedFilters,
    analyzed_summary,
    filter_analyzed,
    load_analyzed_companies,
    merge_analyzed,
)
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_company_store import SavedSearch, StoreError, get_company_store
from lead_finder.use_lead_job import get_lead_job

logger = logging.getLogger(__name__)

FULL_KEY = "analyzed_companies"
VIEW_KEY = "analyzed_view"
SEARCHES_KEY = "analyzed_searches"
_SNI_KEY = "analyzed_sni_codes"
_WEBSITE = {"Any": "any", "Has website": "yes", "No website": "no"}
_CRAWL = {"Any": "any", "Crawled": "crawled", "Failed": "failed", "Not crawled": "missing"}
_EMAIL = {"Any": "any", "Has email": "yes", "No email": "no"}


def render_analyzed_tab() -> None:
    if not _ensure_loaded():
        return
    full = _merged_companies()
    searches = _saved_searches()
    filters = _render_filters(full.companies)
    _reset_page_for_filters(filters)
    visible = filter_analyzed(full.companies, filters, searches)
    export_count = len(visible)
    st.caption(f"{analyzed_summary(visible)}. Export all downloads {export_count} companies.")
    if not full.companies:
        st.info("No companies are saved yet. Run a search, then they show up here.")
        return
    if not visible:
        st.info("No companies match these filters.")
        return
    shown = SearchResult(
        companies=visible,
        summary=SearchSummary(
            fetched=len(visible),
            matched=len(visible),
            incomplete=sum(bool(item.missing_data) for item in visible),
        ),
    )
    st.session_state[VIEW_KEY] = shown
    render_results(
        shown,
        download_name="swedish-lidar-analyzed.csv",
        session_key=VIEW_KEY,
        show_save=False,
        show_display=True,
        show_fetched=False,
        catalog_key=FULL_KEY,
        page_size=100,
    )


def _ensure_loaded() -> bool:
    companies_ready = isinstance(st.session_state.get(FULL_KEY), SearchResult)
    searches_ready = isinstance(st.session_state.get(SEARCHES_KEY), list)
    if companies_ready and searches_ready:
        return True
    store = get_company_store()
    if store is None:
        st.info("Supabase is not configured, so saved companies cannot be loaded.")
        return False
    try:
        with st.spinner("Loading analyzed data…"):
            if not companies_ready:
                st.session_state[FULL_KEY] = load_analyzed_companies(store)
            if not searches_ready:
                st.session_state[SEARCHES_KEY] = store.list_searches()
    except StoreError as error:
        if isinstance(st.session_state.get(FULL_KEY), SearchResult):
            logger.exception("Could not load saved searches")
            st.session_state[SEARCHES_KEY] = []
            st.caption("Saved searches could not be loaded.")
            return True
        logger.exception("Could not load analyzed companies")
        st.error(f"Saved companies could not be loaded. {error}")
        return False
    return True


def _merged_companies() -> SearchResult:
    full = st.session_state[FULL_KEY]
    view = st.session_state.get(VIEW_KEY)
    if isinstance(full, SearchResult) and isinstance(view, SearchResult):
        full = merge_analyzed(full, view)
        st.session_state[FULL_KEY] = full
    if not isinstance(full, SearchResult):
        return SearchResult(companies=[], summary=SearchSummary(fetched=0, matched=0, incomplete=0))
    return full


def _saved_searches() -> list[SavedSearch]:
    saved = st.session_state.get(SEARCHES_KEY)
    if isinstance(saved, list):
        return saved
    return []


def _render_filters(companies: list[ScoredCompany]) -> AnalyzedFilters:
    columns = st.columns([2.4, 2.6, 1.5, 1.5, 1.5, 1.8], vertical_alignment="bottom")
    text_column, sni_column, website_column, crawl_column, email_column, action_column = columns
    text = text_column.text_input(
        "Name or org. number",
        key="analyzed_text",
        placeholder="Name or 5563907392…",
    )
    sni_codes = render_sni_search_filter(companies, sni_column, session_key=_SNI_KEY)
    website = website_column.selectbox("Website", list(_WEBSITE), key="analyzed_website")
    crawl = crawl_column.selectbox("Crawl", list(_CRAWL), key="analyzed_crawl")
    email = email_column.selectbox("Email", list(_EMAIL), key="analyzed_email")
    with action_column:
        clear_column, reload_column = st.columns(2)
        clear_column.button("Clear", key="analyzed_clear", on_click=_clear_filters)
        reload_column.button(
            "Reload",
            key="analyzed_reload",
            on_click=_reload,
            disabled=get_lead_job(VIEW_KEY) is not None,
            help="Load the latest saved companies. Unavailable while a crawl is running.",
        )
    return AnalyzedFilters(
        text=text,
        website=_WEBSITE[str(website)],
        crawl=_CRAWL[str(crawl)],
        email=_EMAIL[str(email)],
        sni_codes=sni_codes,
    )


def _reset_page_for_filters(filters: AnalyzedFilters) -> None:
    token = (filters.text, filters.website, filters.crawl, filters.email, filters.sni_codes)
    if st.session_state.get("analyzed_filter_token") == token:
        return
    st.session_state["analyzed_filter_token"] = token
    st.session_state[f"{VIEW_KEY}_page"] = 0


def _clear_filters() -> None:
    st.session_state["analyzed_text"] = ""
    st.session_state["analyzed_website"] = "Any"
    st.session_state["analyzed_crawl"] = "Any"
    st.session_state["analyzed_email"] = "Any"
    st.session_state[_SNI_KEY] = []


def _reload() -> None:
    st.session_state.pop(FULL_KEY, None)
    st.session_state.pop(SEARCHES_KEY, None)
    st.session_state.pop(VIEW_KEY, None)
    st.session_state.pop(f"{VIEW_KEY}_display_org", None)
