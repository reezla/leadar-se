from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from lead_finder.config import Settings
from lead_finder.models import CompanySearchFilters
from lead_finder.providers.allabolag import AllabolagCompanyProvider


class NoOpRateLimiter:
    def wait(self) -> None:
        pass


def _payload(*, page: int, next_page: int | None, org_suffix: str) -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "allabolag_next_data.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    company = fixture["props"]["pageProps"]["companies"][0]
    company = {
        **company,
        "organisationNumber": f"556000000{org_suffix}",
        "name": f"Company {org_suffix}",
        "displayName": f"Company {org_suffix}",
    }
    return {
        "buildId": "test-build",
        "pageProps": {
            "numberOfHits": 12,
            "pagination": {"currentPage": page, "next": next_page, "pageSize": 10},
            "companies": [company],
        },
    }


def test_provider_paginates_html_then_json() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        parsed = urlparse(str(request.url))
        if parsed.path.endswith("/segmentering"):
            payload = _payload(page=1, next_page=2, org_suffix="1")
            document = {
                "buildId": "test-build",
                "props": {"pageProps": payload["pageProps"]},
            }
            html = f'<script id="__NEXT_DATA__">{json.dumps(document)}</script>'
            return httpx.Response(200, text=html)
        if parsed.path.endswith("/segmentation.json"):
            return httpx.Response(200, json=_payload(page=2, next_page=None, org_suffix="2"))
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AllabolagCompanyProvider(
        Settings(allabolag_base_url="https://allabolag.example"),
        client=client,
        rate_limiter=NoOpRateLimiter(),
    )

    companies = provider.search(CompanySearchFilters(sni_prefixes=["71121"], limit=5))

    assert [company.name for company in companies] == ["Company 1", "Company 2"]
    assert requests[0].url.path.endswith("/segmentering")
    assert requests[1].url.path.endswith("/segmentation.json")


def test_provider_fetches_all_pages_when_limit_is_none() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        parsed = urlparse(str(request.url))
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        next_page = page + 1 if page < 3 else None
        payload = _payload(page=page, next_page=next_page, org_suffix=str(page))
        if parsed.path.endswith("/segmentering"):
            document = {
                "buildId": "test-build",
                "props": {"pageProps": payload["pageProps"]},
            }
            html = f'<script id="__NEXT_DATA__">{json.dumps(document)}</script>'
            return httpx.Response(200, text=html)
        if parsed.path.endswith("/segmentation.json"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = AllabolagCompanyProvider(
        Settings(allabolag_base_url="https://allabolag.example"),
        client=client,
        rate_limiter=NoOpRateLimiter(),
    )

    companies = provider.search(CompanySearchFilters(sni_prefixes=["71121"], limit=None))

    assert [company.name for company in companies] == [
        "Company 1",
        "Company 2",
        "Company 3",
    ]
    assert len(requests) == 3


def test_provider_requires_sni_prefix() -> None:
    provider = AllabolagCompanyProvider(
        Settings(),
        client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
        rate_limiter=NoOpRateLimiter(),
    )
    with pytest.raises(ValueError, match="SNI prefix"):
        provider.search(CompanySearchFilters(limit=10))
