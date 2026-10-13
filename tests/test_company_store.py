import json

import httpx

from lead_finder.company_store_client import HttpCompanyStore
from lead_finder.models import (
    Company,
    CompanySearchFilters,
    ScoredCompany,
    ScoreReason,
    WebsiteProfile,
)
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_company_store import company_row, crawl_patch, enriched_row, query_key


def test_query_key_ignores_filter_order() -> None:
    left = CompanySearchFilters(
        sni_prefixes=["42", "41"],
        counties=["Skåne", "Västra Götaland"],
    )
    right = CompanySearchFilters(
        sni_prefixes=["41", "42"],
        counties=["Västra Götaland", "Skåne"],
    )
    assert query_key("lidar", left) == query_key("lidar", right)


def test_query_key_changes_when_the_sni_list_changes() -> None:
    base = CompanySearchFilters(sni_prefixes=["41"])
    wider = CompanySearchFilters(sni_prefixes=["41", "42"])
    assert query_key("lidar", base) != query_key("lidar", wider)


def test_company_row_keeps_scb_fields_and_leaves_crawl_fields_out() -> None:
    row = company_row(_scored(domain="https://example.se", website=_profile()))
    assert row["organization_number"] == "5560000001"
    assert row["score"] == 4
    assert row["sni_codes"] == ["71110"]
    assert "domain" not in row
    assert "website" not in row
    assert "crawl_status" not in row
    assert "crawl_detail" not in row


def test_crawl_patch_drops_null_bytes_postgres_cannot_store() -> None:
    profile = _profile().model_copy(update={"about_text": "Berg\x00schöld"})
    scored = _scored(website=profile).model_copy(update={"crawl_detail": "note\x00"})
    patch = crawl_patch(scored)
    assert patch["about_text"] == "Bergschöld"
    assert patch["crawl_detail"] == "note"


def test_crawl_patch_saves_about_projects_and_email() -> None:
    patch = crawl_patch(_scored(domain="https://example.se", website=_profile()))
    assert patch["about_text"] == "Builds bridges"
    assert patch["projects_text"] == "E4 bridge"
    assert patch["pages_fetched"] == ["https://example.se/projekt"]
    assert patch["website_source"] == "google"
    assert patch["suggested_recipient"] == "hello@example.se"
    assert patch["domain"] == "https://example.se"
    assert patch["crawl_status"] == "crawled"
    assert "website" not in patch
    assert "name" not in patch
    assert "score" not in patch


def test_save_search_upserts_companies_then_records_the_query() -> None:
    seen, store = _store()
    outcome = store.save_search(_result(), _filters(), "lidar")
    assert outcome.error == ""
    company_post, lookup, search_post = seen
    assert company_post.method == "POST"
    assert company_post.url.path.endswith("/companies")
    body = json.loads(company_post.content)
    assert "domain" not in body[0]
    assert "website" not in body[0]
    assert body[0]["name"] == "Example AB"
    assert "resolution=merge-duplicates" in company_post.headers["prefer"]
    assert company_post.headers["apikey"] == "sb_secret_test"
    assert company_post.headers["user-agent"] == "lead-finder"
    assert "authorization" not in company_post.headers
    assert lookup.method == "GET"
    recorded = json.loads(search_post.content)
    assert recorded["run_count"] == 1
    assert recorded["saved_count"] == 1
    assert recorded["sni_prefixes"] == ["41", "42"]
    assert recorded["query_key"] == query_key("lidar", _filters())


def test_repeated_search_increments_run_count() -> None:
    seen, store = _store(
        lookup=[{"run_count": 2, "first_searched_at": "2026-01-01T00:00:00+00:00"}]
    )
    outcome = store.save_search(_result(), _filters(), "lidar")
    assert outcome.error == ""
    recorded = json.loads(seen[-1].content)
    assert recorded["run_count"] == 3
    assert recorded["first_searched_at"] == "2026-01-01T00:00:00+00:00"


