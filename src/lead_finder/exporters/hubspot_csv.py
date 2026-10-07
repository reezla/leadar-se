from __future__ import annotations

import csv
import io
from urllib.parse import urlparse

from lead_finder.exporters.unique import unique_scored_companies
from lead_finder.models import ScoredCompany, WebsiteProfile

# Semicolon matches the list separator in Swedish Excel, so each header opens as its own column.
DELIMITER = ";"
FIELDNAMES = [
    "Company name",
    "Company domain name",
    "Suggested recipient",
    "Organization number",
    "Lead score",
    "Industry codes (SNI)",
    "City",
    "State/Region",
    "Street address",
    "Employee size class",
    "Revenue size class",
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
WEBSITE_FIELDNAMES = [
    "Website url",
    "About text",
    "Projects text",
    "Pages fetched",
]
OUTREACH_FIELDNAMES = [
    "Outreach status",
    "Customer fit",
    "Customer fit reason",
    "Outreach subject",
    "Outreach body",
]


def export_hubspot_csv(companies: list[ScoredCompany]) -> str:
    records = unique_scored_companies(companies)
    include_match = any(item.product_match is not None for item in records)
    include_website = any(_profile(item) is not None for item in records)
    include_outreach = any(item.outreach is not None for item in records)
    fieldnames = list(FIELDNAMES)
    if include_website:
        fieldnames.extend(WEBSITE_FIELDNAMES)
    if include_match:
        fieldnames.extend(MATCH_FIELDNAMES)
    if include_outreach:
        fieldnames.extend(OUTREACH_FIELDNAMES)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=DELIMITER)
    writer.writeheader()
    for scored in records:
        writer.writerow(
            _row(
                scored,
                include_match=include_match,
                include_website=include_website,
                include_outreach=include_outreach,
            )
        )
    return output.getvalue()


def _row(
    scored: ScoredCompany,
    *,
    include_match: bool,
    include_website: bool,
    include_outreach: bool,
) -> dict[str, str]:
    company = scored.company
    row = {
        "Company name": company.name,
        "Company domain name": _domain(company.domain),
        "Suggested recipient": _recipient(scored),
        "Organization number": company.organization_number,
        "Lead score": str(scored.score),
        "Industry codes (SNI)": "; ".join(company.sni_codes),
        "City": company.municipality or "",
        "State/Region": company.county or "",
        "Street address": company.postal_address or "",
        "Employee size class": company.employee_class or "",
        "Revenue size class": company.revenue_class or "",
        "Lead source": company.source,
        "Source retrieved at": company.retrieved_at.isoformat(),
    }
    if include_website:
        row.update(_website_columns(scored))
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
        row.update(
            {
                "Outreach status": "" if draft is None else draft.status,
                "Customer fit": "" if draft is None else draft.customer_fit,
                "Customer fit reason": "" if draft is None else draft.customer_fit_reason,
                "Outreach subject": "" if draft is None else draft.subject,
                "Outreach body": "" if draft is None else draft.body,
            }
        )
    return row


def _website_columns(scored: ScoredCompany) -> dict[str, str]:
    profile = _profile(scored)
    url = "" if profile is None else profile.url
    return {
        "Website url": url or scored.company.domain or "",
        "About text": "" if profile is None else profile.about_text or "",
        "Projects text": "" if profile is None else profile.projects_text or "",
        "Pages fetched": "" if profile is None else "; ".join(profile.pages_fetched),
    }


def _recipient(scored: ScoredCompany) -> str:
    profile = _profile(scored)
    draft = scored.outreach
    if profile is not None and profile.suggested_recipient:
        return profile.suggested_recipient
    if draft is not None and draft.suggested_recipient:
        return draft.suggested_recipient
    return ""


def _profile(scored: ScoredCompany) -> WebsiteProfile | None:
    if scored.website is not None:
        return scored.website
    if scored.outreach is not None and scored.outreach.website is not None:
        return scored.outreach.website
    return None


def _domain(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").removeprefix("www.").lower()
