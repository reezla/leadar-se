from __future__ import annotations

from collections.abc import Callable

from lead_finder.config import Settings, get_settings
from lead_finder.matching import match_company
from lead_finder.matching_catalog import MatchingCatalog, load_matching_catalog
from lead_finder.models import OutreachDraft, ScoredCompany
from lead_finder.outreach_sender import normalize_sender
from lead_finder.outreach_write import OutreachWriter
from lead_finder.use_company_search import SearchResult

ProgressCallback = Callable[[int, int, str], None]
NoticeCallback = Callable[[str], None]


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
    writer: OutreachWriter | None = None,
    catalog: MatchingCatalog | None = None,
    sender: str = "norrpoint",
    on_progress: ProgressCallback | None = None,
    on_notice: NoticeCallback | None = None,
) -> SearchResult:
    settings = settings or get_settings()
    sender = normalize_sender(sender)
    owns_writer = writer is None
    writer = writer or OutreachWriter(settings)
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
                _draft_company(
                    scored,
                    writer,
                    catalog,
                    sender=sender,
                    on_progress=on_progress,
                    on_notice=on_notice,
                    done=done,
                    total=total,
                )
            )
        return SearchResult(companies=updated, summary=result.summary)
    finally:
        if owns_writer:
            writer.close()


def _draft_company(
    scored: ScoredCompany,
    writer: OutreachWriter,
    catalog: MatchingCatalog,
    *,
    sender: str,
    on_progress: ProgressCallback | None,
    on_notice: NoticeCallback | None,
    done: int,
    total: int,
) -> ScoredCompany:
    company = scored.company
    if scored.crawl_status is None:
        _notify(on_progress, done, total, f"{company.name}: crawl first")
        return scored
    profile = scored.website
    if profile is None or not profile.url:
        _notify(on_progress, done, total, f"{company.name}: no website")
        return scored.model_copy(
            update={
                "outreach": OutreachDraft(
                    status="no_website",
                    detail=scored.crawl_detail or "No official website found.",
                )
            }
        )
    _notify(on_progress, done - 1, total, f"{company.name}: drafting email...")
    match = scored.product_match or match_company(company, catalog)
    outreach = writer.write(company, profile, match, sender)
    ai_detail = outreach.detail if outreach.detail.startswith("AI generation") else ""
    if scored.crawl_detail and not ai_detail:
        outreach = outreach.model_copy(update={"detail": scored.crawl_detail})
    if ai_detail and on_notice is not None:
        on_notice(ai_detail)
    _notify(on_progress, done, total, f"{company.name}: done")
    return scored.model_copy(update={"product_match": match, "outreach": outreach})


def _notify(on_progress: ProgressCallback | None, done: int, total: int, message: str) -> None:
    if on_progress is None:
        return
    on_progress(done, max(total, 1), message)
