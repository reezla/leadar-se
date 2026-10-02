from __future__ import annotations

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


class WebsiteFinder(Protocol):
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
        existing = _existing_website(company.domain)
        if existing:
            return existing
        query = f"{company.name} officiell webbplats"
        google = {
            "q": query,
            "hl": "sv",
            "gl": "se",
            "num": "10",
            "pws": "0",
        }
        return self._search(self.settings.google_search_url, google) or self._search(
            self.settings.duckduckgo_search_url, {"q": query}
        )

    def _search(self, url: str, params: dict[str, str]) -> str | None:
        found = self._request(url, params, method="GET")
        if found or "duckduckgo" not in url:
            return found
        return self._request(url, params, method="POST")

    def _request(self, url: str, params: dict[str, str], *, method: str) -> str | None:
        self.rate_limiter.wait()
        try:
            if method == "POST":
                response = self.client.post(url, data=params)
            else:
                response = self.client.get(url, params=params)
        except httpx.HTTPError:
            return None
        if response.status_code != 200 or _blocked(response):
            return None
        return first_usable_website(parse_organic_urls(response.text))


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


def _blocked(response: httpx.Response) -> bool:
    text = response.text.casefold()
    return "/sorry/" in str(response.url) or "unusual traffic" in text or "detected unusual" in text
