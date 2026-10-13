from lead_finder.use_table_page import displayed_bounds, remember_table_page, table_page


def test_table_page_shows_one_hundred_companies() -> None:
    current, pages, start, end = table_page(250, 0, size=100)
    assert (current, pages, start, end) == (0, 3, 0, 100)
    current, pages, start, end = table_page(250, 2, size=100)
    assert (current, pages, start, end) == (2, 3, 200, 250)


def test_table_page_clamps_a_page_past_the_end() -> None:
    current, pages, start, end = table_page(120, 9, size=100)
    assert (current, pages, start, end) == (1, 2, 100, 120)


def test_short_lists_stay_on_one_page() -> None:
    assert table_page(40, 3, size=100) == (0, 1, 0, 40)
    assert table_page(0, 0, size=100) == (0, 1, 0, 0)


def test_remember_table_page_stores_the_window() -> None:
    state: dict[str, object] = {"analyzed_view_page": 1}
    current, pages, start, end = remember_table_page(state, "analyzed_view", 250, size=100)
    assert (current, pages, start, end) == (1, 3, 100, 200)
    assert state["analyzed_view_page_start"] == 100
    assert state["analyzed_view_page_end"] == 200


def test_displayed_bounds_uses_the_stored_window() -> None:
    state = {"analyzed_view_page_start": 100, "analyzed_view_page_end": 200}
    assert displayed_bounds(state, "analyzed_view", 250) == (100, 200)
    assert displayed_bounds({}, "search_result", 40) == (0, 40)
