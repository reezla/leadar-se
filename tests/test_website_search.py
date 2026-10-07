from pathlib import Path

import httpx
import pytest

from lead_finder.config import Settings
from lead_finder.models import Company
from lead_finder.providers.website_search import GoogleHtmlFinder, SearchBlocked, SearchFailed

FIXTURES = Path(__file__).parent / "fixtures"


def _finder(html: str) -> GoogleHtmlFinder:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GoogleHtmlFinder(Settings(google_requests_per_window=100), client=client)


def test_finds_first_non_allabolag_google_result() -> None:
    html = (FIXTURES / "google_search_allabolag_first.html").read_text(encoding="utf-8")
    company = Company(organization_number="5560000001", name="Aquasvea AB")
    assert _finder(html).find_website(company) == "https://aquasvea.se/"


def test_falls_back_to_duckduckgo_when_google_is_blocked() -> None:
    ddg = """
    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2F3do.se%2F">3dO</a>
    <a class="result__a" href="https://www.hitta.se/3do">Hitta</a>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "google" in host:
            return httpx.Response(200, text="unusual traffic from your computer")
        return httpx.Response(200, text=ddg, headers={"content-type": "text/html"})

    finder = GoogleHtmlFinder(
        Settings(google_requests_per_window=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    company = Company(organization_number="5560000001", name="3dO arkitekter AB")
    assert finder.find_website(company) == "https://3do.se/"
    assert finder.blocked_detail == "Search blocked this network."


def test_reuses_existing_domain_without_search() -> None:
    called = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["count"] += 1
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    finder = GoogleHtmlFinder(Settings(), client=client)
    company = Company(
        organization_number="5560000001",
        name="Aquasvea AB",
        domain="https://aquasvea.se/",
    )
    assert finder.find_website(company) == "https://aquasvea.se/"
    assert called["count"] == 0


def test_blocked_search_without_a_fallback_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="unusual traffic from your computer")

    finder = GoogleHtmlFinder(
        Settings(google_requests_per_window=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    company = Company(organization_number="5560000001", name="Aquasvea AB")
    with pytest.raises(SearchBlocked):
        finder.find_website(company)


def test_lite_duckduckgo_is_used_when_google_has_no_results_and_html_fails() -> None:
    lite = """
    <a class="result-link" href="https://tibi.se/om-oss/">Om oss - Tibi</a>
    <a href="https://www.allabolag.se/tibi">Allabolag</a>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "google" in host:
            return httpx.Response(200, text="<html>enablejs</html>")
        if host.startswith("lite."):
            return httpx.Response(200, text=lite)
        return httpx.Response(202, text="")

    finder = GoogleHtmlFinder(
        Settings(google_requests_per_window=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    company = Company(organization_number="5563026482", name="TIBI STOCKHOLM AKTIEBOLAG")
    assert finder.find_website(company) == "https://tibi.se/om-oss/"


def test_failed_search_without_a_fallback_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    finder = GoogleHtmlFinder(
        Settings(google_requests_per_window=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    company = Company(organization_number="5560000001", name="Aquasvea AB")
    with pytest.raises(SearchFailed):
        finder.find_website(company)
