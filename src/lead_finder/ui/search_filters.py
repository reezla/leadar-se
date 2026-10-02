from __future__ import annotations

import streamlit as st

from lead_finder.config import load_segments
from lead_finder.models import CompanySearchFilters
from lead_finder.ui.layout import FILTER_PAIR_COLUMNS, FILTER_SINGLE_COLUMNS, SEGMENT_COLUMNS
from lead_finder.ui.sni_prefix_selector import render_sni_prefix_selector


def render_filters() -> tuple[str, CompanySearchFilters]:
    segments = load_segments()
    segment_column, _segment_spacer = st.columns(SEGMENT_COLUMNS)
    with segment_column:
        segment_key = st.selectbox(
            "Target segment",
            list(segments),
            format_func=lambda key: segments[key].name,
        )
        segment = segments[segment_key]
        st.caption(segment.description)
    sni_prefixes = render_sni_prefix_selector(segment_key, segment.sni_prefixes)

    county_column, municipality_column, _geography_spacer = st.columns(FILTER_PAIR_COLUMNS)
    with county_column:
        counties = st.text_input("Counties (optional)", placeholder="Västra Götaland, Skåne")
    with municipality_column:
        municipalities = st.text_input(
            "Municipalities (optional)", placeholder="Göteborg, Malmö"
        )

    employee_min_column, employee_max_column, _employee_spacer = st.columns(FILTER_PAIR_COLUMNS)
    with employee_min_column:
        employee_min = st.number_input(
            "Employees Min",
            min_value=0,
            value=None,
            step=1,
            placeholder="0",
        )
    with employee_max_column:
        employee_max = st.number_input(
            "Employees Max",
            min_value=0,
            value=None,
            step=1,
            placeholder="0",
        )

    revenue_min_column, revenue_max_column, _revenue_spacer = st.columns(FILTER_PAIR_COLUMNS)
    with revenue_min_column:
        revenue_min_msek = st.number_input(
            "Revenue Min (MSEK)", min_value=0, value=0, step=1
        )
    with revenue_max_column:
        revenue_max_msek = st.number_input(
            "Revenue Max (MSEK)", min_value=0, value=0, step=1
        )

    query_column, _query_spacer = st.columns(FILTER_SINGLE_COLUMNS)
    with query_column:
        text_query = st.text_input("Name or activity contains (optional)")
    fetch_all = bool(st.session_state.get("fetch_all_companies", False))
    limit_column, _limit_spacer = st.columns(FILTER_SINGLE_COLUMNS)
    with limit_column:
        limit = st.number_input(
            "Maximum companies",
            min_value=10,
            max_value=2_000,
            value=500,
            step=10,
            disabled=fetch_all,
        )
        fetch_all = st.checkbox(
            "All matching companies",
            key="fetch_all_companies",
            help="Fetch every company the query returns, whatever the count.",
        )
    filters = CompanySearchFilters(
        sni_prefixes=sni_prefixes,
        counties=_comma_list(counties),
        municipalities=_comma_list(municipalities),
        employee_min=_optional_positive(employee_min),
        employee_max=_optional_positive(employee_max),
        revenue_min_sek=_optional_positive(revenue_min_msek * 1_000_000),
        revenue_max_sek=_optional_positive(revenue_max_msek * 1_000_000),
        text_query=text_query.strip() or None,
        limit=None if fetch_all else int(limit),
    )
    return segment_key, filters


def _comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional_positive(value: int | None) -> int | None:
    if value is None:
        return None
    return value or None
