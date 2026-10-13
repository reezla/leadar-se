from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from lead_finder.company_store_delete import delete_company_rows
from lead_finder.models import CompanySearchFilters, ScoredCompany
from lead_finder.use_company_search import SearchResult
from lead_finder.use_company_store import (
    SavedSearch,
    SaveOutcome,
    StoreError,
    _blank,
    _optional_int,
    _texts,
    canonical_search,
    company_row,
    enriched_row,
    query_key,
    scored_from_store_row,
)

logger = logging.getLogger(__name__)

_CHUNK = 200
_USER_AGENT = "lead-finder"
_SEARCH_COLUMNS = (
    "query_key,segment_key,sni_prefixes,counties,municipalities,employee_min,employee_max,"
    "revenue_min_sek,revenue_max_sek,active_only,text_query,result_limit,fetched_count,"
    "matched_count,saved_count,last_searched_at,run_count"
)
_UPSERT = "resolution=merge-duplicates,return=minimal"
_ANALYSIS_COLUMNS = (
    "recommended_product",
    "alternative_products",
    "buyer_type",
    "customer_fit",
    "product_analysis",
    "analyzed_at",
)
_COMPANY_COLUMNS = (
    "organization_number,name,workplace_name,sni_codes,activity_description,municipality,county,"
    "postal_address,employee_class,employee_min,employee_max,revenue_class,revenue_min_sek,"
    "revenue_max_sek,active,source,retrieved_at,score,score_reasons,missing_data,domain,about_text,"
    "projects_text,pages_fetched,website_source,suggested_recipient,crawl_status,crawl_detail,"
    "recommended_product,alternative_products,buyer_type,customer_fit,product_analysis,analyzed_at"
)
_PAGE = 1000


