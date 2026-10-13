from __future__ import annotations

import httpx

from lead_finder.use_company_store import SaveOutcome

_CHUNK = 200


def delete_company_rows(
    client: httpx.Client,
    organization_numbers: list[str],
) -> SaveOutcome | None:
    orgs = _organization_numbers(organization_numbers)
    if orgs is None:
        return SaveOutcome(error="Organization number must be 10 digits.")
    for start in range(0, len(orgs), _CHUNK):
        failed = _delete_chunk(client, orgs[start : start + _CHUNK])
        if failed is not None:
            return failed
    return None


def _organization_numbers(values: list[str]) -> list[str] | None:
    seen: set[str] = set()
    orgs: list[str] = []
    for value in values:
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) != 10:
            return None
        if digits not in seen:
            seen.add(digits)
            orgs.append(digits)
    return orgs


def _delete_chunk(client: httpx.Client, organization_numbers: list[str]) -> SaveOutcome | None:
    listed = ",".join(organization_numbers)
    response = client.delete(
        "/companies",
        params={"organization_number": f"in.({listed})"},
        headers={"Prefer": "return=minimal"},
    )
    if response.status_code >= 400:
        detail = response.text.strip().replace("\n", " ")[:300]
        return SaveOutcome(error=f"Supabase returned {response.status_code}: {detail}")
    return None
