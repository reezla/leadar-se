from __future__ import annotations

from lead_finder.models import OutreachDraft, ProductMatch, ScoredCompany, WebsiteProfile


def result_columns(
    *,
    include_match: bool,
    include_crawl: bool = False,
    include_outreach: bool = False,
) -> list[str]:
    leading = ["Score", "Company", "Analyzed", "Org. number", "Website", "Email"]
    crawl = ["About", "Projects"]
    match = ["Job", "Brand", "Primary", "Alternative", "Confidence", "Evidence"]
    outreach = ["Outreach", "Fit", "Subject", "Email body"]
    trailing = ["SNI", "Municipality", "Employees", "Revenue", "Missing"]
    columns = leading
    if include_crawl:
        columns = [*columns, *crawl]
    if include_match:
        columns = [*columns, *match]
    if include_outreach:
        columns = [*columns, *outreach]
    return [*columns, *trailing]


def result_row(
    scored: ScoredCompany,
    *,
    include_match: bool,
    include_crawl: bool = False,
    include_outreach: bool = False,
) -> dict[str, object]:
    row: dict[str, object] = {
        "Score": scored.score,
        "Company": scored.company.name,
        "Analyzed": "Yes" if scored.crawled else "",
        "Org. number": scored.company.organization_number,
        "Website": _website(scored),
        "Email": _email(scored),
    }
    if include_crawl:
        row.update(crawl_columns(website_profile(scored)))
    if include_match:
        row.update(match_columns(scored.product_match))
    if include_outreach:
        row.update(outreach_columns(scored.outreach))
    row.update(
        {
            "SNI": ", ".join(scored.company.sni_codes),
            "Municipality": scored.company.municipality,
            "Employees": employee_display(scored.company.employee_class),
            "Revenue": scored.company.revenue_class,
            "Missing": ", ".join(scored.missing_data),
        }
    )
    return row


def match_columns(match: ProductMatch | None) -> dict[str, str]:
    if match is None:
        return {
            "Job": "",
            "Brand": "",
            "Primary": "",
            "Alternative": "",
            "Confidence": "",
            "Evidence": "",
        }
    return {
        "Job": match.job or "",
        "Brand": match.brand,
        "Primary": match.primary or "",
        "Alternative": match.alternative or "",
        "Confidence": match.confidence,
        "Evidence": "; ".join(match.evidence),
    }


def crawl_columns(profile: WebsiteProfile | None) -> dict[str, str]:
    if profile is None:
        return {"About": "", "Projects": ""}
    return {
        "About": profile.about_text or "",
        "Projects": profile.projects_text or "",
    }


def website_profile(scored: ScoredCompany) -> WebsiteProfile | None:
    if scored.website is not None:
        return scored.website
    if scored.outreach is not None and scored.outreach.website is not None:
        return scored.outreach.website
    return None


def outreach_columns(draft: OutreachDraft | None) -> dict[str, str]:
    if draft is None:
        return {"Outreach": "", "Fit": "", "Subject": "", "Email body": ""}
    return {
        "Outreach": draft.status,
        "Fit": draft.customer_fit,
        "Subject": draft.subject,
        "Email body": draft.body,
    }


def employee_display(value: str | None) -> str | None:
    if not value:
        return value
    compact = " ".join(part for part in value.split() if part.casefold() != "anställda")
    return compact or None


def score_explanation(scored: ScoredCompany) -> list[str]:
    if not scored.reasons:
        return ["No scoring signals matched."]
    lines: list[str] = []
    for reason in scored.reasons:
        points = f"+{reason.points}" if reason.points >= 0 else str(reason.points)
        lines.append(f"{reason.label} ({points})")
    return lines


def _website(scored: ScoredCompany) -> str:
    if scored.company.domain:
        return scored.company.domain
    profile = website_profile(scored)
    return "" if profile is None else profile.url


def _email(scored: ScoredCompany) -> str:
    if scored.outreach is not None and scored.outreach.suggested_recipient:
        return scored.outreach.suggested_recipient
    profile = website_profile(scored)
    if profile is None:
        return ""
    return profile.suggested_recipient or ""
