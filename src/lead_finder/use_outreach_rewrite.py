from __future__ import annotations

from lead_finder.config import Settings, get_settings
from lead_finder.matching import match_company
from lead_finder.matching_catalog import MatchingCatalog, load_matching_catalog
from lead_finder.models import ScoredCompany, WebsiteProfile
from lead_finder.outreach_sender import normalize_sender
from lead_finder.outreach_write import OutreachWriter
from lead_finder.use_company_search import SearchResult


def rewrite_outreach(
    result: SearchResult,
    organization_number: str,
    *,
    sender: str,
    settings: Settings | None = None,
    writer: OutreachWriter | None = None,
    catalog: MatchingCatalog | None = None,
) -> SearchResult:
    settings = settings or get_settings()
    sender = normalize_sender(sender)
    owns_writer = writer is None
    writer = writer or OutreachWriter(settings)
    catalog = catalog or load_matching_catalog()
    try:
        companies = [
            _rewrite(scored, organization_number, sender, writer, catalog)
            for scored in result.companies
        ]
        return SearchResult(companies=companies, summary=result.summary)
    finally:
        if owns_writer:
            writer.close()


def _rewrite(
    scored: ScoredCompany,
    organization_number: str,
    sender: str,
    writer: OutreachWriter,
    catalog: MatchingCatalog,
) -> ScoredCompany:
    draft = scored.outreach
    if scored.company.organization_number != organization_number or draft is None:
        return scored
    profile = (
        WebsiteProfile.model_validate(draft.website.model_dump(mode="json"))
        if draft.website is not None
        else None
    )
    if profile is None or not profile.url:
        return scored.model_copy(
            update={
                "outreach": draft.model_copy(
                    update={"detail": "No crawled website to rewrite from."}
                )
            }
        )
    match = scored.product_match or match_company(scored.company, catalog)
    outreach = writer.write(scored.company, profile, match, sender, previous=draft.body)
    return scored.model_copy(
        update={"product_match": match, "outreach": outreach}
    )
