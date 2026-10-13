from __future__ import annotations

import streamlit as st


def render_table_pager(
    session_key: str,
    *,
    page: int,
    pages: int,
    start: int,
    end: int,
    total: int,
) -> None:
    if pages <= 1:
        return
    pick_key = f"page_pick_{session_key}"
    if st.session_state.get(pick_key) != page + 1:
        st.session_state[pick_key] = page + 1
    with st.container(
        horizontal=True,
        vertical_alignment="center",
        gap=4,
        width="content",
        key=f"table_pager_{session_key}",
    ):
        st.button(
            "Previous",
            disabled=page <= 0,
            width="content",
            key=f"page_prev_{session_key}",
            on_click=_set_page,
            args=(session_key, page - 1),
        )
        st.selectbox(
            "Page",
            list(range(1, pages + 1)),
            label_visibility="collapsed",
            width=88,
            key=pick_key,
            on_change=_choose_page,
            args=(session_key,),
        )
        st.button(
            "Next",
            disabled=page >= pages - 1,
            width="content",
            key=f"page_next_{session_key}",
            on_click=_set_page,
            args=(session_key, page + 1),
        )
        st.caption(f"{start + 1}–{end} of {total}", width="content")


def _set_page(session_key: str, new_page: int) -> None:
    st.session_state[f"{session_key}_page"] = new_page
    st.session_state[f"page_pick_{session_key}"] = new_page + 1


def _choose_page(session_key: str) -> None:
    chosen = st.session_state.get(f"page_pick_{session_key}")
    if isinstance(chosen, int):
        st.session_state[f"{session_key}_page"] = chosen - 1
