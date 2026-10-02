from lead_finder.models import Company, OutreachDraft, ScoredCompany, ScoreReason
from lead_finder.ui.column_hide import hide_slot_weights
from lead_finder.ui.result_table import score_explanation
from lead_finder.ui.results import _columns, _row
from lead_finder.use_result_columns import hide_column, merge_column_order


def test_merge_starts_with_all_available_columns() -> None:
    available = ["Score", "Company", "Missing"]
    order, known = merge_column_order(available, None, None)
    assert order == available
    assert known == available


def test_merge_keeps_hidden_columns_hidden() -> None:
    available = ["Score", "Company", "Missing"]
    order, known = merge_column_order(available, ["Company", "Score"], available)
    assert order == ["Company", "Score"]
    assert known == available


def test_hide_slot_weights_include_checkbox_and_wider_company() -> None:
    weights = hide_slot_weights(["Score", "Company", "Brand"])
    assert len(weights) == 4
    assert weights[2] > weights[1]


def test_hide_column_removes_name() -> None:
    assert hide_column(["Score", "Company", "Website"], "Website") == [
        "Score",
        "Company",
    ]


def test_hide_column_keeps_the_last_column() -> None:
    assert hide_column(["Score"], "Score") == ["Score"]


def test_hide_column_ignores_unknown_name() -> None:
    assert hide_column(["Score", "Company"], "Missing") == ["Score", "Company"]


def test_merge_appends_new_columns() -> None:
    previous = ["Score", "Company", "SNI", "Missing"]
    visible = ["Company", "Score"]
    available = ["Score", "Company", "Job", "Brand", "SNI", "Missing"]
    order, known = merge_column_order(available, visible, previous)
    assert order == ["Company", "Score", "Job", "Brand"]
    assert known == available


def test_row_omits_why_and_matches_column_list() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Test AB"),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
    )
    row = _row(scored, include_match=False)
    assert "Why" not in row
    assert list(row) == _columns(include_match=False)
    assert "Website" in row
    assert row["Email"] == ""


def test_row_strips_anstallda_from_employees() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="5561234567",
            name="Test AB",
            employee_class="20-49 anställda",
        ),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
    )
    assert _row(scored, include_match=False)["Employees"] == "20-49"


def test_outreach_row_includes_fit() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Inclined Labs AB"),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
        outreach=OutreachDraft(
            subject="indoor flight",
            body="Hej,",
            status="drafted",
            customer_fit="weak",
            suggested_recipient="info@inclined.ws",
        ),
    )
    row = _row(scored, include_match=False, include_outreach=True)
    assert row["Fit"] == "weak"
    assert row["Email"] == "info@inclined.ws"
    assert row["Email body"] == "Hej,"
    assert list(row) == _columns(include_match=False, include_outreach=True)


def test_score_cell_is_the_number_only() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Test AB"),
        score=65,
        reasons=[
            ScoreReason(label="Relevant SNI 68201", points=40),
            ScoreReason(label="Company size indicates purchasing capacity", points=25),
        ],
    )
    assert _row(scored, include_match=False)["Score"] == 65
    assert score_explanation(scored) == [
        "Relevant SNI 68201 (+40)",
        "Company size indicates purchasing capacity (+25)",
    ]
