from __future__ import annotations

import logging
from collections.abc import Callable

from lead_finder.config import Settings
from lead_finder.models import ScoredCompany
from lead_finder.providers.serper_search import SerperSearchError
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_crawl_store import store_crawl
from lead_finder.use_lead_job import LeadJob, _save_crawl, _set_message
from lead_finder.use_website_find import WebsiteFind, assign_serper_websites, miss_notice

logger = logging.getLogger(__name__)

ResolveWebsites = Callable[..., WebsiteFind]


def resolve_missing_websites(
    job: LeadJob,
    settings: Settings,
    resolve_websites: ResolveWebsites | None,
) -> tuple[SearchResult, dict[str, str]]:
    result = job.result
    missing = [org for org in job.pending if needs_website(result, org)]
    sources: dict[str, str] = {}
    if not missing or job.stop.is_set():
        return result, sources
    _set_message(job, "Finding websites...")
    resolve = resolve_websites or assign_serper_websites
    try:
        found = resolve(result, missing, settings=settings)
    except Exception as error:
        detail = str(error)[:300]
        if not isinstance(error, SerperSearchError):
            logger.exception("Website lookup failed")
        job.add_notice(detail)
        failed = mark_crawl(job, result, missing, "search_failed", detail)
        return failed, sources
    result = found.result
    if found.missed:
        job.add_notice(miss_notice(found.missed))
    missed = [org for org in missing if needs_website(result, org)]
    for org in missing:
        if org not in missed:
            sources[org] = "serper"
    if missed:
        result = mark_crawl(job, result, missed, "no_website", "No official website found.")
    with job.lock:
        job.result = result
    return result, sources


def mark_crawl(
    job: LeadJob,
    result: SearchResult,
    orgs: list[str],
    status: str,
    detail: str,
) -> SearchResult:
    for org in orgs:
        if job.stop.is_set():
            break
        scored = scored_company(result, org)
        if scored is None:
            continue
        stored, record = store_crawl(
            scored,
            status,
            detail,
            int(job.snapshot()["done"]),
            job.total,
            lambda _done, _total, message: _set_message(job, message),
            profile=None,
        )
        result = replace_company(result, stored)
        with job.lock:
            job.result = result
            job.done += 1
            job.records.append(record)
        _save_crawl(job, result, org)
    return result


def needs_website(result: SearchResult, org: str) -> bool:
    scored = scored_company(result, org)
    return scored is not None and not scored.company.domain


def scored_company(result: SearchResult, org: str) -> ScoredCompany | None:
    for item in result.companies:
        if item.company.organization_number == org:
            return item
    return None


def replace_company(result: SearchResult, scored: ScoredCompany) -> SearchResult:
    org = scored.company.organization_number
    companies = [
        scored if item.company.organization_number == org else item for item in result.companies
    ]
    return SearchResult(companies=companies, summary=result.summary)
