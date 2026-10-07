from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lead_finder.config import Segment
from lead_finder.models import Company, CompanySearchFilters, ScoredCompany, ScoreReason


def filter_companies(companies: list[Company], filters: CompanySearchFilters) -> list[Company]:
    return [company for company in companies if _matches(company, filters)]


def score_company(
    company: Company,
    segment: Segment,
    filters: CompanySearchFilters,
    *,
    now: datetime | None = None,
) -> ScoredCompany:
    reasons: list[ScoreReason] = []
    weights = {
        "sni": 40,
        "keyword": 20,
        "size": 25,
        "geography": 10,
        "freshness": 5,
        **segment.weights,
    }

    matched_sni = next(
        (
            code
            for code in company.sni_codes
            if any(code.startswith(prefix) for prefix in segment.sni_prefixes)
        ),
        None,
    )
    if matched_sni:
        reasons.append(ScoreReason(label=f"Relevant SNI {matched_sni}", points=weights["sni"]))

    haystack = f"{company.name} {company.activity_description or ''}".casefold()
    matched_keywords = [keyword for keyword in segment.keywords if keyword.casefold() in haystack]
    if matched_keywords:
        reasons.append(
            ScoreReason(
                label=f"Relevant text: {', '.join(matched_keywords[:3])}",
                points=weights["keyword"],
            )
        )

    if _has_operational_size(company):
        reasons.append(
            ScoreReason(label="Company size indicates purchasing capacity", points=weights["size"])
        )

    if _in_selected_geography(company, filters):
        reasons.append(ScoreReason(label="Matches selected geography", points=weights["geography"]))

    current_time = now or datetime.now(UTC)
    retrieved_at = company.retrieved_at
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=UTC)
    if retrieved_at >= current_time - timedelta(days=30):
        reasons.append(
            ScoreReason(label="Recently retrieved source data", points=weights["freshness"])
        )

    missing_data = [
        label
        for value, label in (
            (company.sni_codes, "SNI"),
            (company.employee_class or company.employee_min, "employees"),
            (company.revenue_class or company.revenue_min_sek, "revenue"),
            (company.municipality or company.county, "geography"),
        )
        if not value
    ]
    return ScoredCompany(
        company=company,
        score=sum(reason.points for reason in reasons),
        reasons=reasons,
        missing_data=missing_data,
    )


def rank_companies(
    companies: list[Company],
    segment: Segment,
    filters: CompanySearchFilters,
) -> list[ScoredCompany]:
    scored = [score_company(company, segment, filters) for company in companies]
    return sorted(scored, key=lambda item: (-item.score, item.company.name.casefold()))


def _matches(company: Company, filters: CompanySearchFilters) -> bool:
    if filters.active_only and not company.active:
        return False
    if filters.sni_prefixes and not any(
        code.startswith(prefix) for code in company.sni_codes for prefix in filters.sni_prefixes
    ):
        return False
    if filters.counties and (company.county or "") not in filters.counties:
        return False
    if filters.municipalities and (company.municipality or "") not in filters.municipalities:
        return False
    if filters.text_query:
        haystack = f"{company.name} {company.activity_description or ''}".casefold()
        if filters.text_query.casefold() not in haystack:
            return False
    if not _range_overlaps(
        company.employee_min,
        company.employee_max,
        filters.employee_min,
        filters.employee_max,
    ):
        return False
    return _range_overlaps(
        company.revenue_min_sek,
        company.revenue_max_sek,
        filters.revenue_min_sek,
        filters.revenue_max_sek,
    )


def _range_overlaps(
    company_min: int | None,
    company_max: int | None,
    selected_min: int | None,
    selected_max: int | None,
) -> bool:
    if selected_min is None and selected_max is None:
        return True
    if company_min is None and company_max is None:
        return True
    if selected_min is not None and company_max is not None and company_max < selected_min:
        return False
    return not (selected_max is not None and company_min is not None and company_min > selected_max)


def _has_operational_size(company: Company) -> bool:
    if company.employee_max is not None:
        return company.employee_max >= 5
    if company.employee_min is not None:
        return company.employee_min >= 5
    return bool(company.employee_class and company.employee_class not in {"0", "0 anställda"})


def _in_selected_geography(company: Company, filters: CompanySearchFilters) -> bool:
    if not filters.counties and not filters.municipalities:
        return False
    return (not filters.counties or company.county in filters.counties) and (
        not filters.municipalities or company.municipality in filters.municipalities
    )
