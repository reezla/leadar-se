from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping

from pydantic import ValidationError

from lead_finder.models import Company, ScoredCompany
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_result_selection import results_editor_key, selected_rows, selection_state

UPLOADED_KEY = "uploaded_result"
UPLOADED_LABEL = "Uploaded file"
SOURCE_KEYS = (
    (UPLOADED_KEY, UPLOADED_LABEL),
    ("search_result", "SCB search"),
    ("allabolag_result", "Allabolag"),
)


def source_entries(state: Mapping[str, object]) -> list[tuple[str, str, SearchResult]]:
    found: list[tuple[str, str, SearchResult]] = []
    for key, label in SOURCE_KEYS:
        result = state.get(key)
        if isinstance(result, SearchResult) and result.companies:
            found.append((key, label, result))
    return found


def load_saved_leads(raw: str | bytes) -> SearchResult:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("That file is not valid JSON.") from error
    companies = [_scored_record(item) for item in _company_records(payload)]
    if not companies:
        raise ValueError("The file has no companies.")
    return SearchResult(
        companies=companies,
        summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
    )


def desk_companies(result: SearchResult) -> list[ScoredCompany]:
    return list(result.companies)


def _company_records(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        companies = payload.get("companies")
        if isinstance(companies, list):
            return companies
    raise ValueError("Expected a leads file with a companies list.")


def _scored_record(item: object) -> ScoredCompany:
    if not isinstance(item, dict):
        raise ValueError("Each company must be an object.")
    try:
        if "company" in item:
            return ScoredCompany.model_validate(item)
        company = Company.model_validate(item)
    except ValidationError as error:
        raise ValueError(_validation_message(error)) from error
    return ScoredCompany(company=company, score=0, reasons=[])


def _validation_message(error: ValidationError) -> str:
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"Could not read companies ({location}: {first['msg']})."


def draft_status(scored: ScoredCompany) -> str:
    draft = scored.outreach
    if draft is not None and draft.body.strip():
        return "Drafted"
    if scored.website is None or not scored.website.url:
        return "No website"
    return "Ready"


def seed_email_selection(
    state: MutableMapping[str, object],
    session_key: str,
    result: SearchResult,
    analyzed: list[ScoredCompany],
) -> None:
    pick_key = f"email_pick_{session_key}"
    if pick_key in state:
        return
    nonce = int(state.get(f"{session_key}_nonce") or 0)
    picked = set(selected_rows(state.get(results_editor_key(session_key, nonce))))
    orgs = {
        result.companies[index].company.organization_number
        for index in picked
        if 0 <= index < len(result.companies)
    }
    rows = [
        index
        for index, scored in enumerate(analyzed)
        if scored.company.organization_number in orgs
    ]
    if rows:
        state[pick_key] = selection_state(rows)


def selected_org_numbers(companies: list[ScoredCompany], indices: list[int]) -> list[str]:
    chosen: list[str] = []
    for index in indices:
        if 0 <= index < len(companies):
            chosen.append(companies[index].company.organization_number)
    return list(dict.fromkeys(chosen))

