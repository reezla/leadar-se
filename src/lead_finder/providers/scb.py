from __future__ import annotations

import ssl
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, CompanySearchFilters
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter


class ScbCompanyProvider:
    """Adapter for SCB Företagsregistret.

    The endpoint and credentials are configurable because SCB is replacing the API
    during 2026. Only this adapter should need changing when the migration completes.
    """

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
        self.client = client or httpx.Client(
            timeout=settings.scb_timeout_seconds,
            verify=self._ssl_context(),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> ScbCompanyProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search(self, filters: CompanySearchFilters) -> list[Company]:
        companies: list[Company] = []
        offset = 0
        page_size = min(self.settings.scb_page_size, filters.limit)

        while len(companies) < filters.limit:
            self.rate_limiter.wait()
            response = self.client.post(
                self.settings.scb_api_url,
                json=self._build_request(filters, offset=offset, limit=page_size),
            )
            response.raise_for_status()
            records, has_more = self._extract_page(response.json(), page_size)
            if not records:
                break
            companies.extend(self._normalize(record) for record in records)
            if not has_more:
                break
            offset += len(records)

        return companies[: filters.limit]

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()
        cert_path = self.settings.scb_cert_path
        key_path = self.settings.scb_key_path
        if cert_path:
            context.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path) if key_path else None,
                password=self.settings.scb_cert_password,
            )
        return context

    @staticmethod
    def _build_request(
        filters: CompanySearchFilters, *, offset: int, limit: int
    ) -> dict[str, Any]:
        return {
            "offset": offset,
            "limit": limit,
            "filters": {
                "sniPrefixes": filters.sni_prefixes,
                "counties": filters.counties,
                "municipalities": filters.municipalities,
                "activeOnly": filters.active_only,
                "text": filters.text_query,
            },
        }

    @staticmethod
    def _extract_page(payload: Any, page_size: int) -> tuple[list[Mapping[str, Any]], bool]:
        if isinstance(payload, list):
            records = payload
            return records, len(records) == page_size
        records = (
            payload.get("items")
            or payload.get("results")
            or payload.get("foretag")
            or payload.get("records")
            or []
        )
        pagination = payload.get("pagination", {})
        has_more = bool(
            payload.get("hasMore")
            or pagination.get("hasMore")
            or pagination.get("next")
            or len(records) == page_size
        )
        return records, has_more

    @classmethod
    def _normalize(cls, record: Mapping[str, Any]) -> Company:
        organization_number = cls._first(
            record, "organisationsnummer", "organizationNumber", "orgNumber", "orgnr"
        )
        name = cls._first(record, "foretagsnamn", "companyName", "name", "namn")
        if not organization_number or not name:
            raise ValueError("SCB record is missing organization number or company name")

        employee_min, employee_max = cls._interval(
            record,
            low_keys=("employeeMin", "antalAnstalldaMin"),
            high_keys=("employeeMax", "antalAnstalldaMax"),
        )
        revenue_min, revenue_max = cls._interval(
            record,
            low_keys=("revenueMinSek", "omsattningMin"),
            high_keys=("revenueMaxSek", "omsattningMax"),
        )
        return Company(
            organization_number=str(organization_number),
            name=str(name),
            workplace_name=cls._first(record, "arbetsstallenamn", "workplaceName"),
            sni_codes=cls._sni_codes(record),
            activity_description=cls._first(
                record, "verksamhetsbeskrivning", "activityDescription"
            ),
            municipality=cls._first(record, "kommun", "municipality", "kommunNamn"),
            county=cls._first(record, "lan", "county", "lanNamn"),
            postal_address=cls._address(record),
            employee_class=cls._first(
                record, "antalAnstalldaStorleksklass", "employeeSizeClass"
            ),
            employee_min=employee_min,
            employee_max=employee_max,
            revenue_class=cls._first(
                record, "arsomsattningStorleksklass", "revenueSizeClass"
            ),
            revenue_min_sek=revenue_min,
            revenue_max_sek=revenue_max,
            active=bool(cls._first(record, "verksam", "active", default=True)),
            domain=cls._first(record, "webbplats", "website", "domain"),
            retrieved_at=datetime.now(UTC),
        )

    @staticmethod
    def _first(record: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in record and record[key] not in (None, ""):
                return record[key]
        return default

    @classmethod
    def _sni_codes(cls, record: Mapping[str, Any]) -> list[str]:
        raw = cls._first(record, "sniKoder", "sniCodes", "sni", default=[])
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return [
            str(item.get("kod") or item.get("code"))
            if isinstance(item, Mapping)
            else str(item)
            for item in raw
            if item
        ]

    @classmethod
    def _address(cls, record: Mapping[str, Any]) -> str | None:
        direct = cls._first(record, "postadress", "postalAddress")
        if isinstance(direct, str):
            return direct
        if isinstance(direct, Mapping):
            parts = [
                cls._first(direct, "adress", "street"),
                cls._first(direct, "postnummer", "postalCode"),
                cls._first(direct, "postort", "city"),
            ]
            return ", ".join(str(part) for part in parts if part)
        return None

    @classmethod
    def _interval(
        cls,
        record: Mapping[str, Any],
        *,
        low_keys: Iterable[str],
        high_keys: Iterable[str],
    ) -> tuple[int | None, int | None]:
        low = cls._first(record, *low_keys)
        high = cls._first(record, *high_keys)
        return cls._integer(low), cls._integer(high)

    @staticmethod
    def _integer(value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)
