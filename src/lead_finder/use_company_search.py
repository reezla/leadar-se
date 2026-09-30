from __future__ import annotations

from dataclasses import dataclass

from lead_finder.config import Segment
from lead_finder.models import CompanySearchFilters, ScoredCompany
from lead_finder.providers.base import CompanyProvider
from lead_finder.scoring import filter_companies, rank_companies


@dataclass(frozen=True)
class SearchSummary:
    fetched: int
    matched: int
    incomplete: int


@dataclass(frozen=True)
class SearchResult:
    companies: list[ScoredCompany]
    summary: SearchSummary


def search_companies(
    provider: CompanyProvider,
    filters: CompanySearchFilters,
    segment: Segment,
) -> SearchResult:
    fetched = provider.search(filters)
    matching = filter_companies(fetched, filters)
    ranked = rank_companies(matching, segment, filters)
    return SearchResult(
        companies=ranked,
        summary=SearchSummary(
            fetched=len(fetched),
            matched=len(ranked),
            incomplete=sum(bool(company.missing_data) for company in ranked),
        ),
    )
