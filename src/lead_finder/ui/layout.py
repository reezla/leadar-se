from __future__ import annotations

import streamlit as st

SEGMENT_COLUMNS = [5, 5]
PREFIX_COLUMNS = [5, 5]
FILTER_PAIR_COLUMNS = [3, 3, 4]
FILTER_SINGLE_COLUMNS = [3, 7]
OUTREACH_COLUMNS = [2.4, 2.8, 1.0, 3.8]


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
        div[data-testid="stHorizontalBlock"]:has([class*="st-key-hide_col_"]) {
          margin-bottom: -2.35rem;
          position: relative;
          z-index: 8;
          pointer-events: none;
          gap: 0 !important;
        }
        [class*="st-key-hide_col_"] {
          display: flex;
          justify-content: center;
          pointer-events: auto;
        }
        [class*="st-key-hide_col_"] button {
          min-height: 1.25rem !important;
          height: 1.25rem !important;
          min-width: 1.25rem !important;
          padding: 0 !important;
          border: none !important;
          background: transparent !important;
          box-shadow: none !important;
          color: rgba(49, 51, 63, 0.55) !important;
          font-size: 0.95rem !important;
          line-height: 1 !important;
          cursor: pointer;
        }
        [class*="st-key-hide_col_"] button:hover {
          color: #d32f2f !important;
          background: rgba(211, 47, 47, 0.1) !important;
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
        [class*="st-key-restore_cols_"] button {
          min-height: 1.35rem !important;
          height: auto !important;
          padding: 0 0.4rem !important;
          border: none !important;
          background: transparent !important;
          box-shadow: none !important;
          font-size: 0.8rem !important;
          cursor: pointer;
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
