from __future__ import annotations

from dataclasses import dataclass

from lead_finder.config import Settings, get_settings
from lead_finder.models import ScoredCompany
from lead_finder.providers.serper_search import SerperClient, find_websites
from lead_finder.use_company_search import SearchResult


@dataclass(frozen=True)
class WebsiteFind:
    result: SearchResult
    found: int
    missed: list[str]


def assign_serper_websites(
    result: SearchResult,
    org_numbers: list[str],
    *,
    settings: Settings | None = None,
    client: SerperClient | None = None,
) -> WebsiteFind:
    settings = settings or get_settings()
    pending = _pending(result, org_numbers)
    if not pending:
        return WebsiteFind(result=result, found=0, missed=[])
    urls = find_websites(
        [scored.company.name for scored in pending],
        settings=settings,
        client=client,
    )
    saved = {
        scored.company.organization_number: _with_website(scored, url)
        for scored, url in zip(pending, urls, strict=True)
        if url
    }
    missed = [
        scored.company.name
        for scored, url in zip(pending, urls, strict=True)
        if not url
    ]
    companies = [
        saved.get(scored.company.organization_number, scored) for scored in result.companies
    ]
    return WebsiteFind(
        result=SearchResult(companies=companies, summary=result.summary),
        found=len(saved),
        missed=missed,
    )


def miss_notice(names: list[str]) -> str:
    shown = ", ".join(names[:5])
    extra = len(names) - 5
    if extra > 0:
        shown = f"{shown}, and {extra} more"
    return f"No website for {shown}."


def _pending(result: SearchResult, org_numbers: list[str]) -> list[ScoredCompany]:
    by_org = {item.company.organization_number: item for item in result.companies}
    pending: list[ScoredCompany] = []
    for org in dict.fromkeys(org_numbers):
        scored = by_org.get(org)
        if scored is None or scored.company.domain:
            continue
        pending.append(scored)
    return pending


def _with_website(scored: ScoredCompany, url: str) -> ScoredCompany:
    company = scored.company.model_copy(update={"domain": url})
    return scored.model_copy(update={"company": company})
