from __future__ import annotations

import json
from pathlib import Path

import httpx

from lead_finder.config import Settings
from lead_finder.models import CompanySearchFilters
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter
from lead_finder.providers.scb import ScbCompanyProvider


class NoOpRateLimiter:
    def wait(self) -> None:
        pass


def test_provider_normalizes_fixture_and_sends_filters() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "scb_response.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(scb_api_url="https://scb.example/companies", scb_page_size=2)
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())
    filters = CompanySearchFilters(
        sni_prefixes=["7112"],
        counties=["Västra Götaland"],
        limit=2,
    )

    companies = provider.search(filters)

    assert len(companies) == 2
    assert companies[0].organization_number == "5561234567"
    assert companies[0].sni_codes == ["71120"]
    assert companies[0].employee_min == 10
    request_body = json.loads(requests[0].content)
    assert request_body["filters"]["sniPrefixes"] == ["7112"]
    assert request_body["filters"]["counties"] == ["Västra Götaland"]


def test_provider_paginates_until_limit() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        records = [
            {
                "orgNumber": f"556000000{calls}{index}",
                "name": f"Company {calls}-{index}",
                "sniCodes": ["71120"],
            }
            for index in range(2 if calls == 1 else 1)
        ]
        return httpx.Response(200, json={"items": records, "hasMore": calls == 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(scb_api_url="https://scb.example/companies", scb_page_size=2)
    provider = ScbCompanyProvider(settings, client=client, rate_limiter=NoOpRateLimiter())

    companies = provider.search(CompanySearchFilters(limit=3))

    assert len(companies) == 3
    assert calls == 2


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
