from lead_finder.exporters.leads_json import export_leads_json
from lead_finder.models import Company, OutreachDraft, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_email_desk import (
    desk_companies,
    draft_status,
    load_saved_leads,
    seed_email_selection,
    selected_org_numbers,
    source_entries,
)
from lead_finder.use_result_selection import results_editor_key, selection_state


def _company(org: str, name: str) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=name),
        score=10,
        reasons=[ScoreReason(label="Relevant SNI", points=10)],
    )


def _crawled(org: str, name: str, *, url: str | None) -> ScoredCompany:
    profile = None if url is None else WebsiteProfile(url=url, about_text="Om oss")
    company = _company(org, name).company.model_copy(update={"domain": url})
    return _company(org, name).model_copy(
        update={
            "company": company,
            "website": profile,
            "crawl_status": "crawled" if url else "no_website",
        }
    )


def _result(*companies: ScoredCompany) -> SearchResult:
    return SearchResult(
        companies=list(companies),
        summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
    )


def test_source_entries_keep_lists_that_have_companies() -> None:
    scb = _result(_company("5560000001", "Alpha"))
    empty = _result()
    state = {"search_result": scb, "allabolag_result": empty, "other": object()}
    assert source_entries(state) == [("search_result", "SCB search", scb)]


def test_desk_companies_include_rows_that_were_never_crawled() -> None:
    pending = _company("5560000001", "Alpha")
    ready = _crawled("5560000002", "Beta", url="https://beta.se")
    found = desk_companies(_result(pending, ready))
    assert [item.company.name for item in found] == ["Alpha", "Beta"]


def test_draft_status_and_table_row() -> None:
    ready = _crawled("5560000002", "Beta", url="https://beta.se")
    missing = _crawled("5560000003", "Gamma", url=None)
    drafted = ready.model_copy(
        update={"outreach": OutreachDraft(subject="lidar", body="Hej,", customer_fit="moderate")}
    )
    assert draft_status(ready) == "Ready"
    assert draft_status(missing) == "No website"
    assert draft_status(drafted) == "Drafted"


def test_seed_email_selection_uses_the_search_table_once() -> None:
    pending = _company("5560000001", "Alpha")
    ready = _crawled("5560000002", "Beta", url="https://beta.se")
    result = _result(pending, ready)
    state: dict[str, object] = {
        "search_result_nonce": 0,
        results_editor_key("search_result", 0): selection_state([0, 1]),
    }
    seed_email_selection(state, "search_result", result, desk_companies(result))
    assert state["email_pick_search_result"] == selection_state([0, 1])
    state["email_pick_search_result"] = selection_state([])
    seed_email_selection(state, "search_result", result, desk_companies(result))
    assert state["email_pick_search_result"] == selection_state([])


def test_load_saved_leads_reads_an_export_and_a_company_list() -> None:
    exported = _result(
        _crawled("5560000002", "Beta", url="https://beta.se"),
        _company("5560000001", "Alpha"),
    )
    loaded = load_saved_leads(export_leads_json(exported.companies))
    by_name = {item.company.name: item for item in loaded.companies}
    assert set(by_name) == {"Alpha", "Beta"}
    assert by_name["Beta"].website is not None
    assert by_name["Beta"].website.url == "https://beta.se"
    assert by_name["Alpha"].website is None

    bare = load_saved_leads(
        '[{"organization_number": "556000-0001", "name": "Alpha AB"}]'
    )
    assert bare.companies[0].company.organization_number == "5560000001"
    assert bare.companies[0].company.name == "Alpha AB"
    assert source_entries({"uploaded_result": bare})[0][1] == "Uploaded file"


def test_load_saved_leads_rejects_bad_files() -> None:
    try:
        load_saved_leads("{")
    except ValueError as error:
        assert "not valid JSON" in str(error)
    else:
        raise AssertionError("invalid JSON was accepted")
    try:
        load_saved_leads('{"companies": []}')
    except ValueError as error:
        assert "no companies" in str(error)
    else:
        raise AssertionError("empty file was accepted")


def test_selected_org_numbers_ignore_bad_indexes() -> None:
    rows = [
        _crawled("5560000002", "Beta", url="https://beta.se"),
        _crawled("5560000003", "Gamma", url=None),
    ]
    assert selected_org_numbers(rows, [1, 1, 9, -1]) == ["5560000003"]
