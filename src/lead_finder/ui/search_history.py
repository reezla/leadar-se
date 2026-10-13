from __future__ import annotations

import logging
from datetime import UTC, datetime

import streamlit as st

from lead_finder.models import CompanySearchFilters
from lead_finder.use_company_store import SavedSearch, StoreError, get_company_store, query_key
from lead_finder.use_saved_search import format_saved_search

logger = logging.getLogger(__name__)


def render_search_history(segment_key: str, filters: CompanySearchFilters) -> None:
    store = get_company_store()
    if store is None:
        return
    try:
        saved = store.list_searches()
    except StoreError:
        logger.exception("Could not load saved searches")
        st.caption("Saved searches could not be loaded.")
        return
    current = query_key(segment_key, filters)
    match = next((item for item in saved if item.query_key == current), None)
    if match is not None:
        st.caption(_match_caption(match))
    if not saved:
        return
    with st.expander("Already searched"):
        for item in saved:
            st.caption(format_saved_search(item))


def _match_caption(item: SavedSearch) -> str:
    when = _when(item.last_searched_at)
    count = item.saved_count
    return f"This search was last saved {when} · {count} companies · run {item.run_count}."


def _when(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
