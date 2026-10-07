from __future__ import annotations

import logging

import streamlit as st

from lead_finder.config import get_settings, load_segments
from lead_finder.models import CompanySearchFilters
from lead_finder.providers import ScbCompanyProvider
from lead_finder.ui.results import render_results
from lead_finder.use_company_search import search_companies

logger = logging.getLogger(__name__)


def render_scb_tab(segment_key: str, filters: CompanySearchFilters) -> None:
    if not filters.sni_prefixes:
        st.warning("Select at least one SNI prefix, then search.")
    if st.button(
        "Find relevant companies",
        type="primary",
        disabled=not filters.sni_prefixes,
    ):
        settings = get_settings()
        try:
            with (
                st.spinner("Searching SCB Företagsregistret..."),
                ScbCompanyProvider(settings) as provider,
            ):
                result = search_companies(
                    provider,
                    filters,
                    load_segments()[segment_key],
                )
                st.session_state["search_result"] = result
                st.session_state["search_result_nonce"] = (
                    int(st.session_state.get("search_result_nonce") or 0) + 1
                )
        except Exception as error:
            logger.exception("SCB search failed")
            message = f"SCB search failed: {error}"
            st.toast(message, icon=":material/warning:", duration="long")
            st.error(message)

    result = st.session_state.get("search_result")
    if result and result.companies:
        render_results(
            result,
            download_name="swedish-lidar-leads.csv",
            session_key="search_result",
        )
    elif result:
        st.warning("No companies matched these filters. Add SNI prefixes or widen the search.")
