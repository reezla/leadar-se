from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from lead_finder.models import Company, CompanySearchFilters
from lead_finder.sni_resolve import resolve_industry_codes

NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
SNI_RE = re.compile(r"^(\d{2,5})")
UNBOUNDED_REVENUE_KSEK = 999_999_999
UNBOUNDED_EMPLOYEES = 999_999


@dataclass(frozen=True)
class AllabolagPage:
    companies: list[Company]
    hits: int
    page: int
    next_page: int | None
    build_id: str | None


def format_nace_industry(code: str) -> str:
    digits = "".join(character for character in code if character.isdigit())
    if len(digits) <= 2:
        return digits
    return f"{digits[:2]}.{digits[2:]}"


def build_query(
    filters: CompanySearchFilters,
    *,
    page: int = 1,
    ab_only: bool = True,
    sort: str = "revenueDesc",
) -> dict[str, str]:
    query: dict[str, str] = {"sort": sort, "page": str(page)}
    if filters.sni_prefixes:
        query["naceIndustry"] = ",".join(
            format_nace_industry(prefix)
            for prefix in resolve_industry_codes(filters.sni_prefixes)
        )
    locations = [*filters.municipalities, *filters.counties]
    if locations:
        query["location"] = ",".join(locations)
    if filters.revenue_min_sek is not None:
        query["revenueFrom"] = str(filters.revenue_min_sek // 1_000)
        query["revenueTo"] = (
            str(filters.revenue_max_sek // 1_000)
            if filters.revenue_max_sek is not None
            else str(UNBOUNDED_REVENUE_KSEK)
        )
    elif filters.revenue_max_sek is not None:
        query["revenueFrom"] = "0"
        query["revenueTo"] = str(filters.revenue_max_sek // 1_000)
    if filters.employee_min is not None:
        query["numEmployeesFrom"] = str(filters.employee_min)
        employee_max = filters.employee_max
        query["numEmployeesTo"] = (
            str(employee_max) if employee_max is not None else str(UNBOUNDED_EMPLOYEES)
        )
    elif filters.employee_max is not None:
        query["numEmployeesFrom"] = "0"
        query["numEmployeesTo"] = str(filters.employee_max)
    if ab_only:
        query["companyType"] = "AB"
    return query


def build_search_url(base_url: str, query: Mapping[str, str]) -> str:
    params = {key: value for key, value in query.items() if key != "page" or value != "1"}
    return f"{base_url.rstrip('/')}/segmentering?{urlencode(params, safe=',')}"


def parse_html(html: str) -> AllabolagPage:
    match = NEXT_DATA_RE.search(html)
    if match is None:
        raise ValueError("Allabolag page did not include company data")
    return parse_payload(json.loads(match.group(1)))


def parse_payload(payload: Mapping[str, Any]) -> AllabolagPage:
    page_props = payload.get("pageProps") or payload.get("props", {}).get("pageProps") or {}
    pagination = page_props.get("pagination") or {}
    companies = [
        company
        for record in page_props.get("companies") or []
        if isinstance(record, Mapping)
        for company in [_normalize_record(record)]
        if company is not None
    ]
    next_page = pagination.get("next")
    return AllabolagPage(
        companies=companies,
        hits=int(page_props.get("numberOfHits") or 0),
        page=int(pagination.get("currentPage") or 1),
        next_page=int(next_page) if next_page else None,
        build_id=str(payload["buildId"]) if payload.get("buildId") else None,
    )


def _normalize_record(record: Mapping[str, Any]) -> Company | None:
    organization_number = record.get("organisationNumber") or record.get("companyId")
    name = record.get("displayName") or record.get("name")
    if not organization_number or not name:
        return None
    employees_min, employees_max = _parse_range(record.get("numberOfEmployees"))
    revenue_ksek = _integer(record.get("revenue"))
    revenue_sek = None if revenue_ksek is None else revenue_ksek * 1_000
    location = record.get("location") if isinstance(record.get("location"), Mapping) else {}
    status = record.get("status") if isinstance(record.get("status"), Mapping) else {}
    year = record.get("companyAccountsLastUpdatedDate")
    return Company(
        organization_number=str(organization_number),
        name=str(name),
        sni_codes=_sni_codes(record.get("naceCategories")),
        municipality=location.get("municipality"),
        county=location.get("county"),
        postal_address=_address(record.get("postalAddress") or record.get("visitorAddress")),
        employee_class=_employee_class(record.get("numberOfEmployees"), employees_min),
        employee_min=employees_min,
        employee_max=employees_max,
        revenue_class=_revenue_class(revenue_ksek, year),
        revenue_min_sek=revenue_sek,
        revenue_max_sek=revenue_sek,
        active=str(status.get("status") or "ACTIVE").upper() == "ACTIVE",
        domain=_first_str(record.get("homePage")),
        source="Allabolag.se",
        retrieved_at=datetime.now(UTC),
    )


def _sni_codes(raw: Any) -> list[str]:
    values = raw if isinstance(raw, list) else []
    codes: list[str] = []
    for item in values:
        match = SNI_RE.match(str(item).replace(".", "").strip())
        if match:
            codes.append(match.group(1))
    return codes


def _address(raw: Any) -> str | None:
    if not isinstance(raw, Mapping):
        return None
    parts = [raw.get("addressLine"), raw.get("zipCode"), raw.get("postPlace")]
    joined = ", ".join(str(part) for part in parts if part)
    return joined or None


def _parse_range(value: Any) -> tuple[int | None, int | None]:
    if value in (None, ""):
        return None, None
    text = str(value).replace(" ", "").replace(",", "")
    if text.endswith("+"):
        low = _integer(text[:-1])
        return low, None
    if re.fullmatch(r"\d+-\d+", text):
        low, high = text.split("-", 1)
        return int(low), int(high)
    number = _integer(text)
    return number, number


def _employee_class(raw: Any, parsed_min: int | None) -> str | None:
    if raw in (None, ""):
        return None if parsed_min is None else str(parsed_min)
    return str(raw)


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    digits = str(value).replace(" ", "").replace(",", "")
    if digits in {"", "-", "None"} or not re.fullmatch(r"-?\d+(\.\d+)?", digits):
        return None
    return int(float(digits))


def _revenue_class(revenue_ksek: int | None, year: Any) -> str | None:
    if revenue_ksek is None:
        return None
    return f"{revenue_ksek} kSEK ({year or 'unknown'})"


def _first_str(value: Any) -> str | None:
    if not value:
        return None
    return str(value)
