from __future__ import annotations

import streamlit as st

from lead_finder.config import load_segments
from lead_finder.models import CompanySearchFilters
from lead_finder.ui.sni_prefix_selector import render_sni_prefix_selector


def render_filters() -> tuple[str, CompanySearchFilters]:
    segments = load_segments()
    segment_key = st.selectbox(
        "Target segment",
        list(segments),
        format_func=lambda key: segments[key].name,
    )
    segment = segments[segment_key]
    st.caption(segment.description)
    sni_prefixes = render_sni_prefix_selector(segment_key, segment.sni_prefixes)

    geography_left, geography_right = st.columns(2)
    with geography_left:
        counties = st.text_input("Counties (optional)", placeholder="Västra Götaland, Skåne")
    with geography_right:
        municipalities = st.text_input(
            "Municipalities (optional)", placeholder="Göteborg, Malmö"
        )

    employee_left, employee_right = st.columns(2)
    with employee_left:
        employee_min = st.number_input("Minimum employees", min_value=0, value=0, step=1)
    with employee_right:
        employee_max = st.number_input("Maximum employees", min_value=0, value=0, step=1)

    revenue_left, revenue_right = st.columns(2)
    with revenue_left:
        revenue_min_msek = st.number_input(
            "Minimum revenue (MSEK)", min_value=0, value=0, step=1
        )
    with revenue_right:
        revenue_max_msek = st.number_input(
            "Maximum revenue (MSEK)", min_value=0, value=0, step=1
        )

    text_query = st.text_input("Name or activity contains (optional)")
    limit = st.slider("Maximum companies", min_value=10, max_value=2_000, value=500, step=10)
    filters = CompanySearchFilters(
        sni_prefixes=sni_prefixes,
        counties=_comma_list(counties),
        municipalities=_comma_list(municipalities),
        employee_min=_optional_positive(employee_min),
        employee_max=_optional_positive(employee_max),
        revenue_min_sek=_optional_positive(revenue_min_msek * 1_000_000),
        revenue_max_sek=_optional_positive(revenue_max_msek * 1_000_000),
        text_query=text_query.strip() or None,
        limit=limit,
    )
    return segment_key, filters


def _comma_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _optional_positive(value: int) -> int | None:
    return value or None
