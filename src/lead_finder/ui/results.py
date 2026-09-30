from __future__ import annotations

import streamlit as st

from lead_finder.exporters import export_hubspot_csv
from lead_finder.use_company_search import SearchResult


def render_results(result: SearchResult, *, download_name: str) -> None:
    summary = result.summary
    metric_left, metric_middle, metric_right = st.columns(3)
    metric_left.metric("Fetched", summary.fetched)
    metric_middle.metric("Relevant companies", summary.matched)
    metric_right.metric("With missing data", summary.incomplete)

    rows = [
        {
            "Score": scored.score,
            "Company": scored.company.name,
            "Org. number": scored.company.organization_number,
            "SNI": ", ".join(scored.company.sni_codes),
            "Municipality": scored.company.municipality,
            "Employees": scored.company.employee_class,
            "Revenue": scored.company.revenue_class,
            "Why": "; ".join(reason.label for reason in scored.reasons),
            "Missing": ", ".join(scored.missing_data),
        }
        for scored in result.companies
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    csv_content = export_hubspot_csv(result.companies)
    st.download_button(
        "Download HubSpot CSV",
        data=csv_content.encode("utf-8-sig"),
        file_name=download_name,
        mime="text/csv",
        disabled=not result.companies,
        key=f"download_{download_name}",
    )
