from __future__ import annotations

from collections.abc import MutableMapping

PAGE_SIZE = 100


def table_page(count: int, page: int, *, size: int) -> tuple[int, int, int, int]:
    if count <= 0:
        return 0, 1, 0, 0
    if size <= 0 or count <= size:
        return 0, 1, 0, count
    pages = (count + size - 1) // size
    current = min(max(page, 0), pages - 1)
    start = current * size
    return current, pages, start, min(start + size, count)


def remember_table_page(
    state: MutableMapping[str, object],
    session_key: str,
    count: int,
    *,
    size: int | None,
) -> tuple[int, int, int, int]:
    if not size:
        state.pop(f"{session_key}_page_start", None)
        state.pop(f"{session_key}_page_end", None)
        return 0, 1, 0, count
    current, pages, start, end = table_page(
        count,
        int(state.get(f"{session_key}_page") or 0),
        size=size,
    )
    state[f"{session_key}_page"] = current
    state[f"{session_key}_page_start"] = start
    state[f"{session_key}_page_end"] = end
    return current, pages, start, end


def displayed_bounds(
    state: MutableMapping[str, object],
    session_key: str,
    count: int,
) -> tuple[int, int]:
    end = state.get(f"{session_key}_page_end")
    if not isinstance(end, int):
        return 0, count
    start = int(state.get(f"{session_key}_page_start") or 0)
    end = min(max(end, 0), count)
    start = min(max(start, 0), end)
    return start, end
