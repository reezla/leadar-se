from __future__ import annotations

import streamlit as st


def use_result_columns(available: list[str], *, state_key: str) -> list[str]:
    order, known = merge_column_order(
        available,
        st.session_state.get(state_key),
        st.session_state.get(f"{state_key}_known"),
    )
    st.session_state[state_key] = order
    st.session_state[f"{state_key}_known"] = known
    return order


def merge_column_order(
    available: list[str],
    stored: list[str] | None,
    known: list[str] | None,
) -> tuple[list[str], list[str]]:
    if stored is None:
        return list(available), list(available)
    kept = [name for name in stored if name in available]
    newcomers = [name for name in available if name not in (known or []) and name not in kept]
    return [*kept, *newcomers], list(available)


def hide_column(order: list[str], name: str) -> list[str]:
    if name not in order or len(order) <= 1:
        return list(order)
    return [item for item in order if item != name]
