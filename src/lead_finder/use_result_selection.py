from __future__ import annotations

import json
from collections.abc import MutableMapping
from typing import Any

SELECT_STEPS = (5, 10, 20)
_ROW_TINT = "background-color: #f3faf6"
_ANALYZED_YES = f"{_ROW_TINT}; color: #2e7d32; font-weight: 400"


def results_editor_key(session_key: str, nonce: int) -> str:
    return f"results_editor_{session_key}_{nonce}"


def table_order_key(session_key: str) -> str:
    return f"table_order_{session_key}"


def selected_rows(state: object) -> list[int]:
    payload = getattr(state, "selection", None)
    if payload is None and isinstance(state, dict):
        payload = state.get("selection")
    rows = getattr(payload, "rows", None)
    if rows is None and isinstance(payload, dict):
        rows = payload.get("rows")
    return [int(row) for row in rows or []]


def selection_state(rows: list[int]) -> dict[str, object]:
    return {"selection": {"rows": list(rows), "columns": [], "cells": []}}


def keep_row_selection(state: MutableMapping[str, Any], session_key: str) -> None:
    nonce_key = f"{session_key}_nonce"
    old_nonce = int(state.get(nonce_key) or 0)
    rows = selected_rows(state.get(results_editor_key(session_key, old_nonce)))
    new_nonce = old_nonce + 1
    state[nonce_key] = new_nonce
    state[results_editor_key(session_key, new_nonce)] = selection_state(rows)


def crawl_filter_mode(exclude_crawled: bool, only_crawled: bool) -> str:
    if only_crawled:
        return "only"
    if exclude_crawled:
        return "exclude"
    return "any"


def eligible_flags(crawled: list[bool], mode: str) -> list[bool]:
    if mode == "only":
        return list(crawled)
    if mode == "exclude":
        return [not item for item in crawled]
    return [True] * len(crawled)


def extend_matching_selection(
    eligible: list[bool],
    selected: list[int],
    count: int,
    *,
    visual_order: list[int] | None = None,
) -> list[int]:
    order = _visual_order(len(eligible), visual_order)
    kept, start = _cursor(order, selected)
    if count <= 0:
        return kept
    chosen = list(kept)
    already = set(chosen)
    added = 0
    for index in order[start:]:
        if index in already or not eligible[index]:
            continue
        chosen.append(index)
        already.add(index)
        added += 1
        if added >= count:
            break
    return chosen


def eligible_remaining(
    eligible: list[bool],
    selected: list[int],
    *,
    visual_order: list[int] | None = None,
) -> int:
    order = _visual_order(len(eligible), visual_order)
    _, start = _cursor(order, selected)
    return sum(1 for index in order[start:] if eligible[index])


def parse_visual_order(raw: object, row_count: int) -> list[int]:
    if not isinstance(raw, str) or not raw.strip():
        return list(range(row_count))
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return list(range(row_count))
    return _visual_order(row_count, parsed if isinstance(parsed, list) else None)


def analyzed_cell_styles(values: list[object], *, analyzed_index: int | None) -> list[str]:
    if analyzed_index is None or not 0 <= analyzed_index < len(values):
        return [""] * len(values)
    if values[analyzed_index] != "Yes":
        return [""] * len(values)
    styles = [_ROW_TINT] * len(values)
    styles[analyzed_index] = _ANALYZED_YES
    return styles


def _visual_order(limit: int, visual_order: list[int] | None) -> list[int]:
    if _is_permutation(visual_order, limit):
        return [int(index) for index in visual_order or []]
    return list(range(limit))


def _is_permutation(value: object, limit: int) -> bool:
    if not isinstance(value, list) or len(value) != limit:
        return False
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        return False
    return sorted(value) == list(range(limit))


def _cursor(order: list[int], selected: list[int]) -> tuple[list[int], int]:
    place = {origin: position for position, origin in enumerate(order)}
    kept = [index for index in dict.fromkeys(selected) if index in place]
    start = max(place[index] for index in kept) + 1 if kept else 0
    return kept, start
