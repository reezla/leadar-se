from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, CompanySearchFilters
from lead_finder.providers.allabolag_parse import (
    AllabolagPage,
    build_query,
    parse_html,
    parse_payload,
)
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter

ProgressCallback = Callable[[int, int, int], None]


class AllabolagCompanyProvider:
    """Reads public Allabolag segmentation search pages. Stopgap until SCB access is ready."""

    def __init__(
        self,
        settings: Settings,
        *,
        ab_only: bool = True,
        client: httpx.Client | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        self.settings = settings
        self.ab_only = ab_only
        self.on_progress = on_progress
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            settings.allabolag_requests_per_window,
            settings.allabolag_rate_limit_window_seconds,
        )
        self._owns_client = client is None
        self._build_id: str | None = None
        self.client = client or httpx.Client(
            timeout=settings.allabolag_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.allabolag_user_agent,
                "Accept": "text/html,application/json",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> AllabolagCompanyProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search(self, filters: CompanySearchFilters) -> list[Company]:
        if not filters.sni_prefixes:
            raise ValueError("Select at least one SNI prefix before crawling Allabolag")
        companies: list[Company] = []
        seen: set[str] = set()
        page_number = 1
        while not filters.reached(len(companies)):
            parsed = self._fetch_page(filters, page_number)
            if parsed.build_id:
                self._build_id = parsed.build_id
            added = 0
            for company in parsed.companies:
                if company.organization_number in seen:
                    continue
                seen.add(company.organization_number)
                companies.append(company)
                added += 1
                if filters.reached(len(companies)):
                    break
            if self.on_progress:
                self.on_progress(parsed.page, len(companies), parsed.hits)
            if not parsed.next_page or added == 0:
                break
            page_number = parsed.next_page
        return companies[: filters.limit]

    def _fetch_page(self, filters: CompanySearchFilters, page_number: int) -> AllabolagPage:
        query = build_query(filters, page=page_number, ab_only=self.ab_only)
        self.rate_limiter.wait()
        build_id = self._build_id
        if page_number == 1 or not build_id:
            return parse_html(self._get(_html_path(self.settings.allabolag_base_url), query))
        try:
            json_url = _json_path(self.settings.allabolag_base_url, build_id)
            return parse_payload(self._get_json(json_url, query))
        except (httpx.HTTPError, ValueError, TypeError):
            return parse_html(self._get(_html_path(self.settings.allabolag_base_url), query))

    def _get(self, url: str, params: dict[str, str]) -> str:
        response = self.client.get(url, params=params)
        _raise_for_status(response)
        return response.text

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        response = self.client.get(url, params=params, headers={"Accept": "application/json"})
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Allabolag JSON page was not an object")
        return payload


def _html_path(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/segmentering"


def _json_path(base_url: str, build_id: str) -> str:
    return f"{base_url.rstrip('/')}/_next/data/{build_id}/segmentation.json"


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {403, 429}:
        raise RuntimeError(
            f"Allabolag blocked the crawler with HTTP {response.status_code}. "
            "Wait and retry, or open the preview URL in a browser."
        )
    response.raise_for_status()
