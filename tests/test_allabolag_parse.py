from __future__ import annotations

import json
from pathlib import Path

from lead_finder.models import CompanySearchFilters
from lead_finder.providers.allabolag_parse import (
    build_query,
    build_search_url,
    format_nace_industry,
    parse_html,
    parse_payload,
)


def test_format_nace_industry_inserts_dot_after_division() -> None:
    assert format_nace_industry("71121") == "71.121"
    assert format_nace_industry("71.12") == "71.12"
    assert format_nace_industry("71") == "71"
    assert format_nace_industry("02.200") == "02.200"


def test_build_query_maps_sni_revenue_and_employees() -> None:
    query = build_query(
        CompanySearchFilters(
            sni_prefixes=["71121", "41100"],
            municipalities=["Göteborg"],
            employee_min=5,
            revenue_min_sek=5_000_000,
            limit=50,
        )
    )
    assert query["naceIndustry"] == "71.121,41.100"
    assert query["revenueFrom"] == "5000"
    assert query["revenueTo"] == "999999999"
    assert query["numEmployeesFrom"] == "5"
    assert query["numEmployeesTo"] == "999999"
    assert query["companyType"] == "AB"
    assert query["location"] == "Göteborg"
    assert query["sort"] == "revenueDesc"


def test_build_search_url_omits_first_page() -> None:
    url = build_search_url(
        "https://www.allabolag.se",
        {"naceIndustry": "71.121", "page": "1", "sort": "revenueDesc"},
    )
    assert url == "https://www.allabolag.se/segmentering?naceIndustry=71.121&sort=revenueDesc"


def test_parse_payload_normalizes_company_and_sni() -> None:
    fixture = Path(__file__).parent / "fixtures" / "allabolag_next_data.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    page = parse_payload(payload)
    company = page.companies[0]

    assert page.hits == 12
    assert page.next_page == 2
    assert page.build_id == "test-build"
    assert company.organization_number == "5561234567"
    assert company.sni_codes == ["71121", "41000"]
    assert company.employee_min == 18
    assert company.revenue_min_sek == 12_500_000
    assert company.municipality == "Göteborg"
    assert company.source == "Allabolag.se"
    assert company.domain == "https://www.example.se"


def test_employee_range_is_parsed_into_min_and_max() -> None:
    page = parse_payload(
        {
            "pageProps": {
                "numberOfHits": 1,
                "pagination": {"currentPage": 1, "next": None},
                "companies": [
                    {
                        "organisationNumber": "5560000001",
                        "name": "Range AB",
                        "numberOfEmployees": "10-19",
                        "revenue": "5000",
                        "naceCategories": ["71121 Consulting"],
                        "status": {"status": "ACTIVE"},
                    }
                ],
            }
        }
    )
    company = page.companies[0]
    assert company.employee_class == "10-19"
    assert company.employee_min == 10
    assert company.employee_max == 19


def test_parse_html_reads_next_data_script() -> None:
    payload = (Path(__file__).parent / "fixtures" / "allabolag_next_data.json").read_text(
        encoding="utf-8"
    )
    page = parse_html(f'<html><script id="__NEXT_DATA__">{payload}</script></html>')
    assert len(page.companies) == 1
    assert page.companies[0].name == "Nordisk Mätteknik AB"
