from dataclasses import replace
from datetime import UTC, datetime

import httpx

from lead_finder.company_store_client import HttpCompanyStore
from lead_finder.models import Company, ScoredCompany, ScoreReason
from lead_finder.sni_catalog import SniCatalog, SniCode, SniGroup
from lead_finder.use_analyzed_companies import (
    AnalyzedFilters,
    filter_analyzed,
    merge_analyzed,
)
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_company_store import SavedSearch, scored_from_store_row
from lead_finder.use_saved_search import format_saved_search, format_sni_search


def test_store_row_becomes_a_company_with_crawl_fields() -> None:
    scored = scored_from_store_row(
        {
            "organization_number": "5563907392",
            "name": "AKTIEBOLAG KARTVERKSTAN",
            "sni_codes": ["71121"],
            "municipality": "Tyresö",
            "county": "Stockholm",
            "employee_class": "10-19 anställda",
            "active": True,
            "source": "SCB Företagsregistret",
            "retrieved_at": "2026-10-08T08:34:23.905157Z",
            "score": 90,
            "score_reasons": [{"label": "Relevant SNI 71121", "points": 45}],
            "missing_data": ["revenue"],
            "domain": "https://kartverkstan.se/kontakta-oss/",
            "about_text": "Kontakta oss",
            "projects_text": None,
            "pages_fetched": ["https://kartverkstan.se/kontakta-oss/"],
            "website_source": "existing_domain",
            "suggested_recipient": "info@kartverkstan.se",
            "crawl_status": "crawled",
            "crawl_detail": "",
        }
    )
    assert scored.company.name == "AKTIEBOLAG KARTVERKSTAN"
    assert scored.company.municipality == "Tyresö"
    assert scored.score == 90
    assert scored.reasons[0].points == 45
    assert scored.website is not None
    assert scored.website.about_text == "Kontakta oss"
    assert scored.website.suggested_recipient == "info@kartverkstan.se"
    assert scored.crawled


def test_filters_keep_companies_missing_a_website() -> None:
    rows = [
        _company("5560000001", "Alpha AB", domain="https://alpha.se", status="crawled"),
        _company("5560000002", "Beta AB", domain=None, status=None),
    ]
    visible = filter_analyzed(rows, AnalyzedFilters(website="no"))
    assert [item.company.name for item in visible] == ["Beta AB"]


def test_text_filter_matches_org_number_with_a_hyphen() -> None:
    rows = [_company("5563907392", "Kartverkstan AB")]
    visible = filter_analyzed(rows, AnalyzedFilters(text="556390-7392"))
    assert len(visible) == 1


def test_saved_search_filter_keeps_matching_sni_and_county() -> None:
    rows = [
        _company("5560000001", "Alpha AB", sni_codes=["71121"], county="Stockholm"),
        _company("5560000002", "Beta AB", sni_codes=["41100"], county="Stockholm"),
        _company("5560000003", "Gamma AB", sni_codes=["71129"], county="Skåne"),
    ]
    search = _search()
    visible = filter_analyzed(
        rows,
        AnalyzedFilters(search_key=search.query_key),
        [search],
    )
    assert [item.company.name for item in visible] == ["Alpha AB"]


def test_empty_search_filter_keeps_every_company() -> None:
    rows = [_company("5560000001", "Alpha AB", sni_codes=["41100"])]
    visible = filter_analyzed(rows, AnalyzedFilters(), [_search()])
    assert len(visible) == 1


def test_saved_search_label_matches_the_history_line() -> None:
    label = format_saved_search(_search())
    assert label.startswith("7112 · Stockholm · 2 companies · ")
    assert label.endswith("UTC")


def test_sni_search_label_uses_the_catalog_name_without_the_time() -> None:
    catalog = SniCatalog(
        groups=[
            SniGroup(
                id="fit",
                title="Fit",
                codes=[SniCode(code="7112", name="Teknisk konsultverksamhet")],
            )
        ]
    )
    label = format_sni_search(_search(), catalog)
    assert label == "7112 — Teknisk konsultverksamhet · Stockholm · 2 companies"


