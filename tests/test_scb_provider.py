from __future__ import annotations

import httpx
import pytest

from lead_finder.config import Settings
from lead_finder.models import CompanySearchFilters
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter
from lead_finder.providers.scb import ScbCompanyProvider

LAN = [
    {"kod": "14", "klartext": "Västra Götaland"},
    {"kod": "01", "klartext": "Stockholm"},
]
KOMMUN = [
    {"kod": "1480", "klartext": "Göteborg"},
    {"kod": "0180", "klartext": "Stockholm"},
]
SNI = [
    {"kod": "71110", "klartext": "Arkitektverksamhet"},
    {"kod": "71121", "klartext": "Byggteknik"},
    {"kod": "71122", "klartext": "Industriteknik"},
]


class NoOpRateLimiter:
    def wait(self) -> None:
        pass


def _record(
    org: str,
    name: str,
    sni: str,
    *,
    county: str,
    municipality: str,
    employees: str,
    status: str = "1",
) -> dict[str, object]:
    return {
        "peOrgNr": f"16{org}",
        "orgNr": org,
        "namn": name,
        "postAdress": {
            "gatuAdress": "Storgatan 1",
            "coAdress": "",
            "postNr": "41103",
            "postOrt": "Göteborg",
        },
        "primarNaringsgren": {"rangordning": 1, "naringsgren": sni},
        "kommunSate": municipality,
        "lanSate": county,
        "anstKl": employees,
        "ftgStat": status,
    }


def _code_table(request: httpx.Request) -> httpx.Response | None:
    path = request.url.path
    if path.endswith("/kodtabeller/lankoder"):
        return httpx.Response(200, json=LAN)
    if path.endswith("/kodtabeller/kommunkoder"):
        return httpx.Response(200, json=KOMMUN)
    if path.endswith("/kodtabeller/naringsgrenkoder"):
        return httpx.Response(200, json=SNI)
    return None


def test_provider_queries_sni_codes_and_normalizes_records() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        table = _code_table(request)
        if table is not None:
            return table
        if request.url.path.endswith("/naringsgren/71121"):
            return httpx.Response(
                200,
                json={
                    "jes": [
                        _record(
                            "5561234567",
                            "Nordisk Mätteknik AB",
                            "71121",
                            county="14",
                            municipality="1480",
                            employees="4",
                        ),
                        _record(
                            "5560000001",
                            "Vilande AB",
                            "71121",
                            county="14",
                            municipality="1480",
                            employees="1",
                            status="9",
                        ),
                    ],
                    "pagination": {"nextCursorId": 0, "limit": 2, "hasMore": False},
                },
            )
        if request.url.path.endswith("/naringsgren/71122"):
            return httpx.Response(
                200,
                json={
                    "jes": [
                        _record(
                            "5599999999",
                            "Stockholm Teknik AB",
                            "71122",
                            county="01",
                            municipality="0180",
                            employees="6",
                        )
                    ],
                    "pagination": {"nextCursorId": 0, "limit": 2, "hasMore": False},
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        scb_api_url="https://scb.example",
        scb_api_key="test-key",
        scb_page_size=2,
    )
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())
    companies = provider.search(
        CompanySearchFilters(sni_prefixes=["7112"], counties=["Västra Götaland"], limit=2)
    )

    assert [company.organization_number for company in companies] == ["5561234567"]
    company = companies[0]
    assert company.name == "Nordisk Mätteknik AB"
    assert company.sni_codes == ["71121"]
    assert company.county == "Västra Götaland"
    assert company.municipality == "Göteborg"
    assert company.employee_class == "10-19 anställda"
    assert company.employee_min == 10
    assert company.employee_max == 19
    assert company.postal_address == "Storgatan 1, 41103 Göteborg"
    assert company.active is True

    industry_calls = [
        request
        for request in requests
        if "/juridiskaenheter/naringsgren/" in request.url.path
    ]
    assert [request.url.path.rsplit("/", 1)[-1] for request in industry_calls] == [
        "71121",
        "71122",
    ]
    assert industry_calls[0].method == "GET"
    assert industry_calls[0].headers["X-API-Key"] == "test-key"
    assert industry_calls[0].url.params["limit"] == "2"
    assert "cursorId" not in industry_calls[0].url.params
    assert all("limit" not in request.url.params for request in requests if _code_table(request))


