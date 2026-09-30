from __future__ import annotations

import streamlit as st

from lead_finder.config import get_settings, load_segments
from lead_finder.models import CompanySearchFilters
from lead_finder.providers import ScbCompanyProvider
from lead_finder.ui.results import render_results
from lead_finder.use_company_search import search_companies


def render_scb_tab(segment_key: str, filters: CompanySearchFilters) -> None:
    st.caption("Official SCB Företagsregistret search. Requires API credentials in `.env`.")
    if st.button("Find relevant companies", type="primary"):
        settings = get_settings()
        try:
            with (
                st.spinner("Searching SCB Företagsregistret..."),
                ScbCompanyProvider(settings) as provider,
            ):
                st.session_state["search_result"] = search_companies(
                    provider,
                    filters,
                    load_segments()[segment_key],
                )
        except Exception as error:
            st.error(f"SCB search failed: {error}")

    result = st.session_state.get("search_result")
    if result:
        render_results(result, download_name="swedish-lidar-leads.csv")
    else:
        st.info("Configure filters and search. SCB API credentials are required in `.env`.")
