from __future__ import annotations

from typing import Any

import streamlit as st

_PENDING_KEY = "score_popup_pending"


def open_score_popup_if_clicked(
    selection: Any,
    rows: list[dict[str, object]],
    explanations: list[list[str]],
    *,
    widget_key: str,
) -> None:
    pending = st.session_state.get(_PENDING_KEY)
    cells = _cells(selection)
    if cells:
        row_index, column = cells[0]
        if column == "Score" and 0 <= row_index < len(rows):
            pending = {
                "company": rows[row_index].get("Company") or "",
                "score": rows[row_index].get("Score") or 0,
                "lines": explanations[row_index] if row_index < len(explanations) else [],
                "widget_key": widget_key,
            }
            st.session_state[_PENDING_KEY] = pending
    if isinstance(pending, dict) and pending.get("widget_key"):
        render_score_popup(
            str(pending.get("company") or ""),
            int(pending.get("score") or 0),
            list(pending.get("lines") or []),
        )


def _clear_pending() -> None:
    pending = st.session_state.get(_PENDING_KEY)
    widget_key = pending.get("widget_key") if isinstance(pending, dict) else None
    st.session_state[_PENDING_KEY] = None
    if isinstance(widget_key, str):
        _clear_cells(widget_key)


def _clear_cells(widget_key: str) -> None:
    state = st.session_state.get(widget_key)
    payload = getattr(state, "selection", None)
    if payload is None and isinstance(state, dict):
        payload = state.get("selection")
    rows = _selection_values(payload, "rows")
    columns = _selection_values(payload, "columns")
    st.session_state[widget_key] = {
        "selection": {"rows": rows, "columns": columns, "cells": []}
    }


def _selection_values(payload: Any, key: str) -> list[Any]:
    if payload is None:
        return []
    values = getattr(payload, key, None)
    if values is None and isinstance(payload, dict):
        values = payload.get(key)
    return list(values or [])


def _cells(selection: Any) -> list[tuple[int, str]]:
    payload = getattr(selection, "selection", selection)
    cells = getattr(payload, "cells", None)
    if cells is None and isinstance(payload, dict):
        cells = payload.get("cells")
    return [(int(row), str(column)) for row, column in cells or []]


@st.dialog("Score", on_dismiss=_clear_pending)
def render_score_popup(company: str, score: int, lines: list[str]) -> None:
    st.metric(company or "Company", score)
    for line in lines:
        st.caption(line)
    if st.button("Close", key="score_popup_close"):
        _clear_pending()
        st.rerun()