def test_failed_company_save_does_not_record_the_query() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(500, text="nope")

    store = HttpCompanyStore(
        "http://supabase.test",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    outcome = store.save_search(_result(), _filters(), "lidar")
    assert outcome.error
    assert seen
    assert all("company_searches" not in request.url.path for request in seen)


def test_empty_search_records_the_query_without_a_company_upsert() -> None:
    seen, store = _store()
    outcome = store.save_search(_result(companies=[]), _filters(), "lidar")
    assert outcome.error == ""
    assert [request.method for request in seen] == ["GET", "POST"]
    assert seen[-1].url.path.endswith("/company_searches")


def test_save_companies_inserts_the_company_and_domain() -> None:
    seen, store = _store()
    scored = _scored(domain="https://example.se", website=_profile())
    outcome = store.save_companies([scored], include_crawl=False)
    assert outcome.error == ""
    body = json.loads(seen[0].content)[0]
    assert seen[0].method == "POST"
    assert seen[0].url.params["on_conflict"] == "organization_number"
    assert body["name"] == "Example AB"
    assert body["domain"] == "https://example.se"
    assert "website" not in body
    assert "crawl_status" not in body


def test_crawl_save_updates_the_company_with_website_text() -> None:
    seen, store = _store()
    outcome = store.patch_crawl(_scored(domain="https://example.se", website=_profile()))
    assert outcome.error == ""
    body = json.loads(seen[0].content)[0]
    assert body["name"] == "Example AB"
    assert body["domain"] == "https://example.se"
    assert body["crawl_status"] == "crawled"
    assert body["about_text"] == "Builds bridges"
    assert body["projects_text"] == "E4 bridge"
    assert body["suggested_recipient"] == "hello@example.se"
    assert "website" not in body


def test_delete_companies_removes_rows_by_organization_number() -> None:
    seen, store = _store()
    outcome = store.delete_companies(["556000-0001", "5560000001"])
    assert outcome.error == ""
    request = seen[0]
    assert request.method == "DELETE"
    assert request.url.path.endswith("/companies")
    assert request.url.params["organization_number"] == "in.(5560000001)"
    assert request.headers["prefer"] == "return=minimal"


def test_delete_companies_with_no_ids_does_not_call_supabase() -> None:
    seen, store = _store()
    outcome = store.delete_companies([])
    assert outcome.error == ""
    assert seen == []


def test_delete_companies_rejects_a_short_organization_number() -> None:
    seen, store = _store()
    outcome = store.delete_companies(["5560000001", "12"])
    assert outcome.error
    assert seen == []


def test_delete_companies_reports_a_supabase_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(403, text="permission denied")

    store = HttpCompanyStore(
        "http://supabase.test",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    outcome = store.delete_companies(["5560000001"])
    assert "403" in outcome.error


def test_delete_companies_chunks_large_selections() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    store = HttpCompanyStore(
        "http://supabase.test",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    outcome = store.delete_companies([f"{index:010d}" for index in range(201)])
    assert outcome.error == ""
    assert len(seen) == 2
    first = seen[0].url.params["organization_number"]
    assert first.startswith("in.(")
    assert first.count(",") == 199


def test_enriched_row_leaves_crawl_off_until_requested() -> None:
    scored = _scored(domain="https://example.se", website=_profile())
    plain = enriched_row(scored, include_crawl=False)
    assert plain["domain"] == "https://example.se"
    assert "about_text" not in plain
    assert "website" not in plain
    full = enriched_row(scored, include_crawl=True)
    assert full["projects_text"] == "E4 bridge"
    assert "website" not in full


def _filters() -> CompanySearchFilters:
    return CompanySearchFilters(
        sni_prefixes=["42", "41"],
        counties=["Skåne", "Västra Götaland"],
        limit=500,
    )


def _result(companies: list[ScoredCompany] | None = None) -> SearchResult:
    rows = [_scored()] if companies is None else companies
    return SearchResult(
        companies=rows,
        summary=SearchSummary(fetched=3, matched=len(rows), incomplete=0),
    )


def _scored(
    *,
    domain: str | None = "https://example.se",
    website: WebsiteProfile | None = None,
) -> ScoredCompany:
    return ScoredCompany(
        company=Company(
            organization_number="556000-0001",
            name="Example AB",
            sni_codes=["71110"],
            domain=domain,
        ),
        score=4,
        reasons=[ScoreReason(label="Relevant SNI", points=4)],
        missing_data=["revenue"],
        website=website,
        crawl_status="crawled" if website else None,
    )


def _profile() -> WebsiteProfile:
    return WebsiteProfile(
        url="https://example.se",
        about_text="Builds bridges",
        projects_text="E4 bridge",
        pages_fetched=["https://example.se/projekt"],
        suggested_recipient="hello@example.se",
    )


def _store(
    lookup: list[dict[str, object]] | None = None,
) -> tuple[list[httpx.Request], HttpCompanyStore]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/company_searches") and request.method == "GET":
            return httpx.Response(200, json=[] if lookup is None else lookup)
        return httpx.Response(201)

    store = HttpCompanyStore(
        "http://supabase.test",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    return seen, store
