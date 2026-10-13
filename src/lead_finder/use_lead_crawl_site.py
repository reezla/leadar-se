from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from lead_finder.models import Company, ScoredCompany, WebsiteProfile
from lead_finder.providers.website_search import _existing_website
from lead_finder.use_lead_crawl_store import ProgressCallback, notify_progress, store_crawl

logger = logging.getLogger(__name__)


class SiteCrawler(Protocol):
    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        """Fetch the company site and return the text we keep."""
        ...


def crawl_company_site(
    scored: ScoredCompany,
    crawler: SiteCrawler,
    *,
    source: str,
    on_progress: ProgressCallback | None = None,
    should_stop: Callable[[], bool] | None = None,
    done: int = 0,
    total: int = 1,
) -> tuple[ScoredCompany, dict[str, object] | None, str | None, bool]:
    url = _existing_website(scored.company.domain)
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
    company = scored.company.model_copy(update={"domain": url})
    return crawl_url(
        scored,
        company,
        url,
        source,
        crawler,
        on_progress=on_progress,
        should_stop=should_stop,
        done=done,
        total=total,
    )


def crawl_url(
    scored: ScoredCompany,
    company: Company,
    url: str,
    source: str,
    crawler: SiteCrawler,
    *,
    on_progress: ProgressCallback | None,
    should_stop: Callable[[], bool] | None,
    done: int,
    total: int,
) -> tuple[ScoredCompany, dict[str, object] | None, str | None, bool]:
    notify_progress(on_progress, done - 1, total, f"{company.name}: crawling {url}...")
    detail = ""
    status = "crawled"
    notice = None
    try:
        profile = crawler.crawl(url, source=source)
    except Exception as error:
        if should_stop is not None and should_stop():
            return scored, None, None, True
        profile = WebsiteProfile(url=url, source=source)
        detail = f"crawl_failed: {error}"[:300]
        status = "crawl_failed"
        logger.warning("Crawl failed company=%s url=%s detail=%s", company.name, url, error)
        notice = f"Crawl failed for {company.name}: {detail}"
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
    return stored, record, notice, False
