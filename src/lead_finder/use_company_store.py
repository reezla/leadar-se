from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from lead_finder.config import get_settings
from lead_finder.models import (
    Company,
    CompanyAnalysis,
    CompanySearchFilters,
    ScoredCompany,
    ScoreReason,
    WebsiteProfile,
)
from lead_finder.sni_resolve import expand_sni_prefixes
from lead_finder.use_company_search import SearchResult


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class SaveOutcome:
    error: str = ""


@dataclass(frozen=True)
class SavedSearch:
    query_key: str
    segment_key: str
    sni_prefixes: list[str]
    counties: list[str]
    municipalities: list[str]
    employee_min: int | None
    employee_max: int | None
    revenue_min_sek: int | None
    revenue_max_sek: int | None
    active_only: bool
    text_query: str | None
    result_limit: int | None
    fetched_count: int
    matched_count: int
    saved_count: int
    last_searched_at: datetime
    run_count: int


class CompanyStore(Protocol):
    def save_search(
        self,
        result: SearchResult,
        filters: CompanySearchFilters,
        segment_key: str,
    ) -> SaveOutcome: ...

    def save_companies(
        self,
        companies: list[ScoredCompany],
        *,
        include_crawl: bool = False,
    ) -> SaveOutcome: ...

    def patch_crawl(self, scored: ScoredCompany) -> SaveOutcome: ...

    def list_searches(self, limit: int = 20) -> list[SavedSearch]: ...

    def list_companies(self) -> list[ScoredCompany]: ...

    def delete_companies(self, organization_numbers: list[str]) -> SaveOutcome: ...


