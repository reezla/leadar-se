from __future__ import annotations

import streamlit as st

from lead_finder.sni_catalog import SniGroup, load_sni_catalog
from lead_finder.use_sni_selection import (
    SNI_PREFIXES_KEY,
    add_sni_prefix,
    format_sni_label,
    parse_sni_prefixes,
    sync_sni_selection,
)


def render_sni_prefix_selector(segment_key: str, segment_prefixes: list[str]) -> list[str]:
    catalog = load_sni_catalog()
    sync_sni_selection(
        st.session_state,
        segment_key=segment_key,
        segment_prefixes=segment_prefixes,
    )
    selected = list(st.session_state.get(SNI_PREFIXES_KEY) or [])
    options = list(dict.fromkeys([*catalog.codes(), *selected]))

    chosen = st.multiselect(
        "SNI prefixes",
        options=options,
        format_func=lambda code: format_sni_label(code, catalog),
        accept_new_options=True,
        key=SNI_PREFIXES_KEY,
        placeholder="Type a custom SNI prefix",
        help=(
            "Hard filters. Click a code below to add it. "
            "Selected codes appear here and can be removed with x."
        ),
    )
    prefixes = parse_sni_prefixes(",".join(str(item) for item in chosen))

    st.caption("Click a code to add it to the search.")
    for group in catalog.groups:
        _render_catalog_group(group, prefixes)
    return prefixes


def _add_prefix(code: str) -> None:
    current = st.session_state.get(SNI_PREFIXES_KEY) or []
    st.session_state[SNI_PREFIXES_KEY] = add_sni_prefix(list(current), code)


def _render_catalog_group(group: SniGroup, selected: list[str]) -> None:
    with st.expander(group.title, expanded=group.id == "highest_fit"):
        if group.description:
            st.caption(group.description)
        columns = st.columns(2)
        for index, item in enumerate(group.codes):
            columns[index % 2].button(
                f"{item.code} — {item.name}",
                key=f"add_sni_{group.id}_{item.code}",
                help=item.why,
                disabled=item.code in selected,
                on_click=_add_prefix,
                args=(item.code,),
                use_container_width=True,
            )