def test_provider_follows_cursor_until_limit() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        table = _code_table(request)
        if table is not None:
            return table
        cursor = request.url.params.get("cursorId")
        if cursor is None:
            return httpx.Response(
                200,
                json={
                    "jes": [
                        _record(
                            "5560000001",
                            "Company 1",
                            "71121",
                            county="14",
                            municipality="1480",
                            employees="2",
                        )
                    ],
                    "pagination": {"nextCursorId": 99, "limit": 2, "hasMore": True},
                },
            )
        return httpx.Response(
            200,
            json={
                "jes": [
                    _record(
                        "5560000002",
                        "Company 2",
                        "71121",
                        county="14",
                        municipality="1480",
                        employees="2",
                    )
                ],
                "pagination": {"nextCursorId": 0, "limit": 2, "hasMore": False},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        scb_api_url="https://scb.example",
        scb_api_key="test-key",
        scb_page_size=2,
    )
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())
    companies = provider.search(CompanySearchFilters(limit=2))

    assert [company.name for company in companies] == ["Company 1", "Company 2"]
    company_calls = [request for request in calls if request.url.path.endswith("/juridiskaenheter")]
    assert company_calls[1].url.params["cursorId"] == "99"


def test_provider_fetches_all_pages_when_limit_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        table = _code_table(request)
        if table is not None:
            return table
        cursor = request.url.params.get("cursorId")
        pages = {
            None: ("5560000001", 99, True),
            "99": ("5560000002", 100, True),
            "100": ("5560000003", 0, False),
        }
        org, next_cursor, has_more = pages[cursor]
        return httpx.Response(
            200,
            json={
                "jes": [
                    _record(
                        org,
                        f"Company {org[-1]}",
                        "71121",
                        county="14",
                        municipality="1480",
                        employees="2",
                    )
                ],
                "pagination": {
                    "nextCursorId": next_cursor,
                    "limit": 2,
                    "hasMore": has_more,
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        scb_api_url="https://scb.example",
        scb_api_key="test-key",
        scb_page_size=2,
    )
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())
    companies = provider.search(CompanySearchFilters(limit=None))

    assert [company.name for company in companies] == [
        "Company 1",
        "Company 2",
        "Company 3",
    ]


def test_provider_requires_api_key() -> None:
    settings = Settings(scb_api_url="https://scb.example", scb_api_key=None)
    provider = ScbCompanyProvider(settings, rate_limiter=NoOpRateLimiter())
    with pytest.raises(ValueError, match="SCB_API_KEY"):
        provider.search(CompanySearchFilters(limit=1))


def test_rate_limiter_waits_when_window_is_full() -> None:
    now = 0.0
    delays: list[float] = []

    def clock() -> float:
        return now

    def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    limiter = SlidingWindowRateLimiter(2, 10, clock=clock, sleep=sleep)
    limiter.wait()
    limiter.wait()
    limiter.wait()

    assert delays == [10]


def test_provider_maps_architect_71111_to_scb_71110() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        table = _code_table(request)
        if table is not None:
            return table
        if request.url.path.endswith("/naringsgren/71110"):
            return httpx.Response(
                200,
                json={
                    "jes": [
                        _record(
                            "5561111111",
                            "Arkitektbolaget AB",
                            "71110",
                            county="14",
                            municipality="1480",
                            employees="4",
                        )
                    ],
                    "pagination": {"nextCursorId": 0, "limit": 2, "hasMore": False},
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        scb_api_url="https://scb.example",
        scb_api_key="test-key",
        scb_page_size=2,
    )
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())
    companies = provider.search(CompanySearchFilters(sni_prefixes=["71111"], limit=5))

    assert [company.name for company in companies] == ["Arkitektbolaget AB"]
    industry_calls = [
        request
        for request in requests
        if "/juridiskaenheter/naringsgren/" in request.url.path
    ]
    assert [request.url.path.rsplit("/", 1)[-1] for request in industry_calls] == ["71110"]


def test_blocked_key_raises_the_api_detail() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            json={
                "title": "Too Many Requests",
                "status": 429,
                "detail": "API key temporarily blocked until 2026-10-02 13:14:12Z.",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(scb_api_url="https://scb.example", scb_api_key="test-key")
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())

    with pytest.raises(ValueError, match="temporarily blocked until 2026-10-02 13:14:12Z"):
        provider.search(CompanySearchFilters(sni_prefixes=["71121"]))
    assert calls == 1
