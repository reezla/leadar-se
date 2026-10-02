from __future__ import annotations

import streamlit as st

from lead_finder.models import OutreachDraft, ProductMatch, ScoredCompany
from lead_finder.ui.column_hide import render_column_hide_controls
from lead_finder.ui.score_popup import open_score_popup_if_clicked


def result_columns(*, include_match: bool, include_outreach: bool = False) -> list[str]:
    leading = ["Score", "Company", "Org. number", "Website", "Email"]
    match = ["Job", "Brand", "Primary", "Alternative", "Confidence", "Evidence"]
    outreach = ["Outreach", "Fit", "Subject", "Email body"]
    trailing = ["SNI", "Municipality", "Employees", "Revenue", "Missing"]
    columns = leading
    if include_match:
        columns = [*columns, *match]
    if include_outreach:
        columns = [*columns, *outreach]
    return [*columns, *trailing]


def result_row(
    scored: ScoredCompany,
    *,
    include_match: bool,
    include_outreach: bool = False,
) -> dict[str, object]:
    row: dict[str, object] = {
        "Score": scored.score,
        "Company": scored.company.name,
        "Org. number": scored.company.organization_number,
        "Website": _website(scored),
        "Email": _email(scored),
    }
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


def result_column_config(rows: list[dict[str, object]]) -> dict[str, object]:
    compact = st.column_config.Column()
    names = [str(row.get("Company") or "") for row in rows]
    longest = max([len("Company"), *(len(name) for name in names)], default=len("Company"))
    return {
        "Score": st.column_config.NumberColumn(
            format="%d",
            width="small",
            help="Click a score to see why that company was scored.",
        ),
        "Company": st.column_config.TextColumn(width=max(int((longest * 8 + 36) * 0.6), 96)),
        "Website": st.column_config.TextColumn("Website"),
        "Email": st.column_config.TextColumn("Email"),
        "Email body": st.column_config.TextColumn("Email body"),
        "Org. number": compact,
        "SNI": compact,
        "Municipality": compact,
        "Employees": compact,
        "Revenue": compact,
        "Brand": compact,
        "Primary": compact,
        "Alternative": compact,
        "Confidence": compact,
        "Job": compact,
        "Evidence": compact,
        "Outreach": compact,
        "Fit": st.column_config.TextColumn(
            "Fit",
            help="Website-based estimate: weak, moderate, or strong potential customer.",
            width="small",
        ),
        "Subject": compact,
        "Missing": compact,
    }


def _website(scored: ScoredCompany) -> str:
    if scored.company.domain:
        return scored.company.domain
    if scored.outreach is not None and scored.outreach.website is not None:
        return scored.outreach.website.url
    return ""


def _email(scored: ScoredCompany) -> str:
    if scored.outreach is None:
        return ""
    return scored.outreach.suggested_recipient or ""


def render_result_table(
    rows: list[dict[str, object]],
    *,
    available: list[str],
    order: list[str],
    widget_key: str,
    state_key: str,
    explanations: list[list[str]] | None = None,
) -> list[int]:
    render_column_hide_controls(available, order, state_key=state_key)
    event = st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_order=order or available,
        column_config=result_column_config(rows),
        on_select="rerun",
        selection_mode=["multi-row", "single-cell"],
        key=widget_key,
        row_height=36,
    )
    open_score_popup_if_clicked(
        event,
        rows,
        explanations or [[] for _ in rows],
        widget_key=widget_key,
    )
    return list(event.selection.rows)
