from __future__ import annotations

import csv
import io
from urllib.parse import urlparse

from lead_finder.models import ScoredCompany

FIELDNAMES = [
    "Company name",
    "Company domain name",
    "Organization number",
    "Lead score",
    "Lead score reasons",
    "Industry codes (SNI)",
    "City",
    "State/Region",
    "Street address",
    "Employee size class",
    "Revenue size class",
    "Data completeness warnings",
    "Lead source",
    "Source retrieved at",
]


def export_hubspot_csv(companies: list[ScoredCompany]) -> str:
    deduplicated: dict[str, ScoredCompany] = {}
    for scored in companies:
        key = scored.company.organization_number
        current = deduplicated.get(key)
        if current is None or scored.score > current.score:
            deduplicated[key] = scored

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES)
    writer.writeheader()
    for scored in sorted(
        deduplicated.values(), key=lambda item: (-item.score, item.company.name.casefold())
    ):
        company = scored.company
        writer.writerow(
            {
                "Company name": company.name,
                "Company domain name": _domain(company.domain),
                "Organization number": company.organization_number,
                "Lead score": scored.score,
                "Lead score reasons": "; ".join(
                    f"{reason.label} (+{reason.points})" for reason in scored.reasons
                ),
                "Industry codes (SNI)": "; ".join(company.sni_codes),
                "City": company.municipality or "",
                "State/Region": company.county or "",
                "Street address": company.postal_address or "",
                "Employee size class": company.employee_class or "",
                "Revenue size class": company.revenue_class or "",
                "Data completeness warnings": "; ".join(scored.missing_data),
                "Lead source": company.source,
                "Source retrieved at": company.retrieved_at.isoformat(),
            }
        )
    return output.getvalue()


def _domain(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").removeprefix("www.").lower()
