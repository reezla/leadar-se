from __future__ import annotations

from typing import Protocol

from lead_finder.models import Company, CompanySearchFilters


class CompanyProvider(Protocol):
    def search(self, filters: CompanySearchFilters) -> list[Company]:
        """Return normalized companies matching source-supported filters."""
        ...
