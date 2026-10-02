from __future__ import annotations

import csv
import io
from urllib.parse import urlparse

from lead_finder.exporters.unique import unique_scored_companies
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
MATCH_FIELDNAMES = [
    "Recommended brand",
    "Recommended job",
    "Recommended product",
    "Alternative product",
    "Match confidence",
    "Match evidence",
    "Match status",
]
OUTREACH_FIELDNAMES = [
    "Website url",
    "Outreach status",
    "Customer fit",
    "Customer fit reason",
    "Outreach subject",
    "Outreach body",
    "Suggested recipient",
]


def export_hubspot_csv(companies: list[ScoredCompany]) -> str:
    records = unique_scored_companies(companies)
    include_match = any(item.product_match is not None for item in records)
    include_outreach = any(item.outreach is not None for item in records)
    fieldnames = list(FIELDNAMES)
    if include_match:
        fieldnames.extend(MATCH_FIELDNAMES)
    if include_outreach:
        fieldnames.extend(OUTREACH_FIELDNAMES)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for scored in records:
        writer.writerow(
            _row(scored, include_match=include_match, include_outreach=include_outreach)
        )
    return output.getvalue()


def _row(
    scored: ScoredCompany,
    *,
    include_match: bool,
    include_outreach: bool,
) -> dict[str, str]:
    company = scored.company
    row = {
        "Company name": company.name,
        "Company domain name": _domain(company.domain),
        "Organization number": company.organization_number,
        "Lead score": str(scored.score),
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
    if include_match:
        match = scored.product_match
        row.update(
            {
                "Recommended brand": "" if match is None else match.brand,
                "Recommended job": "" if match is None else match.job or "",
                "Recommended product": "" if match is None else match.primary or "",
                "Alternative product": "" if match is None else match.alternative or "",
                "Match confidence": "" if match is None else match.confidence,
                "Match evidence": "" if match is None else "; ".join(match.evidence),
                "Match status": "" if match is None else match.status,
            }
        )
    if include_outreach:
        draft = scored.outreach
        website = "" if draft is None or draft.website is None else draft.website.url
        row.update(
            {
                "Website url": website or company.domain or "",
                "Outreach status": "" if draft is None else draft.status,
                "Customer fit": "" if draft is None else draft.customer_fit,
                "Customer fit reason": "" if draft is None else draft.customer_fit_reason,
                "Outreach subject": "" if draft is None else draft.subject,
                "Outreach body": "" if draft is None else draft.body,
                "Suggested recipient": "" if draft is None else draft.suggested_recipient or "",
            }
        )
    return row


def _domain(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").removeprefix("www.").lower()
