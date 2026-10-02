from __future__ import annotations

from html import escape

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.use_company_search import SearchResult
from lead_finder.use_outreach_rewrite import rewrite_outreach

_FIT_COLORS = {
    "weak": "#c62828",
    "moderate": "#ef6c00",
    "strong": "#2e7d32",
}


def focus_outreach_preview(
    result: SearchResult,
    org_numbers: list[str],
    *,
    widget_key: str,
) -> None:
    wanted = set(org_numbers)
    for scored in result.companies:
        if scored.company.organization_number not in wanted:
            continue
        if scored.outreach is None:
            continue
        st.session_state[f"outreach_preview_{widget_key}"] = scored.company.name
        return


def render_outreach_preview(
    result: SearchResult,
    *,
    session_key: str,
    widget_key: str,
    sender: str | None,
) -> SearchResult:
    processed = [scored for scored in result.companies if scored.outreach is not None]
    if not processed:
        return result
    names = [scored.company.name for scored in processed]
    choice = st.selectbox("Outreach preview", names, key=f"outreach_preview_{widget_key}")
    scored = next(item for item in processed if item.company.name == choice)
    draft = scored.outreach
    if draft is None:
        return result
    website = scored.company.domain or (draft.website.url if draft.website else "")
    if website:
        st.caption(f"Website: {website}")
    _render_market_fit(draft.customer_fit, draft.customer_fit_reason)
    if draft.suggested_recipient:
        st.caption(f"Suggested recipient: {draft.suggested_recipient}")
    if draft.status == "no_website":
        st.warning(draft.detail or "No official website found.")
        return result
    if draft.detail and draft.detail != "template":
        st.caption(draft.detail)
    nonce = st.session_state.get(f"{session_key}_nonce", 0)
    org = scored.company.organization_number
    subject = st.text_input(
        "Subject",
        draft.subject,
        key=f"outreach_subject_{widget_key}_{nonce}_{org}",
    )
    body = st.text_area(
        "Body",
        draft.body,
        height=220,
        key=f"outreach_body_{widget_key}_{nonce}_{org}",
    )
    can_rewrite = bool(sender) and draft.website is not None and bool(draft.website.url)
    if st.button(
        "Rewrite email",
        disabled=not can_rewrite,
        key=f"outreach_rewrite_{widget_key}_{org}",
    ):
        result = rewrite_outreach(result, org, sender=sender or "norrpoint")
        st.session_state[session_key] = result
        nonce_key = f"{session_key}_nonce"
        st.session_state[nonce_key] = int(st.session_state.get(nonce_key) or 0) + 1
        st.rerun()
    return _apply_edits(result, org, subject, body, session_key=session_key)


def _render_market_fit(fit: str, reason: str) -> None:
    if not fit:
        return
    caption = "rgba(49, 51, 63, 0.6)"
    color = _FIT_COLORS.get(fit, caption)
    sentence = _reason_sentence(reason)
    reason_html = f" {escape(sentence)}" if sentence else ""
    st.markdown(
        (
            f'<p style="margin:0.15rem 0 0.35rem 0;font-size:0.875rem;'
            f'line-height:1.4;color:{caption}">'
            f'Market fit: <span style="color:{color};font-weight:600">{escape(fit)}</span>'
            f"{reason_html}"
            "</p>"
        ),
        unsafe_allow_html=True,
    )


def _reason_sentence(reason: str) -> str:
    text = " ".join(reason.split())
    if not text:
        return ""
    if text[-1] not in ".!?":
        return f"{text}."
    return text


def _apply_edits(
    result: SearchResult,
    organization_number: str,
    subject: str,
    body: str,
    *,
    session_key: str,
) -> SearchResult:
    updated: list[ScoredCompany] = []
    changed = False
    for scored in result.companies:
        draft = scored.outreach
        if (
            scored.company.organization_number != organization_number
            or draft is None
            or (draft.subject == subject and draft.body == body)
        ):
            updated.append(scored)
            continue
        changed = True
        updated.append(
            scored.model_copy(
                update={
                    "outreach": draft.model_copy(
                        update={"subject": subject, "body": body}
                    )
                }
            )
        )
    if not changed:
        return result
    next_result = SearchResult(companies=updated, summary=result.summary)
    st.session_state[session_key] = next_result
    return next_result
