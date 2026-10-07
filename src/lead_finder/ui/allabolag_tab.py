from __future__ import annotations

import logging

import streamlit as st

from lead_finder.config import get_settings, load_segments
from lead_finder.models import CompanySearchFilters
from lead_finder.providers.allabolag_parse import build_query, build_search_url
from lead_finder.ui.results import render_results
from lead_finder.use_allabolag_crawl import crawl_allabolag

logger = logging.getLogger(__name__)


def render_allabolag_tab(segment_key: str, filters: CompanySearchFilters) -> None:
    st.caption(
        "Stopgap crawler of public Allabolag segmentation listings while SCB access is pending. "
        "It is rate-limited, reads listing pages only, and skips people/board data. "
        "Allabolag terms restrict unlicensed commercial reuse; prefer SCB once the key arrives."
    )
    if not filters.sni_prefixes:
        st.warning("Select at least one SNI prefix. An unfiltered crawl would be too broad.")
    ab_only = st.checkbox("Aktiebolag only", value=True, key="allabolag_ab_only")
    settings = get_settings()
    preview_url = build_search_url(
        settings.allabolag_base_url,
        build_query(filters, ab_only=ab_only),
    )
    st.link_button("Open this search on Allabolag", preview_url)

    if st.button("Crawl Allabolag", type="primary", disabled=not filters.sni_prefixes):
        progress = st.progress(0, text="Starting Allabolag crawl...")

        def on_progress(page: int, fetched: int, hits: int) -> None:
            target = hits or 1
            if filters.limit is not None:
                target = min(hits, filters.limit) or 1
            progress.progress(
                min(fetched / target, 1.0),
                text=f"Page {page}: {fetched} of {target} ({hits} matches)",
            )

        try:
            st.session_state["allabolag_result"] = crawl_allabolag(
                filters,
                load_segments()[segment_key],
                settings,
                ab_only=ab_only,
                on_progress=on_progress,
            )
            st.session_state["allabolag_result_nonce"] = (
                int(st.session_state.get("allabolag_result_nonce") or 0) + 1
            )
            progress.progress(1.0, text="Crawl finished")
        except Exception as error:
            logger.exception("Allabolag crawl failed")
            message = f"Allabolag crawl failed: {error}"
            st.toast(message, icon=":material/warning:", duration="long")
            st.error(message)

    result = st.session_state.get("allabolag_result")
    if result and result.companies:
        render_results(
            result,
            download_name="allabolag-lidar-leads.csv",
            session_key="allabolag_result",
        )
    elif result:
        st.warning("No companies matched these filters. Add SNI prefixes or widen the search.")
