from __future__ import annotations

from collections.abc import MutableMapping

from lead_finder.models import ScoredCompany
from lead_finder.use_company_search import SearchResult, SearchSummary


def delete_targets(companies: list[ScoredCompany]) -> list[dict[str, str]]:
    seen: set[str] = set()
    targets: list[dict[str, str]] = []
    for item in companies:
        org = item.company.organization_number
        if not org or org in seen:
            continue
        seen.add(org)
        name = item.company.name.strip()
        targets.append(
            {
                "organization_number": org,
                "label": f"{name} ({org})" if name else org,
            }
        )
    return targets


def without_organizations(result: SearchResult, organization_numbers: set[str]) -> SearchResult:
    companies = [
        item
        for item in result.companies
        if item.company.organization_number not in organization_numbers
    ]
    return SearchResult(
        companies=companies,
        summary=SearchSummary(
            fetched=len(companies),
            matched=len(companies),
            incomplete=sum(bool(item.missing_data) for item in companies),
        ),
    )


def forget_deleted_companies(
    state: MutableMapping[str, object],
    *,
    session_key: str,
    catalog_key: str,
    organization_numbers: set[str],
) -> None:
    for key in (catalog_key, session_key):
        current = state.get(key)
        if isinstance(current, SearchResult):
            state[key] = without_organizations(current, organization_numbers)
    if state.get(f"{session_key}_display_org") in organization_numbers:
        state.pop(f"{session_key}_display_org", None)
        state.pop(f"sheet_pick_{session_key}", None)
    stored_key = f"{session_key}_outreach_orgs"
    stored = state.get(stored_key)
    if isinstance(stored, list):
        state[stored_key] = [org for org in stored if org not in organization_numbers]
    nonce_key = f"{session_key}_nonce"
    state[nonce_key] = int(state.get(nonce_key) or 0) + 1
