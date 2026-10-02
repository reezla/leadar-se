from __future__ import annotations

import json
from collections.abc import Callable

from lead_finder.config import Settings, get_settings
from lead_finder.matching import match_company
from lead_finder.matching_catalog import MatchingCatalog, load_matching_catalog
from lead_finder.models import OutreachDraft, ScoredCompany, WebsiteProfile
from lead_finder.outreach_sender import normalize_sender
from lead_finder.outreach_write import OutreachWriter
from lead_finder.providers.website_crawl import WebsiteCrawler
from lead_finder.providers.website_search import WebsiteFinder, build_website_finder
from lead_finder.use_company_search import SearchResult

ProgressCallback = Callable[[int, int, str], None]


def resolve_outreach_selection(
    current: list[str],
    stored: list[str],
    *,
    clicked: bool,
) -> tuple[list[str], list[str]]:
    current = list(dict.fromkeys(current))
    stored = list(dict.fromkeys(stored))
    if clicked:
        return current or stored, []
    return current, current


def generate_outreach(
    result: SearchResult,
    selected_org_numbers: list[str],
    *,
    settings: Settings | None = None,
    finder: WebsiteFinder | None = None,
    crawler: WebsiteCrawler | None = None,
    writer: OutreachWriter | None = None,
    catalog: MatchingCatalog | None = None,
    sender: str = "norrpoint",
    on_progress: ProgressCallback | None = None,
) -> SearchResult:
    settings = settings or get_settings()
    sender = normalize_sender(sender)
    owned: list[object] = []
    if finder is None:
        finder = build_website_finder(settings)
        owned.append(finder)
    if crawler is None:
        shared = getattr(finder, "client", None)
        crawler = WebsiteCrawler(settings, client=shared)
        if shared is None:
            owned.append(crawler)
    if writer is None:
        writer = OutreachWriter(settings)
        owned.append(writer)
    catalog = catalog or load_matching_catalog()
    selected = list(dict.fromkeys(selected_org_numbers))[: settings.outreach_max_selected]
    selected_set = set(selected)
    try:
        updated, done = [], 0
        total = len(selected)
        for scored in result.companies:
            if scored.company.organization_number not in selected_set:
                updated.append(scored)
                continue
            done += 1
            updated.append(
                _process_company(
                    scored,
                    finder,
                    crawler,
                    writer,
                    catalog,
                    sender=sender,
                    on_progress=on_progress,
                    done=done,
                    total=total,
                )
            )
        return SearchResult(companies=updated, summary=result.summary)
    finally:
        for item in owned:
            close = getattr(item, "close", None)
            if callable(close):
                close()


def _process_company(
    scored: ScoredCompany,
    finder: WebsiteFinder,
    crawler: WebsiteCrawler,
    writer: OutreachWriter,
    catalog: MatchingCatalog,
    *,
    sender: str,
    on_progress: ProgressCallback | None,
    done: int,
    total: int,
) -> ScoredCompany:
    company = scored.company
    source = "existing_domain" if company.domain else "google"
    _notify(on_progress, done - 1, total, f"{company.name}: finding website...")
    try:
        url = finder.find_website(company)
    except Exception as error:
        return scored.model_copy(
            update={
                "outreach": OutreachDraft(
                    status="no_website",
                    detail=str(error)[:300],
                )
            }
        )
    if not url:
        return scored.model_copy(
            update={
                "outreach": OutreachDraft(
                    status="no_website",
                    detail="No official website found.",
                )
            }
        )
    company = company.model_copy(update={"domain": url})
    _notify(on_progress, done - 1, total, f"{company.name}: crawling {url}...")
    detail = ""
    try:
        profile = crawler.crawl(url, source=source)
    except Exception as error:
        profile = WebsiteProfile(url=url, source=source)
        detail = f"crawl_failed: {error}"[:300]
    _log_website_crawl(company.name, profile, crawl_detail=detail)
    match = scored.product_match or match_company(company, catalog)
    _notify(on_progress, done - 1, total, f"{company.name}: drafting email...")
    outreach = writer.write(company, profile, match, sender)
    if detail:
        outreach = outreach.model_copy(update={"detail": detail})
    _notify(on_progress, done, total, f"{company.name}: done")
    return scored.model_copy(
        update={"company": company, "product_match": match, "outreach": outreach}
    )


def _notify(on_progress: ProgressCallback | None, done: int, total: int, message: str) -> None:
    if on_progress is None:
        return
    on_progress(done, max(total, 1), message)


def _log_website_crawl(
    company_name: str,
    profile: WebsiteProfile,
    *,
    crawl_detail: str = "",
) -> None:
    payload: dict[str, object] = {
        "company": company_name,
        "website": profile.model_dump(mode="json"),
    }
    if crawl_detail:
        payload["crawl_detail"] = crawl_detail
    print(
        "Website crawl result:",
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        flush=True,
    )
