from __future__ import annotations

from pathlib import Path

import streamlit as st

from lead_finder.exporters import export_hubspot_csv, export_leads_json
from lead_finder.models import ScoredCompany


def render_export_bar(companies: list[ScoredCompany], *, download_name: str) -> None:
    disabled = not companies
    json_name = Path(download_name).with_suffix(".json").name
    with st.popover(
        "Export",
        icon=":material/download:",
        disabled=disabled,
        key=f"export_menu_{download_name}",
    ):
        st.download_button(
            "CSV for HubSpot",
            data=export_hubspot_csv(companies).encode("utf-8-sig"),
            file_name=download_name,
            mime="text/csv",
            disabled=disabled,
            width="stretch",
            icon=":material/download:",
            key=f"download_csv_{download_name}",
        )
        st.download_button(
            "JSON records",
            data=export_leads_json(companies).encode("utf-8"),
            file_name=json_name,
            mime="application/json",
            disabled=disabled,
            width="stretch",
            icon=":material/data_object:",
            key=f"download_json_{json_name}",
        )
