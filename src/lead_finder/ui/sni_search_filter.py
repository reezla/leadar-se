from __future__ import annotations

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.sni_catalog import load_sni_catalog
from lead_finder.use_analyzed_companies import sni_options
from lead_finder.use_sni_selection import format_sni_label


def render_sni_search_filter(
    companies: list[ScoredCompany],
    column: st.delta_generator.DeltaGenerator,
    *,
    session_key: str,
) -> tuple[str, ...]:
    """Multi-select of the SNI codes found in the saved companies. Empty means any."""
    options = sni_options(companies)
    counts = dict(options)
    codes = [code for code, _count in options]
    picked = st.session_state.get(session_key)
    if not isinstance(picked, list) or any(code not in counts for code in picked):
        st.session_state[session_key] = [
            code for code in (picked if isinstance(picked, list) else []) if code in counts
        ]
    catalog = load_sni_catalog()
    chosen = column.multiselect(
        "SNI",
        codes,
        key=session_key,
        placeholder="Any",
        format_func=lambda code: f"{_label(code, catalog)} ({counts.get(code, 0)})",
        help="Show companies with any of the selected SNI codes. Leave empty for all.",
    )
    return tuple(chosen)


def _label(code: str, catalog: object) -> str:
    """Show the company's own code, with the catalog name of its closest group."""
    full = format_sni_label(code, catalog)
    _, separator, name = full.partition(" — ")
    return f"{code} — {name}" if separator else code
