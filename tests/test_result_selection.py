from lead_finder.models import Company, ScoredCompany, ScoreReason
from lead_finder.use_result_selection import (
    analyzed_cell_styles,
    crawl_filter_mode,
    eligible_flags,
    eligible_remaining,
    extend_matching_selection,
    keep_row_selection,
    parse_visual_order,
    results_editor_key,
    selected_rows,
)


def _company(org: str) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=org),
        score=1,
        reasons=[ScoreReason(label="Relevant SNI", points=1)],
    )


def test_crawled_is_true_only_after_a_successful_crawl() -> None:
    done = _company("5560000001").model_copy(update={"crawl_status": "crawled"})
    failed = _company("5560000002").model_copy(update={"crawl_status": "crawl_failed"})
    assert done.crawled is True
    assert done.model_dump()["crawled"] is True
    assert failed.crawled is False
    assert failed.model_dump()["crawled"] is False


def test_extend_skips_crawled_rows_after_the_current_selection() -> None:
    eligible = eligible_flags([False, True, False, False, True, False], "exclude")
    assert extend_matching_selection(eligible, [0], 2) == [0, 2, 3]
    assert eligible_remaining(eligible, [0]) == 3


def test_only_crawled_selects_crawled_rows() -> None:
    eligible = eligible_flags([False, True, False, True], "only")
    assert extend_matching_selection(eligible, [], 2) == [1, 3]


def test_neither_filter_selects_the_next_companies() -> None:
    assert crawl_filter_mode(False, False) == "any"
    eligible = eligible_flags([False, True, False], "any")
    assert extend_matching_selection(eligible, [], 2) == [0, 1]


def test_only_crawled_wins_when_both_filters_are_set() -> None:
    assert crawl_filter_mode(True, True) == "only"
    assert crawl_filter_mode(True, False) == "exclude"


def test_extend_starts_at_the_top_when_nothing_is_checked() -> None:
    eligible = [False, True, True, True]
    assert extend_matching_selection(eligible, [], 2) == [1, 2]


def test_extend_keeps_a_checked_crawled_row() -> None:
    eligible = [False, True]
    assert extend_matching_selection(eligible, [0], 5) == [0, 1]


def test_keep_row_selection_copies_checks_onto_the_next_table() -> None:
    state = {
        "search_result_nonce": 2,
        results_editor_key("search_result", 2): {"selection": {"rows": [1, 4], "columns": []}},
    }
    keep_row_selection(state, "search_result")
    assert state["search_result_nonce"] == 3
    assert selected_rows(state[results_editor_key("search_result", 3)]) == [1, 4]


def test_sorted_municipality_marks_the_rows_under_the_checked_one() -> None:
    # On screen: Malmö, Stockholm, Uppsala. Stockholm is checked. +1 marks Uppsala.
    eligible = [True, True, True]
    malmo_stockholm_uppsala = [1, 0, 2]
    assert extend_matching_selection(
        eligible,
        [0],
        1,
        visual_order=malmo_stockholm_uppsala,
    ) == [0, 2]


def test_extend_continues_after_the_checked_row_in_table_order() -> None:
    eligible = [True, True, True, True, True]
    visual = [3, 1, 2, 4, 0]
    assert extend_matching_selection(eligible, [2], 2, visual_order=visual) == [2, 4, 0]
    assert eligible_remaining(eligible, [2], visual_order=visual) == 2


def test_extend_skips_ineligible_rows_after_the_checked_row() -> None:
    eligible = [True, False, True, False, True]
    visual = [4, 3, 2, 1, 0]
    assert extend_matching_selection(eligible, [2], 2, visual_order=visual) == [2, 0]


def test_parse_visual_order_accepts_only_a_full_permutation() -> None:
    assert parse_visual_order("[2, 0, 1]", 3) == [2, 0, 1]
    assert parse_visual_order("", 3) == [0, 1, 2]
    assert parse_visual_order("[0, 1]", 3) == [0, 1, 2]
    assert parse_visual_order("nope", 3) == [0, 1, 2]


def test_analyzed_yes_is_thin_green_on_a_light_row() -> None:
    styles = analyzed_cell_styles(["Aquasvea", "Yes", ""], analyzed_index=1)
    assert styles[0] == "background-color: #f3faf6"
    assert "color: #2e7d32" in styles[1]
    assert "font-weight: 400" in styles[1]
    assert analyzed_cell_styles(["Aquasvea", ""], analyzed_index=1) == ["", ""]