def test_sni_search_label_omits_the_word_employees() -> None:
    label = format_sni_search(replace(_search(), employee_min=10, employee_max=19))
    assert "employees" not in label
    assert "10-19" in label


def test_merge_keeps_companies_that_were_filtered_out() -> None:
    full = _result(
        [
            _company("5560000001", "Alpha AB", domain=None, status=None),
            _company("5560000002", "Beta AB", domain="https://beta.se", status="crawled"),
        ]
    )
    updated = _company("5560000001", "Alpha AB", domain="https://alpha.se", status="crawled")
    merged = merge_analyzed(full, _result([updated]))
    assert merged.companies[0].company.domain == "https://alpha.se"
    assert merged.companies[1].company.name == "Beta AB"


def test_list_companies_reads_saved_rows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["order"] == "name.asc"
        return httpx.Response(
            200,
            json=[
                {
                    "organization_number": "5560000001",
                    "name": "Example AB",
                    "sni_codes": ["71110"],
                    "active": True,
                    "score": 4,
                    "score_reasons": [],
                    "missing_data": [],
                    "domain": "https://example.se",
                    "crawl_status": "crawled",
                    "crawl_detail": "",
                    "pages_fetched": [],
                }
            ],
        )

    store = HttpCompanyStore(
        "http://supabase.test",
        "sb_secret_test",
        transport=httpx.MockTransport(handler),
    )
    companies = store.list_companies()
    assert companies[0].company.domain == "https://example.se"
    assert companies[0].crawled


def _company(
    org: str,
    name: str,
    *,
    domain: str | None = None,
    status: str | None = None,
    sni_codes: list[str] | None = None,
    county: str | None = None,
) -> ScoredCompany:
    return ScoredCompany(
        company=Company(
            organization_number=org,
            name=name,
            domain=domain,
            sni_codes=sni_codes or [],
            county=county,
        ),
        score=1,
        reasons=[ScoreReason(label="Relevant SNI", points=1)],
        crawl_status=status,
    )


def _search() -> SavedSearch:
    return SavedSearch(
        query_key="search-7112",
        segment_key="lidar",
        sni_prefixes=["7112"],
        counties=["Stockholm"],
        municipalities=[],
        employee_min=None,
        employee_max=None,
        revenue_min_sek=None,
        revenue_max_sek=None,
        active_only=True,
        text_query=None,
        result_limit=None,
        fetched_count=2,
        matched_count=2,
        saved_count=2,
        last_searched_at=datetime(2026, 10, 8, 8, 34, tzinfo=UTC),
        run_count=1,
    )


def _result(companies: list[ScoredCompany]) -> SearchResult:
    return SearchResult(
        companies=companies,
        summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
    )


def test_sni_options_count_codes_most_common_first() -> None:
    from lead_finder.use_analyzed_companies import sni_options

    rows = [
        _company("5560000001", "Alpha AB", sni_codes=["71121", "41100"]),
        _company("5560000002", "Beta AB", sni_codes=["71121"]),
        _company("5560000003", "Gamma AB", sni_codes=["08120"]),
    ]
    assert sni_options(rows) == [("71121", 2), ("08120", 1), ("41100", 1)]


def test_several_sni_codes_match_any_of_them() -> None:
    rows = [
        _company("5560000001", "Alpha AB", sni_codes=["71121"]),
        _company("5560000002", "Beta AB", sni_codes=["41100"]),
        _company("5560000003", "Gamma AB", sni_codes=["08120"]),
    ]
    picked = filter_analyzed(rows, AnalyzedFilters(sni_codes=("71121", "08120")))
    assert [item.company.name for item in picked] == ["Alpha AB", "Gamma AB"]
    assert len(filter_analyzed(rows, AnalyzedFilters())) == 3
