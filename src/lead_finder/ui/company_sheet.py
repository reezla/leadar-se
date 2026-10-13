from __future__ import annotations

import streamlit as st

from lead_finder.models import Company, ScoredCompany
from lead_finder.ui.copy_field import render_readonly_field, render_readonly_pair
from lead_finder.ui.result_rows import employee_display, score_explanation
from lead_finder.use_analyzed_companies import crawl_label, has_email


def render_company_sheet(
    scored: ScoredCompany,
    *,
    session_key: str,
    alternatives: list[ScoredCompany] | None = None,
) -> None:
    company = scored.company
    with st.container(border=True):
        title_column, hide_column = st.columns([8, 1])
        title_column.subheader(company.name)
        title_column.caption(_identity(company))
        if hide_column.button("Hide", key=f"hide_sheet_{session_key}"):
            st.session_state.pop(f"{session_key}_display_org", None)
            st.rerun()
        _pick_company(alternatives or [], company.organization_number, session_key)
        _facts(scored)
        org = company.organization_number
        about_column, projects_column = st.columns(2)
        about = (scored.website.about_text if scored.website else None) or ""
        projects = (scored.website.projects_text if scored.website else None) or ""
        with about_column:
            render_readonly_field(
                "About",
                about or "Not set",
                key=f"sheet_about_{org}",
                multiline=True,
            )
        with projects_column:
            render_readonly_field(
                "Projects",
                projects or "Not set",
                key=f"sheet_projects_{org}",
                multiline=True,
            )
        pages = [] if scored.website is None else scored.website.pages_fetched
        if pages:
            with st.expander(f"Pages read ({len(pages)})"):
                for index, page in enumerate(pages):
                    render_readonly_field(
                        f"Page {index + 1}",
                        page,
                        key=f"sheet_page_{org}_{index}",
                        link=True,
                    )
        reasons = score_explanation(scored)
        if reasons:
            with st.expander("Why this score"):
                render_readonly_field(
                    "Score reasons",
                    "\n".join(reasons),
                    key=f"sheet_reasons_{org}",
                    multiline=True,
                    height=min(max(len(reasons) * 28, 88), 200),
                )


def _pick_company(alternatives: list[ScoredCompany], current_org: str, session_key: str) -> None:
    if len(alternatives) < 2:
        return
    labels = {item.company.organization_number: item.company.name for item in alternatives}
    if current_org not in labels:
        return
    orgs = list(labels)
    key = f"sheet_pick_{session_key}"
    if st.session_state.get(key) not in orgs:
        st.session_state[key] = current_org
    picked = st.selectbox(
        "Showing",
        orgs,
        format_func=lambda org: labels[org],
        key=key,
        help="Switch between the selected companies.",
    )
    if picked != current_org:
        st.session_state[f"{session_key}_display_org"] = picked
        st.rerun()


def _facts(scored: ScoredCompany) -> None:
    company = scored.company
    _inject_stat_styles()
    score_column, crawl_column, people_column, revenue_column = st.columns(4)
    score_column.markdown(_stat_block("Score", str(scored.score)), unsafe_allow_html=True)
    crawl_column.markdown(
        _stat_block("Crawl", crawl_label(scored.crawl_status)),
        unsafe_allow_html=True,
    )
    people_column.markdown(
        _stat_block("Employees", employee_display(company.employee_class) or "Not set"),
        unsafe_allow_html=True,
    )
    revenue_column.markdown(
        _stat_block("Revenue", company.revenue_class or "Not set"),
        unsafe_allow_html=True,
    )
    website = company.domain or ("" if scored.website is None else scored.website.url)
    email = "" if scored.website is None else (scored.website.suggested_recipient or "")
    org = company.organization_number
    render_readonly_pair(
        ("Website", website or "Not set", f"sheet_site_{org}"),
        ("Email", email or "Not set", f"sheet_mail_{org}"),
        left_link=True,
    )
    if scored.crawl_status not in {None, "crawled"} and scored.crawl_detail:
        render_readonly_field(
            "Crawl detail",
            scored.crawl_detail,
            key=f"sheet_crawl_detail_{company.organization_number}",
            multiline=True,
            height=88,
        )
    elif not has_email(scored):
        st.caption("No email stored for this company.")


def _identity(company: Company) -> str:
    place = ", ".join(part for part in (company.municipality, company.county) if part)
    sni = ", ".join(company.sni_codes) or "Not set"
    where = place or "Place not set"
    return f"Org. number {company.organization_number} · {where} · SNI {sni}"


def _stat_block(label: str, value: str) -> str:
    safe_label = _html(label)
    safe_value = _html(value)
    return (
        f'<div class="sheet-stat"><div class="sheet-stat-label">{safe_label}</div>'
        f'<div class="sheet-stat-value">{safe_value}</div></div>'
    )


def _inject_stat_styles() -> None:
    if st.session_state.get("_sheet_stat_styles"):
        return
    st.session_state["_sheet_stat_styles"] = True
    st.markdown(
        """
        <style>
        .sheet-stat { margin-bottom: 0.35rem; }
        .sheet-stat-label {
          font-size: 1rem;
          font-weight: 600;
          color: rgb(49, 51, 63);
          line-height: 1.3;
        }
        .sheet-stat-value {
          font-size: 0.82rem;
          font-weight: 400;
          color: rgb(49, 51, 63);
          line-height: 1.35;
          margin-top: 0.15rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
