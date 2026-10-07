from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from lead_finder.config import Settings, get_settings
from lead_finder.models import ScoredCompany, WebsiteProfile
from lead_finder.providers.website_crawl import WebsiteCrawler
from lead_finder.providers.website_search import (
    SearchBlocked,
    WebsiteFinder,
    build_website_finder,
)
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_crawl_store import crawl_record, notify_progress, store_crawl

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]
SEARCH_BLOCKED_NOTICE = "Search blocked this network. The remaining crawl has stopped."


@dataclass(frozen=True)
class LeadCrawlBatch:
    result: SearchResult
    records: list[dict[str, object]]
    notices: list[str]
    stopped: bool


def generate_leads(
    result: SearchResult,
    selected_org_numbers: list[str],
    *,
    settings: Settings | None = None,
    finder: WebsiteFinder | None = None,
    crawler: WebsiteCrawler | None = None,
    on_progress: ProgressCallback | None = None,
    on_notice: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> LeadCrawlBatch:
    settings = settings or get_settings()
    owned: list[object] = []
    if finder is None:
        finder = build_website_finder(settings)
        owned.append(finder)
    if crawler is None:
        shared = getattr(finder, "client", None)
        crawler = WebsiteCrawler(settings, client=shared)
        if shared is None:
            owned.append(crawler)
    selected = list(dict.fromkeys(selected_org_numbers))[: settings.outreach_max_selected]
    selected_set = set(selected)
    try:
        updated: list[ScoredCompany] = []
        records: list[dict[str, object]] = []
        notices: list[str] = []
        stopped = False
        done, total = 0, len(selected)
        for scored in result.companies:
            if scored.company.organization_number not in selected_set:
                updated.append(scored)
                continue
            if stopped or (should_stop is not None and should_stop()):
                stopped = True
                updated.append(scored)
                continue
            done += 1
            company, record, notice, stop = _crawl_company(
                scored,
                finder,
                crawler,
                on_progress=on_progress,
                should_stop=should_stop,
                done=done,
                total=total,
            )
            updated.append(company)
            if record is not None:
                records.append(record)
            if notice and notice not in notices:
                notices.append(notice)
                if on_notice is not None:
                    on_notice(notice)
            stopped = stop
        return LeadCrawlBatch(
            result=SearchResult(companies=updated, summary=result.summary),
            records=records,
            notices=notices,
            stopped=stopped,
        )
    finally:
        for item in owned:
            close = getattr(item, "close", None)
            if callable(close):
                close()


def _crawl_company(
    scored: ScoredCompany,
    finder: WebsiteFinder,
    crawler: WebsiteCrawler,
    *,
    on_progress: ProgressCallback | None,
    should_stop: Callable[[], bool] | None,
    done: int,
    total: int,
) -> tuple[ScoredCompany, dict[str, object] | None, str | None, bool]:
    company = scored.company
    source = "existing_domain" if company.domain else "google"
    notify_progress(on_progress, done - 1, total, f"{company.name}: finding website...")
    try:
        url = finder.find_website(company)
    except SearchBlocked as error:
        logger.warning("Search blocked company=%s detail=%s", company.name, error)
        record = crawl_record(
            company.name,
            None,
            status="search_blocked",
            crawl_detail=str(error)[:300],
        )
        return scored, record, SEARCH_BLOCKED_NOTICE, True
    except Exception as error:
        if _asked_to_stop(should_stop):
            return scored, None, None, True
        logger.warning("Search failed company=%s detail=%s", company.name, error)
        detail = str(error)[:300]
        failed, record = store_crawl(
            scored,
            "search_failed",
            detail,
            done,
            total,
            on_progress,
            profile=None,
        )
        return failed, record, f"Search failed for {company.name}: {detail}", False
    if not url:
        missed, record = store_crawl(
            scored,
            "no_website",
            "No official website found.",
            done,
            total,
            on_progress,
            profile=None,
        )
        return missed, record, None, False
    notice = _search_notice(finder, company.name)
    stop = bool(getattr(finder, "blocked_detail", None))
    company = company.model_copy(update={"domain": url})
    notify_progress(on_progress, done - 1, total, f"{company.name}: crawling {url}...")
    detail = ""
    status = "crawled"
    try:
        profile = crawler.crawl(url, source=source)
    except Exception as error:
        if _asked_to_stop(should_stop):
            return scored, None, None, True
        profile = WebsiteProfile(url=url, source=source)
        detail = f"crawl_failed: {error}"[:300]
        status = "crawl_failed"
        logger.warning("Crawl failed company=%s url=%s detail=%s", company.name, url, error)
        notice = notice or f"Crawl failed for {company.name}: {detail}"
    notify_progress(on_progress, done, total, f"{company.name}: done")
    stored, record = store_crawl(
        scored,
        status,
        detail,
        done,
        total,
        on_progress,
        profile=profile,
        company=company,
        notify=False,
    )
    return stored, record, notice, stop


def _asked_to_stop(should_stop: Callable[[], bool] | None) -> bool:
    return should_stop is not None and should_stop()


def _search_notice(finder: WebsiteFinder, company_name: str) -> str | None:
    if getattr(finder, "blocked_detail", None):
        return SEARCH_BLOCKED_NOTICE
    if getattr(finder, "request_failed", False):
        return f"Search failed for {company_name}. The crawl is continuing."
    return None
