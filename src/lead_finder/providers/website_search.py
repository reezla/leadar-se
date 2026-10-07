from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company
from lead_finder.providers.google_search_parse import (
    first_usable_website,
    parse_organic_urls,
    unwrap_href,
)
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


class SearchBlocked(Exception):
    """Google or DuckDuckGo returned a block page and no website."""


class SearchFailed(Exception):
    """The search request failed and no website was found."""


class WebsiteFinder(Protocol):
    blocked_detail: str | None
    request_failed: bool

    def find_website(self, company: Company) -> str | None:
        """Return the official website URL, or None if none was found."""
        ...


class GoogleHtmlFinder:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            settings.google_requests_per_window,
            settings.google_rate_limit_window_seconds,
        )
        self.blocked_detail = None
        self.request_failed = False
        self.client = client or httpx.Client(
            timeout=settings.google_search_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.allabolag_user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> GoogleHtmlFinder:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def find_website(self, company: Company) -> str | None:
        self.blocked_detail = None
        self.request_failed = False
        existing = _existing_website(company.domain)
        if existing:
            return existing
        query = f"{company.name} officiell webbplats"
        google = self._search(
            self.settings.google_search_url,
            {"q": query, "hl": "sv", "gl": "se", "num": "10", "pws": "0"},
        )
        if google.url and not google.blocked:
            return google.url
        if not google.url:
            logger.warning(
                "Google returned no website company=%s detail=%s",
                company.name,
                google.detail or "no usable link",
            )
        fallback = self._duckduckgo(query)
        self._remember(google, fallback)
        if fallback.url:
            return fallback.url
        if google.url:
            return google.url
        if google.blocked or fallback.blocked:
            raise SearchBlocked(self.blocked_detail or "Search blocked this network.")
        if google.failed or fallback.failed or google.detail:
            detail = _joined_detail(google.detail, fallback.detail) or "Search request failed."
            raise SearchFailed(detail)
        return None

    def _duckduckgo(self, query: str) -> _Hit:
        params = {"q": query}
        html_hit = self._search(self.settings.duckduckgo_search_url, params)
        if html_hit.url or html_hit.blocked:
            return html_hit
        lite = self._search(self.settings.duckduckgo_lite_url, params)
        if lite.url or lite.blocked:
            return lite
        return _Hit(
            failed=html_hit.failed or lite.failed,
            detail=_joined_detail(html_hit.detail, lite.detail),
        )

    def _remember(self, google: _Hit, fallback: _Hit) -> None:
        if google.blocked or fallback.blocked:
            self.blocked_detail = google.detail or fallback.detail or "Search blocked this network."
        if google.failed or fallback.failed:
            self.request_failed = True

    def _search(self, url: str, params: dict[str, str]) -> _Hit:
        found = self._request(url, params, method="GET")
        if found.url or found.blocked or "duckduckgo" not in url:
            return found
        return self._request(url, params, method="POST")

    def _request(self, url: str, params: dict[str, str], *, method: str) -> _Hit:
        self.rate_limiter.wait()
        try:
            if method == "POST":
                response = self.client.post(url, data=params)
            else:
                response = self.client.get(url, params=params)
        except httpx.HTTPError as error:
            logger.warning("Search request failed url=%s error=%s", url, error)
            return _Hit(failed=True, detail=f"Could not reach {url}.")
        if _blocked(response) or response.status_code == 429:
            logger.warning(
                "Search blocked url=%s status=%s",
                response.url,
                response.status_code,
            )
            return _Hit(blocked=True, detail="Search blocked this network.")
        if response.status_code != 200:
            logger.warning(
                "Search request failed url=%s status=%s",
                response.url,
                response.status_code,
            )
            return _Hit(failed=True, detail=f"Search returned HTTP {response.status_code}.")
        url = first_usable_website(parse_organic_urls(response.text))
        if url is None and _google_shell(response):
            return _Hit(detail="Google showed a consent or script page instead of results.")
        return _Hit(url=url)


def build_website_finder(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
) -> GoogleHtmlFinder:
    provider = settings.website_search_provider.casefold()
    if provider != "google":
        raise ValueError(f"Unsupported website search provider: {provider}")
    return GoogleHtmlFinder(settings, client=client)


def _existing_website(domain: str | None) -> str | None:
    if not domain:
        return None
    raw = domain if "://" in domain else f"https://{domain}"
    return unwrap_href(raw)


@dataclass(frozen=True)
class _Hit:
    url: str | None = None
    blocked: bool = False
    failed: bool = False
    detail: str = ""


def _joined_detail(*parts: str) -> str:
    unique: list[str] = []
    for part in parts:
        if part and part not in unique:
            unique.append(part)
    return "; ".join(unique)


def _google_shell(response: httpx.Response) -> bool:
    if "google." not in (response.url.host or ""):
        return False
    text = response.text.casefold()
    return "enablejs" in text or "consent.google" in text


def _blocked(response: httpx.Response) -> bool:
    text = response.text.casefold()
    return "/sorry/" in str(response.url) or "unusual traffic" in text or "detected unusual" in text
