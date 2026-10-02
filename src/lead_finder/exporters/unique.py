from __future__ import annotations

from lead_finder.models import ScoredCompany


def unique_scored_companies(companies: list[ScoredCompany]) -> list[ScoredCompany]:
    by_org: dict[str, ScoredCompany] = {}
    for scored in companies:
        key = scored.company.organization_number
        current = by_org.get(key)
        if current is None or scored.score > current.score:
            by_org[key] = scored
    return sorted(
        by_org.values(),
        key=lambda item: (-item.score, item.company.name.casefold()),
    )
