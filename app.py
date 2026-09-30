from __future__ import annotations

import streamlit as st

from lead_finder.ui import render_allabolag_tab, render_filters, render_scb_tab


def main() -> None:
    st.set_page_config(page_title="Swedish LiDAR Lead Finder", layout="wide")
    st.title("Swedish LiDAR Lead Finder")
    st.write(
        "Find and rank Swedish companies likely to benefit from handheld LiDAR scanning."
    )
    segment_key, filters = render_filters()
    scb_tab, crawl_tab = st.tabs(["SCB search", "Crawl Allabolag"])
    with scb_tab:
        render_scb_tab(segment_key, filters)
    with crawl_tab:
        render_allabolag_tab(segment_key, filters)


if __name__ == "__main__":
    main()
