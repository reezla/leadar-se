from __future__ import annotations

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.ui.export_bar import render_export_bar
from lead_finder.ui.outreach_bar import render_outreach_bar
from lead_finder.ui.result_rows import (
    result_columns,
    result_row,
    score_explanation,
    website_profile,
)
from lead_finder.ui.result_select import render_select_more
from lead_finder.ui.result_table import render_result_table
from lead_finder.ui.table_sort_bridge import (
    render_table_order_field,
    render_table_order_script,
)
from lead_finder.use_company_search import SearchResult
from lead_finder.use_result_columns import use_result_columns
from lead_finder.use_result_selection import results_editor_key

_columns = result_columns
_row = result_row


def render_results(
    result: SearchResult,
    *,
    download_name: str,
    session_key: str,
) -> None:
    summary = result.summary
    matched = sum(scored.product_match is not None for scored in result.companies)
    crawled = sum(scored.crawl_status is not None for scored in result.companies)
    drafted = sum(scored.outreach is not None for scored in result.companies)
    st.metric("Fetched", summary.fetched)
    if crawled:
        st.caption(f"Website data gathered for {crawled} companies.")
    if drafted:
        st.caption(f"Outreach drafted for {drafted} companies.")

    include_match = matched > 0
    include_crawl = crawled > 0 or any(
        website_profile(scored) is not None for scored in result.companies
    )
    include_outreach = drafted > 0
    rows = [
        result_row(
            scored,
            include_match=include_match,
            include_crawl=include_crawl,
            include_outreach=include_outreach,
        )
        for scored in result.companies
    ]
    explanations = [score_explanation(scored) for scored in result.companies]
    available = result_columns(
        include_match=include_match,
        include_crawl=include_crawl,
        include_outreach=include_outreach,
    )
    state_key = f"result_columns_{session_key}"
    order = use_result_columns(available, state_key=state_key)
    nonce = int(st.session_state.get(f"{session_key}_nonce", 0) or 0)
    widget_key = results_editor_key(session_key, nonce)
    visual_order = render_table_order_field(session_key, len(rows))
    render_select_more(
        [scored.crawled for scored in result.companies],
        widget_key=widget_key,
        session_key=session_key,
        visual_order=visual_order,
    )
    selected = render_result_table(
        rows,
        available=available,
        order=order or available,
        widget_key=widget_key,
        state_key=state_key,
        explanations=explanations,
    )
    render_table_order_script(widget_key, session_key, len(rows))
    render_export_bar(
        result.companies,
        selected=_selected_companies(result.companies, selected),
        download_name=download_name,
    )
    render_outreach_bar(
        result,
        selected,
        session_key=session_key,
        widget_key=download_name,
    )


def _selected_companies(companies: list[ScoredCompany], indices: list[int]) -> list[ScoredCompany]:
    return [companies[index] for index in indices if 0 <= index < len(companies)]
