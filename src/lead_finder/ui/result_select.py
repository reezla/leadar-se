from __future__ import annotations

import streamlit as st

from lead_finder.use_result_selection import (
    SELECT_STEPS,
    crawl_filter_mode,
    eligible_flags,
    eligible_remaining,
    extend_matching_selection,
    selected_rows,
    selection_state,
)


def render_select_more(
    crawled: list[bool],
    *,
    widget_key: str,
    session_key: str,
    visual_order: list[int] | None = None,
) -> None:
    exclude_key, only_key = _filter_keys(session_key)
    if exclude_key not in st.session_state and only_key not in st.session_state:
        st.session_state[exclude_key] = True
    mode = crawl_filter_mode(
        bool(st.session_state.get(exclude_key)),
        bool(st.session_state.get(only_key)),
    )
    current = selected_rows(st.session_state.get(widget_key))
    eligible = eligible_flags(crawled, mode)
    remaining = eligible_remaining(eligible, current, visual_order=visual_order)
    with st.container(
        horizontal=True,
        vertical_alignment="center",
        width="content",
        gap="small",
        key=f"select_cluster_{session_key}",
    ):
        with st.container(key=f"mark_next_{session_key}", width="content"):
            st.text("Mark next:")
        for count in SELECT_STEPS:
            if st.button(
                f"+{count}",
                key=f"select_more_{count}_{widget_key}",
                disabled=remaining <= 0,
                help=_help(count, mode),
            ):
                st.session_state[widget_key] = selection_state(
                    extend_matching_selection(
                        eligible,
                        current,
                        count,
                        visual_order=visual_order,
                    )
                )
                st.rerun()
        st.checkbox(
            "Exclude crawled",
            key=exclude_key,
            on_change=_keep_single_filter,
            args=(exclude_key, only_key),
        )
        st.checkbox(
            "Only crawled",
            key=only_key,
            on_change=_keep_single_filter,
            args=(only_key, exclude_key),
        )


def _filter_keys(session_key: str) -> tuple[str, str]:
    return f"crawl_filter_exclude_{session_key}", f"crawl_filter_only_{session_key}"


def _keep_single_filter(active_key: str, other_key: str) -> None:
    if st.session_state.get(active_key):
        st.session_state[other_key] = False


def _help(count: int, mode: str) -> str:
    if mode == "only":
        target = "crawled companies"
    elif mode == "exclude":
        target = "companies that have not been crawled"
    else:
        target = "companies"
    return (
        f"Check the next {count} {target} after the checked row, in the order the table is showing."
    )
