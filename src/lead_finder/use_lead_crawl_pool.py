from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from lead_finder.analysis import ProductAnalyzer, analyze_scored
from lead_finder.config import Settings, get_settings
from lead_finder.models import ScoredCompany
from lead_finder.providers.website_crawl import WebsiteCrawler
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_crawl_lookup import (
    ResolveWebsites,
    replace_company,
    resolve_missing_websites,
    scored_company,
)
from lead_finder.use_lead_crawl_site import SiteCrawler, crawl_company_site
from lead_finder.use_lead_crawl_store import crawl_record
from lead_finder.use_lead_job import LeadJob, _finish, _save_crawl, _set_message

logger = logging.getLogger(__name__)

CrawlResult = tuple[ScoredCompany, dict[str, object] | None, str | None, bool]


def crawl_pending(
    job: LeadJob,
    *,
    settings: Settings | None = None,
    crawler: SiteCrawler | None = None,
    resolve_websites: ResolveWebsites | None = None,
    analyzer: ProductAnalyzer | None = None,
) -> None:
    settings = settings or get_settings()
    owned: WebsiteCrawler | None = None
    owned_analyzer: ProductAnalyzer | None = None
    if crawler is None:
        owned = WebsiteCrawler(settings)
        crawler = owned
    if analyzer is None:
        owned_analyzer = _build_analyzer(settings)
        analyzer = owned_analyzer
    job.client = getattr(crawler, "client", None)
    try:
        result, sources = resolve_missing_websites(job, settings, resolve_websites)
        _crawl_ready(job, result, crawler, settings, sources, analyzer)
    except Exception as error:
        done = int(job.snapshot()["done"])
        if job.stop.is_set():
            _finish(job, done)
            return
        logger.exception("Lead crawl failed")
        job.add_notice(f"Lead crawl failed: {error}")
        with job.lock:
            job.error = str(error)
            job.done = done
            job.phase = "done"
    finally:
        job.client = None
        if owned is not None:
            owned.close()
        if owned_analyzer is not None:
            owned_analyzer.close()


def has_saved_site_text(scored: ScoredCompany) -> bool:
    """Already crawled with usable text: analyze it again instead of re-crawling the site."""
    profile = scored.website
    if scored.crawl_status != "crawled" or profile is None:
        return False
    return bool((profile.about_text or "").strip() or (profile.projects_text or "").strip())


def _build_analyzer(settings: Settings) -> ProductAnalyzer | None:
    try:
        return ProductAnalyzer(settings)
    except Exception:
        logger.exception("Product analysis is unavailable")
        return None


def _crawl_ready(
    job: LeadJob,
    result: SearchResult,
    crawler: SiteCrawler,
    settings: Settings,
    sources: dict[str, str],
    analyzer: ProductAnalyzer | None = None,
) -> None:
    ready = [
        scored
        for org in job.pending
        if (scored := scored_company(result, org)) is not None and scored.company.domain
    ]
    if ready and not job.stop.is_set():
        workers = max(1, min(settings.website_crawl_concurrency, len(ready)))
        _run_pool(job, result, crawler, ready, sources, workers, analyzer)
    _finish(job, int(job.snapshot()["done"]))


def _run_pool(
    job: LeadJob,
    result: SearchResult,
    crawler: SiteCrawler,
    ready: list[ScoredCompany],
    sources: dict[str, str],
    workers: int,
    analyzer: ProductAnalyzer | None = None,
) -> None:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: dict[Future[CrawlResult], str] = {}
        for scored in ready:
            if job.stop.is_set():
                break
            org = scored.company.organization_number
            source = sources.get(org, "existing_domain")
            futures[pool.submit(_crawl_one, job, scored, crawler, source, analyzer)] = org
        for future in as_completed(futures):
            result = _collect(job, result, futures[future], future)


def _crawl_one(
    job: LeadJob,
    scored: ScoredCompany,
    crawler: SiteCrawler,
    source: str,
    analyzer: ProductAnalyzer | None = None,
) -> CrawlResult:
    if job.stop.is_set():
        return scored, None, None, True
    if has_saved_site_text(scored):
        _set_message(job, f"{scored.company.name}: recommending scanners...")
        stored = analyze_scored(scored, analyzer)
        record = crawl_record(
            scored.company.name,
            stored.website,
            status="crawled",
            crawl_detail="Reused saved website text; scanners recommended.",
        )
        return stored, record, None, False
    stored, record, notice, stop = crawl_company_site(
        scored,
        crawler,
        source=source,
        on_progress=lambda _done, _total, message: _set_message(job, message),
        should_stop=job.stop.is_set,
        total=job.total,
    )
    if record is not None and not job.stop.is_set():
        _set_message(job, f"{stored.company.name}: recommending scanners...")
        stored = analyze_scored(stored, analyzer)
    return stored, record, notice, stop


def _collect(
    job: LeadJob,
    result: SearchResult,
    org: str,
    future: Future[CrawlResult],
) -> SearchResult:
    try:
        stored, record, notice, stop = future.result()
    except Exception as error:
        if not job.stop.is_set():
            logger.exception("Lead crawl failed org=%s", org)
            job.add_notice(f"Lead crawl failed: {error}")
        return result
    if notice:
        job.add_notice(notice)
    if stop and not job.stop.is_set():
        with job.lock:
            job.stopped = True
    if record is None:
        return result
    result = replace_company(result, stored)
    with job.lock:
        job.result = result
        job.done += 1
        job.records.append(record)
    _save_crawl(job, result, org)
    return result
