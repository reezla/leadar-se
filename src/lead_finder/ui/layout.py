from __future__ import annotations

import streamlit as st

SEGMENT_COLUMNS = [5, 5]
PREFIX_COLUMNS = [5, 5]
FILTER_PAIR_COLUMNS = [3, 3, 4]
FILTER_SINGLE_COLUMNS = [3, 7]


def inject_layout_styles() -> None:
    st.markdown(
        """
        <style>
        [class*="st-key-add_sni_"] [data-testid="stTooltipHoverTarget"] {
          justify-content: flex-start !important;
          text-align: left !important;
        }
        [class*="st-key-add_sni_"] {
          width: 78%;
        }
        [class*="st-key-add_sni_"] button,
        [class*="st-key-add_sni_"] button * {
          justify-content: flex-start !important;
          text-align: left !important;
        }
        [class*="st-key-add_sni_"] button {
          width: 100% !important;
          height: auto !important;
          overflow: hidden;
        }
        [class*="st-key-add_sni_"] button > div,
        [class*="st-key-add_sni_"] button > div > span,
        [class*="st-key-add_sni_"] [data-testid="stMarkdownContainer"] {
          width: 100%;
          min-width: 0;
          overflow: hidden;
        }
        [class*="st-key-add_sni_"] [data-testid="stMarkdownContainer"] p {
          display: block;
          width: 100%;
          margin: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        [class*="st-key-add_sni_"] {
          position: relative;
        }
        [class*="st-key-add_sni_"]:hover [data-testid="stMarkdownContainer"] p {
          position: absolute;
          left: 0;
          top: 0;
          z-index: 40;
          width: max-content;
          max-width: min(70vw, 48rem);
          padding: 0.45rem 0.75rem;
          overflow: visible;
          text-overflow: unset;
          white-space: normal;
          background: var(--background-color, #ffffff);
          border: 1px solid rgba(49, 51, 63, 0.2);
          border-radius: 0.5rem;
          box-shadow: 0 4px 16px rgba(49, 51, 63, 0.15);
        }
        [class*="st-key-sni_prefixes"] [role="group"] {
          max-height: none !important;
          height: auto !important;
        }
        [class*="st-key-sni_prefixes"] [data-testid="stMultiSelectTagsContainer"] {
          flex-wrap: wrap !important;
          align-items: flex-start !important;
          overflow: visible !important;
          max-height: none !important;
          height: auto !important;
        }
        [class*="st-key-sni_prefixes"] [aria-label="Selected values"] {
          flex-wrap: wrap !important;
        }
        [class*="st-key-sni_prefixes"] [data-testid="stMultiSelectTagsContainer"] span[title] {
          white-space: normal !important;
        }
        [class*="st-key-export_menu_"] button,
        [class*="st-key-download_csv_"] button,
        [class*="st-key-download_json_"] button {
          min-height: 2.75rem;
          cursor: pointer;
        }
        [class*="st-key-select_cluster_"] {
          width: max-content !important;
          max-width: 100% !important;
          justify-content: flex-start !important;
          align-items: center !important;
          gap: 0.45rem !important;
        }
        [class*="st-key-select_cluster_"] [class*="st-key-select_more_"],
        [class*="st-key-select_cluster_"] [class*="st-key-crawl_filter_"],
        [class*="st-key-select_cluster_"] [class*="st-key-mark_next_"] {
          flex: 0 0 auto !important;
          width: auto !important;
        }
        [class*="st-key-select_cluster_"] [class*="st-key-mark_next_"] {
          margin-right: calc(1.5rem - 0.45rem) !important;
        }
        [class*="st-key-mark_next_"] [data-testid="stText"] {
          white-space: nowrap;
        }
        [data-testid="stElementContainer"][class*="st-key-refresh_rows"],
        [data-testid="stElementContainer"][class*="st-key-table_order_"],
        [data-testid="stElementContainer"]:has([id^="table-order-bridge"]) {
          position: absolute !important;
          width: 1px !important;
          height: 1px !important;
          margin: 0 !important;
          padding: 0 !important;
          overflow: hidden !important;
          clip: rect(0, 0, 0, 0) !important;
          opacity: 0 !important;
        }
        [class*="st-key-select_more_"] button {
          width: auto !important;
          min-width: 3rem;
        }
        [class*="st-key-table_pager_"] {
          gap: 0.25rem !important;
          align-items: center !important;
        }
        [class*="st-key-table_pager_"] [data-testid="stElementContainer"] {
          margin: 0 !important;
          width: auto !important;
        }
        [class*="st-key-page_pick_"] {
          width: 5.5rem !important;
          min-width: 5.5rem !important;
        }
        [data-testid="stToastContainer"] {
          position: fixed !important;
          top: auto !important;
          right: auto !important;
          bottom: 1.5rem !important;
          left: 50% !important;
          transform: translateX(-50%) !important;
          width: min(32rem, calc(100vw - 2rem));
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
