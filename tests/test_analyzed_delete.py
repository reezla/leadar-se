from lead_finder.models import Company, ScoredCompany, ScoreReason
from lead_finder.ui.delete_companies import company_list_html
from lead_finder.use_analyzed_delete import (
    delete_targets,
    forget_deleted_companies,
    without_organizations,
)
from lead_finder.use_company_search import SearchResult, SearchSummary


def test_delete_targets_label_each_selected_company_once() -> None:
    targets = delete_targets(
        [
            _company("5560000001", "Alpha AB"),
            _company("5560000001", "Alpha AB"),
            _company("5560000002", "  "),
        ]
    )
    assert targets == [
        {"organization_number": "5560000001", "label": "Alpha AB (5560000001)"},
        {"organization_number": "5560000002", "label": "5560000002"},
    ]


def test_without_organizations_drops_selected_rows_and_updates_the_summary() -> None:
    result = _result(
        [
            _company("5560000001", "Alpha AB", missing=True),
            _company("5560000002", "Beta AB"),
        ]
    )
    kept = without_organizations(result, {"5560000001"})
    assert [item.company.name for item in kept.companies] == ["Beta AB"]
    assert kept.summary.fetched == 1
    assert kept.summary.incomplete == 0


def test_forget_deleted_companies_updates_both_lists_and_clears_that_sheet() -> None:
    state: dict[str, object] = {
        "analyzed_companies": _result(
            [_company("5560000001", "Alpha AB"), _company("5560000002", "Beta AB")]
        ),
        "analyzed_view": _result([_company("5560000001", "Alpha AB")]),
        "analyzed_view_display_org": "5560000001",
        "sheet_pick_analyzed_view": "5560000001",
        "analyzed_view_outreach_orgs": ["5560000001", "5560000002"],
        "analyzed_view_nonce": 2,
    }
    forget_deleted_companies(
        state,
        session_key="analyzed_view",
        catalog_key="analyzed_companies",
        organization_numbers={"5560000001"},
    )
    full = state["analyzed_companies"]
    view = state["analyzed_view"]
    assert isinstance(full, SearchResult)
    assert isinstance(view, SearchResult)
    assert [item.company.name for item in full.companies] == ["Beta AB"]
    assert view.companies == []
    assert "analyzed_view_display_org" not in state
    assert "sheet_pick_analyzed_view" not in state
    assert state["analyzed_view_outreach_orgs"] == ["5560000002"]
    assert state["analyzed_view_nonce"] == 3


def test_company_list_scrolls_inside_10rem_and_escapes_names() -> None:
    markup = company_list_html(["Alpha AB", "<Beta>"])
    assert "max-height:10rem" in markup
    assert "overflow-y:auto" in markup
    assert "Alpha AB" in markup
    assert "&lt;Beta&gt;" in markup
    assert "<Beta>" not in markup


def _company(org: str, name: str, *, missing: bool = False) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=name),
        score=1,
        reasons=[ScoreReason(label="Relevant SNI", points=1)],
        missing_data=["revenue"] if missing else [],
    )


def _result(companies: list[ScoredCompany]) -> SearchResult:
    return SearchResult(
        companies=companies,
        summary=SearchSummary(
            fetched=len(companies),
            matched=len(companies),
            incomplete=sum(bool(item.missing_data) for item in companies),
        ),
    )
