from __future__ import annotations

import streamlit as st

from lead_finder.ui.export_bar import render_export_bar
from lead_finder.ui.outreach_bar import render_outreach_bar
from lead_finder.ui.result_table import (
    render_result_table,
    result_columns,
    result_row,
    score_explanation,
)
from lead_finder.use_company_search import SearchResult
from lead_finder.use_result_columns import use_result_columns

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
    drafted = sum(scored.outreach is not None for scored in result.companies)
    metric_left, metric_middle, metric_right = st.columns(3)
    metric_left.metric("Fetched", summary.fetched)
    metric_middle.metric("Relevant companies", summary.matched)
    metric_right.metric("With missing data", summary.incomplete)
    if drafted:
        st.caption(f"Outreach drafted for {drafted} companies.")

    include_match = matched > 0
    include_outreach = drafted > 0
    rows = [
        result_row(scored, include_match=include_match, include_outreach=include_outreach)
        for scored in result.companies
    ]
    explanations = [score_explanation(scored) for scored in result.companies]
    available = result_columns(include_match=include_match, include_outreach=include_outreach)
    state_key = f"result_columns_{session_key}"
    order = use_result_columns(available, state_key=state_key)
    nonce = st.session_state.get(f"{session_key}_nonce", 0)
    selected = render_result_table(
        rows,
        available=available,
        order=order or available,
        widget_key=f"results_editor_{session_key}_{nonce}",
        state_key=state_key,
        explanations=explanations,
    )
    render_export_bar(result.companies, download_name=download_name)
    render_outreach_bar(
        result,
        selected,
        session_key=session_key,
        widget_key=download_name,
    )