class HttpCompanyStore:
    def __init__(
        self,
        url: str,
        secret_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._secret_key = secret_key
        self._transport = transport

    def save_search(
        self,
        result: SearchResult,
        filters: CompanySearchFilters,
        segment_key: str,
    ) -> SaveOutcome:
        try:
            with self._open() as client:
                rows = [company_row(item) for item in result.companies]
                for chunk in _chunks(rows, _CHUNK):
                    failed = _post_companies(client, chunk)
                    if failed is not None:
                        return failed
                return _record_search(client, result, filters, segment_key)
        except httpx.HTTPError as error:
            logger.warning("Company save failed: %s", error)
            return SaveOutcome(error=str(error))

    def save_companies(
        self,
        companies: list[ScoredCompany],
        *,
        include_crawl: bool = False,
    ) -> SaveOutcome:
        rows = [enriched_row(item, include_crawl=include_crawl) for item in companies]
        if not rows:
            return SaveOutcome()
        try:
            with self._open() as client:
                for chunk in _chunks(rows, _CHUNK):
                    failed = _post_companies(client, chunk)
                    if failed is not None:
                        return failed
        except httpx.HTTPError as error:
            logger.warning("Company save failed: %s", error)
            return SaveOutcome(error=str(error))
        return SaveOutcome()

    def patch_crawl(self, scored: ScoredCompany) -> SaveOutcome:
        return self.save_companies([scored], include_crawl=True)

    def list_searches(self, limit: int = 20) -> list[SavedSearch]:
        try:
            with self._open() as client:
                response = client.get(
                    "/company_searches",
                    params={
                        "select": _SEARCH_COLUMNS,
                        "order": "last_searched_at.desc",
                        "limit": str(limit),
                    },
                )
        except httpx.HTTPError as error:
            raise StoreError(str(error)) from error
        if response.status_code >= 400:
            raise StoreError(_detail(response))
        return [_saved_search(item) for item in response.json()]

    def list_companies(self) -> list[ScoredCompany]:
        try:
            with self._open() as client:
                try:
                    rows = _get_pages(client, "/companies", _COMPANY_COLUMNS)
                except StoreError as error:
                    if not _missing_column(str(error)):
                        raise
                    logger.warning("Analysis columns missing; apply the latest migration.")
                    rows = _get_pages(client, "/companies", _without_analysis(_COMPANY_COLUMNS))
        except httpx.HTTPError as error:
            raise StoreError(str(error)) from error
        return [scored_from_store_row(row) for row in rows]

    def delete_companies(self, organization_numbers: list[str]) -> SaveOutcome:
        try:
            with self._open() as client:
                failed = delete_company_rows(client, organization_numbers)
        except httpx.HTTPError as error:
            logger.warning("Company delete failed: %s", error)
            return SaveOutcome(error=str(error))
        return failed or SaveOutcome()

    def _open(self) -> httpx.Client:
        kwargs: dict[str, object] = {}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(
            base_url=f"{self._url}/rest/v1",
            headers={
                "apikey": self._secret_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
            },
            timeout=30,
            **kwargs,
        )


def _post_companies(client: httpx.Client, rows: list[dict[str, object]]) -> SaveOutcome | None:
    response = _upsert(client, rows)
    if response.status_code >= 400 and _missing_column(response.text):
        logger.warning("Analysis columns missing; saving without them. Apply the latest migration.")
        response = _upsert(client, [_strip_analysis(row) for row in rows])
    if response.status_code >= 400:
        return SaveOutcome(error=_detail(response))
    return None


def _upsert(client: httpx.Client, rows: list[dict[str, object]]) -> httpx.Response:
    return client.post(
        "/companies",
        params={"on_conflict": "organization_number"},
        headers={"Prefer": _UPSERT},
        json=rows,
    )


def _missing_column(text: str) -> bool:
    folded = text.casefold()
    hit = "42703" in folded or "pgrst204" in folded or "does not exist" in folded
    return hit and any(column in folded for column in _ANALYSIS_COLUMNS)


def _strip_analysis(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key not in _ANALYSIS_COLUMNS}


def _without_analysis(columns: str) -> str:
    return ",".join(part for part in columns.split(",") if part not in _ANALYSIS_COLUMNS)


def _record_search(
    client: httpx.Client,
    result: SearchResult,
    filters: CompanySearchFilters,
    segment_key: str,
) -> SaveOutcome:
    key = query_key(segment_key, filters)
    existing = client.get(
        "/company_searches",
        params={"query_key": f"eq.{key}", "select": "run_count,first_searched_at", "limit": "1"},
    )
    if existing.status_code >= 400:
        return SaveOutcome(error=_detail(existing))
    rows = existing.json()
    now = datetime.now(UTC).isoformat()
    if rows:
        run_count = int(rows[0]["run_count"]) + 1
        first_searched_at = str(rows[0]["first_searched_at"])
    else:
        run_count = 1
        first_searched_at = now
    response = client.post(
        "/company_searches",
        params={"on_conflict": "query_key"},
        headers={"Prefer": _UPSERT},
        json={
            **canonical_search(segment_key, filters),
            "query_key": key,
            "fetched_count": result.summary.fetched,
            "matched_count": result.summary.matched,
            "saved_count": len(result.companies),
            "first_searched_at": first_searched_at,
            "last_searched_at": now,
            "run_count": run_count,
        },
    )
    if response.status_code >= 400:
        return SaveOutcome(error=_detail(response))
    return SaveOutcome()


def _saved_search(row: dict[str, object]) -> SavedSearch:
    return SavedSearch(
        query_key=str(row["query_key"]),
        segment_key=str(row["segment_key"]),
        sni_prefixes=_texts(row.get("sni_prefixes")),
        counties=_texts(row.get("counties")),
        municipalities=_texts(row.get("municipalities")),
        employee_min=_optional_int(row.get("employee_min")),
        employee_max=_optional_int(row.get("employee_max")),
        revenue_min_sek=_optional_int(row.get("revenue_min_sek")),
        revenue_max_sek=_optional_int(row.get("revenue_max_sek")),
        active_only=bool(row.get("active_only", True)),
        text_query=_blank(row.get("text_query")),
        result_limit=_optional_int(row.get("result_limit")),
        fetched_count=int(row.get("fetched_count") or 0),
        matched_count=int(row.get("matched_count") or 0),
        saved_count=int(row.get("saved_count") or 0),
        last_searched_at=datetime.fromisoformat(str(row["last_searched_at"])),
        run_count=int(row.get("run_count") or 1),
    )


def _get_pages(client: httpx.Client, path: str, select: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    offset = 0
    while True:
        params = {"select": select, "order": "name.asc", "limit": str(_PAGE), "offset": str(offset)}
        response = client.get(path, params=params)
        if response.status_code >= 400:
            raise StoreError(_detail(response))
        chunk = response.json()
        rows.extend(chunk)
        if len(chunk) < _PAGE:
            return rows
        offset += _PAGE


def _chunks(rows: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _detail(response: httpx.Response) -> str:
    detail = response.text.strip().replace("\n", " ")[:300]
    return f"Supabase returned {response.status_code}: {detail}"
