from __future__ import annotations

from collections.abc import Callable

from lead_finder.config import Segment, Settings
from lead_finder.models import CompanySearchFilters
from lead_finder.providers.allabolag import AllabolagCompanyProvider, ProgressCallback
from lead_finder.use_company_search import SearchResult, search_companies


def crawl_allabolag(
    filters: CompanySearchFilters,
    segment: Segment,
    settings: Settings,
    *,
    ab_only: bool = True,
    on_progress: ProgressCallback | Callable[[int, int, int], None] | None = None,
) -> SearchResult:
    with AllabolagCompanyProvider(
        settings,
        ab_only=ab_only,
        on_progress=on_progress,
    ) as provider:
        return search_companies(provider, filters, segment)
