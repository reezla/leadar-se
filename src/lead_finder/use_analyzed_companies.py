from __future__ import annotations

from dataclasses import dataclass

from lead_finder.models import ScoredCompany
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_company_store import CompanyStore, SavedSearch
from lead_finder.use_saved_search import companies_in_saved_search

FAILED_CRAWL = {"crawl_failed", "search_failed", "no_website"}


@dataclass(frozen=True)
class AnalyzedFilters:
    text: str = ""
    website: str = "any"
    crawl: str = "any"
    email: str = "any"
    search_key: str = ""
    sni_codes: tuple[str, ...] = ()


def load_analyzed_companies(store: CompanyStore) -> SearchResult:
    companies = store.list_companies()
    return SearchResult(
        companies=companies,
        summary=SearchSummary(
            fetched=len(companies),
            matched=len(companies),
            incomplete=sum(bool(item.missing_data) for item in companies),
        ),
    )


def filter_analyzed(
    companies: list[ScoredCompany],
    filters: AnalyzedFilters,
    searches: list[SavedSearch] | None = None,
) -> list[ScoredCompany]:
    narrowed = _for_saved_search(companies, filters.search_key, searches or [])
    return [item for item in narrowed if _matches(item, filters)]


def sni_options(companies: list[ScoredCompany]) -> list[tuple[str, int]]:
    """SNI codes present in the saved companies, most common first."""
    counts: dict[str, int] = {}
    for item in companies:
        for code in dict.fromkeys(item.company.sni_codes):
            counts[code] = counts.get(code, 0) + 1
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))


def merge_analyzed(full: SearchResult, updated: SearchResult) -> SearchResult:
    by_org = {item.company.organization_number: item for item in updated.companies}
    companies = [
        by_org.get(item.company.organization_number, item) for item in full.companies
    ]
    return SearchResult(companies=companies, summary=full.summary)


def analyzed_summary(companies: list[ScoredCompany]) -> str:
    websites = sum(has_website(item) for item in companies)
    crawled = sum(item.crawl_status == "crawled" for item in companies)
    return f"{len(companies)} companies · {websites} with a website · {crawled} crawled"


def has_website(scored: ScoredCompany) -> bool:
    if scored.company.domain and scored.company.domain.strip():
        return True
    return bool(scored.website and scored.website.url.strip())


def has_email(scored: ScoredCompany) -> bool:
    profile = scored.website
    return bool(profile and profile.suggested_recipient and profile.suggested_recipient.strip())


def crawl_label(status: str | None) -> str:
    if status == "crawled":
        return "Crawled"
    if status == "crawl_failed":
        return "Crawl failed"
    if status == "search_failed":
        return "No website found"
    if status == "no_website":
        return "No website"
    if status:
        return status.replace("_", " ")
    return "Not crawled"


def _for_saved_search(
    companies: list[ScoredCompany],
    search_key: str,
    searches: list[SavedSearch],
) -> list[ScoredCompany]:
    if not search_key:
        return companies
    search = next((item for item in searches if item.query_key == search_key), None)
    if search is None:
        return []
    allowed = companies_in_saved_search(companies, search)
    return [item for item in companies if item.company.organization_number in allowed]


def _matches(scored: ScoredCompany, filters: AnalyzedFilters) -> bool:
    if not _matches_text(scored, filters.text):
        return False
    if filters.sni_codes and not set(scored.company.sni_codes) & set(filters.sni_codes):
        return False
    website = has_website(scored)
    if filters.website == "yes" and not website:
        return False
    if filters.website == "no" and website:
        return False
    status = scored.crawl_status or ""
    if filters.crawl == "crawled" and status != "crawled":
        return False
    if filters.crawl == "failed" and status not in FAILED_CRAWL:
        return False
    if filters.crawl == "missing" and status:
        return False
    email = has_email(scored)
    if filters.email == "yes" and not email:
        return False
    return not (filters.email == "no" and email)


def _matches_text(scored: ScoredCompany, text: str) -> bool:
    needle = text.casefold().strip()
    if not needle:
        return True
    company = scored.company
    if needle in company.name.casefold():
        return True
    if needle in company.organization_number:
        return True
    digits = "".join(character for character in needle if character.isdigit())
    return bool(digits) and digits in company.organization_number
