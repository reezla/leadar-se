from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402

from lead_finder.ui import render_allabolag_tab, render_filters, render_scb_tab  # noqa: E402
from lead_finder.ui.analyzed_tab import render_analyzed_tab  # noqa: E402
from lead_finder.ui.email_page import render_email_page  # noqa: E402
from lead_finder.ui.layout import inject_layout_styles  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="Swedish LiDAR Lead Finder", layout="wide")
    inject_layout_styles()
    search = st.Page(
        _search_page,
        title="Find companies",
        icon=":material/search:",
        default=True,
    )
    emails = st.Page(
        render_email_page,
        title="Write emails",
        icon=":material/mail:",
        url_path="emails",
    )
    st.navigation([search, emails], position="top").run()


def _search_page() -> None:
    st.title("Swedish LiDAR Lead Finder")
    st.write(
        "Find and rank Swedish companies likely to benefit from handheld LiDAR scanning."
    )
    if _view_picker() == "Analyzed data":
        render_analyzed_tab()
        return
    segment_key, filters = render_filters()
    scb_tab, crawl_tab = st.tabs(["SCB search", "Crawl Allabolag"])
    with scb_tab:
        render_scb_tab(segment_key, filters)
    with crawl_tab:
        render_allabolag_tab(segment_key, filters)


def _view_picker() -> str:
    if "finder_view" not in st.session_state:
        current = st.query_params.get("view")
        st.session_state["finder_view"] = (
            "Analyzed data" if current == "analyzed" else "Search"
        )
    choice = st.segmented_control(
        "Choose a view",
        ["Search", "Analyzed data"],
        key="finder_view",
        required=True,
    )
    selected = choice or "Search"
    token = "analyzed" if selected == "Analyzed data" else "search"
    if st.query_params.get("view") != token:
        st.query_params["view"] = token
    return selected


if __name__ == "__main__":
    main()
