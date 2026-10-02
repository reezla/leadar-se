from __future__ import annotations

from dataclasses import dataclass

from lead_finder.matching_catalog import JobRule, MatchingCatalog, load_matching_catalog
from lead_finder.models import Company, ProductMatch


@dataclass(frozen=True)
class JobHit:
    job: JobRule
    sni_hit: str | None
    keyword_hits: list[str]
    confidence: str
    status: str


def match_company(
    company: Company,
    catalog: MatchingCatalog | None = None,
) -> ProductMatch:
    catalog = catalog or load_matching_catalog()
    haystack = _haystack(company)
    norrpoint = _best_hit(company, catalog, haystack, "norrpoint")
    metricop = _best_hit(company, catalog, haystack, "metricop")
    return _product_match(norrpoint, metricop, catalog)


def _haystack(company: Company) -> str:
    return " ".join(
        part
        for part in (company.name, company.activity_description, company.domain)
        if part
    ).casefold()


def _best_hit(
    company: Company,
    catalog: MatchingCatalog,
    haystack: str,
    brand: str,
) -> JobHit | None:
    hits = [
        hit
        for job in catalog.jobs
        if job.brand == brand
        for hit in [_evaluate_job(company, job, haystack)]
        if hit is not None
    ]
    return hits[0] if hits else None


def _evaluate_job(company: Company, job: JobRule, haystack: str) -> JobHit | None:
    if not _employee_ok(company, job):
        return None
    sni_hit = _sni_hit(company, job)
    keyword_hits = [word for word in job.keywords if word.casefold() in haystack]
    if job.require_keywords and not keyword_hits:
        return None
    if not sni_hit and not keyword_hits:
        return None
    if keyword_hits and sni_hit:
        confidence, status = "high", "matched"
    elif keyword_hits:
        confidence, status = "medium", "matched"
    else:
        confidence, status = "low", job.sni_only_status
    return JobHit(
        job=job,
        sni_hit=sni_hit,
        keyword_hits=keyword_hits,
        confidence=confidence,
        status=status,
    )


def _sni_hit(company: Company, job: JobRule) -> str | None:
    primary = company.sni_codes[0] if company.sni_codes else None
    if primary is None:
        return None
    if any(primary.startswith(prefix) for prefix in job.sni_prefixes):
        return primary
    return None


def _employee_ok(company: Company, job: JobRule) -> bool:
    if job.employee_min is not None and not _size_at_least(company, job.employee_min):
        return False
    return job.employee_max is None or _size_at_most(company, job.employee_max)


def _size_at_least(company: Company, minimum: int) -> bool:
    if company.employee_max is not None:
        return company.employee_max >= minimum
    if company.employee_min is not None:
        return company.employee_min >= minimum
    return False


def _size_at_most(company: Company, maximum: int) -> bool:
    if company.employee_max is not None:
        return company.employee_max <= maximum
    if company.employee_min is not None:
        return company.employee_min <= maximum
    return False


def _product_match(
    norrpoint: JobHit | None,
    metricop: JobHit | None,
    catalog: MatchingCatalog,
) -> ProductMatch:
    if norrpoint is None and metricop is None:
        return ProductMatch(evidence=["No product-job signals in SNI, name, or activity"])
    norrpoint_ok = norrpoint is not None and norrpoint.status == "matched"
    metricop_ok = metricop is not None and metricop.status == "matched"
    brand = _brand(norrpoint_ok, metricop_ok)
    primary_hit = norrpoint if norrpoint_ok else metricop if metricop_ok else None
    return ProductMatch(
        job=_job_label(norrpoint, metricop),
        brand=brand,
        primary=catalog.family_name(primary_hit.job.primary) if primary_hit else None,
        alternative=_alternative(
            norrpoint if norrpoint_ok else None,
            metricop if metricop_ok else None,
            catalog,
        ),
        confidence=_confidence(
            norrpoint if norrpoint_ok else None,
            metricop if metricop_ok else None,
        ),
        evidence=_evidence(norrpoint, metricop, catalog),
        status="matched" if primary_hit else "needs_review",
    )


def _brand(norrpoint_ok: bool, metricop_ok: bool) -> str:
    if norrpoint_ok and metricop_ok:
        return "norrpoint; metricop"
    if norrpoint_ok:
        return "norrpoint"
    if metricop_ok:
        return "metricop"
    return "none"


def _job_label(norrpoint: JobHit | None, metricop: JobHit | None) -> str:
    names = [hit.job.name for hit in (norrpoint, metricop) if hit is not None]
    return "; ".join(names)


def _alternative(
    norrpoint: JobHit | None,
    metricop: JobHit | None,
    catalog: MatchingCatalog,
) -> str | None:
    if norrpoint is not None and metricop is not None:
        return catalog.family_name(metricop.job.primary)
    if norrpoint is None:
        return None
    return catalog.family_name(norrpoint.job.alternative)


def _confidence(norrpoint: JobHit | None, metricop: JobHit | None) -> str:
    ranks = {"high": 3, "medium": 2, "low": 1}
    hits = [hit.confidence for hit in (norrpoint, metricop) if hit is not None]
    return max(hits, key=lambda item: ranks[item]) if hits else "low"


def _evidence(
    norrpoint: JobHit | None,
    metricop: JobHit | None,
    catalog: MatchingCatalog,
) -> list[str]:
    parts: list[str] = []
    for hit in (norrpoint, metricop):
        if hit is None:
            continue
        details: list[str] = []
        if hit.sni_hit:
            details.append(f"SNI {hit.sni_hit}")
        if hit.keyword_hits:
            details.append("text: " + ", ".join(hit.keyword_hits[:3]))
        label = hit.job.name
        if hit.status == "matched" and hit.job.primary:
            label = f"{label} → {catalog.family_name(hit.job.primary)}"
        elif hit.status == "needs_review":
            label = f"{label} needs review"
        parts.append(f"{label} ({', '.join(details)})" if details else label)
    return parts
