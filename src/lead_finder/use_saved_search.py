from __future__ import annotations

from datetime import UTC, datetime

from lead_finder.models import CompanySearchFilters, ScoredCompany
from lead_finder.scoring import filter_companies
from lead_finder.sni_catalog import SniCatalog, load_sni_catalog
from lead_finder.use_company_store import SavedSearch
from lead_finder.use_sni_selection import format_sni_label


def format_saved_search(item: SavedSearch) -> str:
    codes = ", ".join(item.sni_prefixes) or "No SNI"
    return " · ".join([*_search_parts(item, codes), _when(item.last_searched_at)])


def format_sni_search(item: SavedSearch, catalog: SniCatalog | None = None) -> str:
    table = catalog if catalog is not None else load_sni_catalog()
    names = ", ".join(format_sni_label(code, table) for code in item.sni_prefixes) or "No SNI"
    return " · ".join(_search_parts(item, names, employee_label=""))


def search_filter_options(searches: list[SavedSearch]) -> list[tuple[str, str]]:
    return [("", "Any"), *[(item.query_key, format_sni_search(item)) for item in searches]]


def companies_in_saved_search(companies: list[ScoredCompany], search: SavedSearch) -> set[str]:
    filters = CompanySearchFilters(
        sni_prefixes=list(search.sni_prefixes),
        counties=list(search.counties),
        municipalities=list(search.municipalities),
        employee_min=search.employee_min,
        employee_max=search.employee_max,
        revenue_min_sek=search.revenue_min_sek,
        revenue_max_sek=search.revenue_max_sek,
        active_only=search.active_only,
        text_query=search.text_query,
    )
    matched = filter_companies([item.company for item in companies], filters)
    return {company.organization_number for company in matched}


def _search_parts(
    item: SavedSearch,
    sni_label: str,
    *,
    employee_label: str = "employees",
) -> list[str]:
    parts = [sni_label]
    place = ", ".join([*item.counties, *item.municipalities])
    if place:
        parts.append(place)
    employees = _span(item.employee_min, item.employee_max, employee_label)
    if employees:
        parts.append(employees)
    revenue = _span(_msek(item.revenue_min_sek), _msek(item.revenue_max_sek), "MSEK")
    if revenue:
        parts.append(revenue)
    parts.append(f"{item.saved_count} companies")
    return parts


def _span(low: int | None, high: int | None, label: str) -> str:
    if low is None and high is None:
        return ""
    prefix = f"{label} " if label else ""
    if low is None:
        return f"{prefix}≤ {high}"
    if high is None:
        return f"{prefix}≥ {low}"
    return f"{prefix}{low}-{high}"


def _msek(value: int | None) -> int | None:
    if value is None:
        return None
    return value // 1_000_000


def _when(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
