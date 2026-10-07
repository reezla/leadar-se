from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, CompanySearchFilters
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter
from lead_finder.providers.scb_map import normalize_company
from lead_finder.scoring import filter_companies
from lead_finder.sni_resolve import expand_sni_prefixes, resolve_industry_codes


class ScbCompanyProvider:
    """Adapter for SCB:s allmänna företagsregister (https://apiafr.scb.se)."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            settings.scb_requests_per_window,
            settings.scb_rate_limit_window_seconds,
        )
        self._owns_client = client is None
        self._api_key = ""
        self._code_tables: dict[str, dict[str, str]] = {}
        self.first_raw_record: dict[str, Any] | None = None
        self.client = client or httpx.Client(timeout=settings.scb_timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> ScbCompanyProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search(self, filters: CompanySearchFilters) -> list[Company]:
        filters, counties, municipalities = self._prepare(filters)
        collected: list[Company] = []
        seen: set[str] = set()
        for path in self._collection_paths(filters, counties, municipalities):
            self._collect(path, filters, counties, municipalities, collected, seen)
            if filters.reached(len(collected)):
                break
        return collected[: filters.limit]

    def _prepare(
        self, filters: CompanySearchFilters
    ) -> tuple[CompanySearchFilters, Mapping[str, str], Mapping[str, str]]:
        api_key = (self.settings.scb_api_key or "").strip()
        if not api_key:
            raise ValueError("SCB_API_KEY is missing. Add it to .env and restart the app.")
        self._api_key = api_key
        counties = self._code_table("lankoder")
        municipalities = self._code_table("kommunkoder")
        if filters.sni_prefixes:
            industry = self._code_table("naringsgrenkoder")
            filters = filters.model_copy(
                update={"sni_prefixes": expand_sni_prefixes(filters.sni_prefixes, industry)}
            )
        return filters, counties, municipalities

    def _collection_paths(
        self,
        filters: CompanySearchFilters,
        counties: Mapping[str, str],
        municipalities: Mapping[str, str],
    ) -> list[str]:
        if filters.sni_prefixes:
            codes = self._industry_codes(filters.sni_prefixes)
            return [f"juridiskaenheter/naringsgren/{code}" for code in codes]
        county_codes = _codes_for_names(filters.counties, counties)
        if county_codes:
            return [f"juridiskaenheter/lan/{code}" for code in county_codes]
        municipality_codes = _codes_for_names(filters.municipalities, municipalities)
        if municipality_codes:
            return [f"juridiskaenheter/kommun/{code}" for code in municipality_codes]
        return ["juridiskaenheter"]

    def _industry_codes(self, prefixes: list[str]) -> list[str]:
        return resolve_industry_codes(prefixes, self._code_table("naringsgrenkoder"))

    def _collect(
        self,
        path: str,
        filters: CompanySearchFilters,
        counties: Mapping[str, str],
        municipalities: Mapping[str, str],
        collected: list[Company],
        seen: set[str],
    ) -> None:
        cursor: int | None = None
        seen_cursors: set[int] = set()
        while not filters.reached(len(collected)):
            payload = self._get(path, cursor)
            records = payload.get("jes") if isinstance(payload, dict) else None
            if not isinstance(records, list) or not records:
                return
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                company = normalize_company(
                    record, counties=counties, municipalities=municipalities
                )
                if company.organization_number in seen:
                    continue
                if not filter_companies([company], filters):
                    continue
                seen.add(company.organization_number)
                collected.append(company)
                if self.first_raw_record is None:
                    self.first_raw_record = dict(record)
                if filters.reached(len(collected)):
                    return
            next_cursor = _next_cursor(payload, seen_cursors)
            if next_cursor is None:
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    def _get(self, path: str, cursor: int | None, *, paginate: bool = True) -> Any:
        params: dict[str, int] | None = None
        if paginate:
            params = {"limit": self._page_size()}
            if cursor is not None:
                params["cursorId"] = cursor
        response: httpx.Response | None = None
        for attempt in range(3):
            self.rate_limiter.wait()
            try:
                response = self.client.get(
                    self._url(path),
                    params=params,
                    headers={"Accept": "application/json", "X-API-Key": self._api_key},
                )
            except httpx.RequestError as error:
                raise ValueError(f"SCB did not respond: {error}") from error
            if response.status_code == 429 and attempt < 2 and _retryable(response):
                time.sleep(_retry_after(response))
                continue
            break
        if response is None or response.is_error:
            raise _api_failure(response)
        return response.json()

    def _code_table(self, name: str) -> dict[str, str]:
        cached = self._code_tables.get(name)
        if cached is not None:
            return cached
        payload = self._get(f"kodtabeller/{name}", None, paginate=False)
        if not isinstance(payload, list):
            raise ValueError(f"SCB code table {name} returned an unexpected payload")
        table = {
            str(item["kod"]): str(item["klartext"])
            for item in payload
            if isinstance(item, Mapping) and item.get("kod") is not None
        }
        self._code_tables[name] = table
        return table

    def _page_size(self) -> int:
        return min(max(self.settings.scb_page_size, 1), 5000)

    def _url(self, path: str) -> str:
        base = self.settings.scb_api_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/{path.lstrip('/')}"


def _codes_for_names(names: list[str], table: Mapping[str, str]) -> list[str]:
    by_name = {label.casefold(): code for code, label in table.items()}
    codes: list[str] = []
    for name in names:
        code = by_name.get(name.casefold())
        if code is None and name in table:
            code = name
        if code is not None:
            codes.append(code)
    return codes


def _next_cursor(payload: Mapping[str, Any], seen_cursors: set[int]) -> int | None:
    pagination = payload.get("pagination")
    if not isinstance(pagination, Mapping) or not pagination.get("hasMore"):
        return None
    cursor = pagination.get("nextCursorId")
    if not isinstance(cursor, int) or cursor in seen_cursors:
        return None
    return cursor


def _api_failure(response: httpx.Response | None) -> ValueError:
    if response is None:
        return ValueError("SCB did not respond.")
    detail = _api_detail(response)
    if detail:
        return ValueError(f"HTTP {response.status_code}: {detail}")
    return ValueError(f"SCB returned HTTP {response.status_code}.")


def _api_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return " ".join(response.text.split())[:240]
    if isinstance(payload, Mapping):
        for key in ("detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _retryable(response: httpx.Response) -> bool:
    if "blocked" in _api_detail(response).casefold():
        return False
    return _retry_after(response) <= 2


def _retry_after(response: httpx.Response) -> float:
    try:
        return max(float(response.headers.get("Retry-After", "1")), 0)
    except ValueError:
        return 1