def query_key(segment_key: str, filters: CompanySearchFilters) -> str:
    payload = json.dumps(
        canonical_search(segment_key, filters),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical_search(segment_key: str, filters: CompanySearchFilters) -> dict[str, object]:
    prefixes = expand_sni_prefixes(list(filters.sni_prefixes))
    return {
        "segment_key": segment_key,
        "sni_prefixes": sorted(set(prefixes)),
        "counties": _sorted_text(filters.counties),
        "municipalities": _sorted_text(filters.municipalities),
        "employee_min": filters.employee_min,
        "employee_max": filters.employee_max,
        "revenue_min_sek": filters.revenue_min_sek,
        "revenue_max_sek": filters.revenue_max_sek,
        "active_only": filters.active_only,
        "text_query": _blank(filters.text_query),
        "result_limit": filters.limit,
    }


def company_row(scored: ScoredCompany) -> dict[str, object]:
    company = scored.company
    return {
        "organization_number": company.organization_number,
        "name": company.name,
        "workplace_name": company.workplace_name,
        "sni_codes": company.sni_codes,
        "activity_description": company.activity_description,
        "municipality": company.municipality,
        "county": company.county,
        "postal_address": company.postal_address,
        "employee_class": company.employee_class,
        "employee_min": company.employee_min,
        "employee_max": company.employee_max,
        "revenue_class": company.revenue_class,
        "revenue_min_sek": company.revenue_min_sek,
        "revenue_max_sek": company.revenue_max_sek,
        "active": company.active,
        "source": company.source,
        "retrieved_at": company.retrieved_at.isoformat(),
        "score": scored.score,
        "score_reasons": [reason.model_dump() for reason in scored.reasons],
        "missing_data": scored.missing_data,
    }


def enriched_row(scored: ScoredCompany, *, include_crawl: bool = False) -> dict[str, object]:
    row = company_row(scored)
    if scored.company.domain:
        row["domain"] = scored.company.domain
    if include_crawl and scored.crawl_status:
        row.update(crawl_patch(scored))
    if scored.analysis is not None:
        row.update(analysis_patch(scored.analysis))
    return row


def analysis_patch(analysis: CompanyAnalysis) -> dict[str, object]:
    return {
        "recommended_product": analysis.recommended_product,
        "alternative_products": [pick.product for pick in analysis.alternatives],
        "buyer_type": analysis.buyer_type or None,
        "customer_fit": analysis.customer_fit or None,
        "product_analysis": analysis.model_dump(mode="json"),
        "analyzed_at": analysis.analyzed_at.isoformat(),
    }


def analysis_from_row(row: dict[str, object]) -> CompanyAnalysis | None:
    payload = row.get("product_analysis")
    if isinstance(payload, str) and payload.strip():
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = None
    if not isinstance(payload, dict):
        return None
    try:
        return CompanyAnalysis.model_validate(payload)
    except ValueError:
        return None


def crawl_patch(scored: ScoredCompany) -> dict[str, object]:
    profile = scored.website
    pages: list[str] = []
    if profile is not None:
        pages = [text for page in profile.pages_fetched if (text := _db_text(page))]
    patch: dict[str, object] = {
        "about_text": None if profile is None else _db_text(profile.about_text),
        "projects_text": None if profile is None else _db_text(profile.projects_text),
        "pages_fetched": pages,
        "website_source": None if profile is None else _db_text(profile.source),
        "suggested_recipient": None if profile is None else _db_text(profile.suggested_recipient),
        "crawl_status": scored.crawl_status,
        "crawl_detail": _db_text(scored.crawl_detail) or "",
    }
    if scored.company.domain:
        patch["domain"] = _db_text(scored.company.domain)
    return patch


def scored_from_store_row(row: dict[str, object]) -> ScoredCompany:
    scored = _scored_from_row(row)
    analysis = analysis_from_row(row)
    if analysis is None:
        return scored
    from lead_finder.analysis import apply_analysis

    return apply_analysis(scored, analysis)


def _scored_from_row(row: dict[str, object]) -> ScoredCompany:
    domain = _blank(row.get("domain"))
    about = _blank(row.get("about_text"))
    projects = _blank(row.get("projects_text"))
    source = _blank(row.get("website_source"))
    email = _blank(row.get("suggested_recipient"))
    pages = _texts(row.get("pages_fetched"))
    website = None
    if domain or about or projects or pages or source or email:
        website = WebsiteProfile(
            url=domain or "",
            about_text=about,
            projects_text=projects,
            pages_fetched=pages,
            source=source or "google",
            suggested_recipient=email,
        )
    retrieved = row.get("retrieved_at")
    retrieved_at = datetime.now(UTC)
    if isinstance(retrieved, str) and retrieved.strip():
        retrieved_at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    return ScoredCompany(
        company=Company(
            organization_number=str(row["organization_number"]),
            name=str(row.get("name") or ""),
            workplace_name=_blank(row.get("workplace_name")),
            sni_codes=_texts(row.get("sni_codes")),
            activity_description=_blank(row.get("activity_description")),
            municipality=_blank(row.get("municipality")),
            county=_blank(row.get("county")),
            postal_address=_blank(row.get("postal_address")),
            employee_class=_blank(row.get("employee_class")),
            employee_min=_optional_int(row.get("employee_min")),
            employee_max=_optional_int(row.get("employee_max")),
            revenue_class=_blank(row.get("revenue_class")),
            revenue_min_sek=_optional_int(row.get("revenue_min_sek")),
            revenue_max_sek=_optional_int(row.get("revenue_max_sek")),
            active=bool(row.get("active", True)),
            domain=domain,
            source=str(row.get("source") or "SCB Företagsregistret"),
            retrieved_at=retrieved_at,
        ),
        score=int(row.get("score") or 0),
        reasons=_reasons(row.get("score_reasons")),
        missing_data=_texts(row.get("missing_data")),
        website=website,
        crawl_status=_blank(row.get("crawl_status")),
        crawl_detail=str(row.get("crawl_detail") or ""),
    )


def get_company_store() -> CompanyStore | None:
    settings = get_settings()
    url = (settings.supabase_url or "").strip()
    secret = (settings.supabase_secret_key or "").strip()
    if not url or not secret:
        return None
    from lead_finder.company_store_client import HttpCompanyStore

    return HttpCompanyStore(url, secret)


def _sorted_text(values: list[str]) -> list[str]:
    return sorted({item.strip() for item in values if item and item.strip()})


def _db_text(value: str | None) -> str | None:
    return None if value is None else value.replace("\x00", "")


def _blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _reasons(value: object) -> list[ScoreReason]:
    if not isinstance(value, list):
        return []
    reasons: list[ScoreReason] = []
    for item in value:
        if not isinstance(item, dict) or "label" not in item:
            continue
        reasons.append(ScoreReason(label=str(item["label"]), points=int(item.get("points") or 0)))
    return reasons
