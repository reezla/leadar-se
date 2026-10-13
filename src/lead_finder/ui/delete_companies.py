from __future__ import annotations

import html
import logging

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.ui.notices import push_success
from lead_finder.use_analyzed_delete import delete_targets, forget_deleted_companies
from lead_finder.use_company_store import get_company_store
from lead_finder.use_lead_job import get_lead_job

logger = logging.getLogger(__name__)

_PENDING = "analyzed_delete_pending"


def render_delete_button(chosen: list[ScoredCompany], *, session_key: str) -> None:
    running = get_lead_job(session_key) is not None
    if st.button(
        "Delete",
        icon=":material/delete:",
        disabled=not chosen or running,
        key=f"delete_rows_{session_key}",
        help="Delete the selected companies. Unavailable while a crawl is running.",
    ):
        st.session_state[_PENDING] = delete_targets(chosen)


def render_delete_dialog(*, session_key: str, catalog_key: str) -> None:
    pending = st.session_state.get(_PENDING)
    if isinstance(pending, list) and pending:
        _confirm_delete(pending, session_key=session_key, catalog_key=catalog_key)


def company_list_html(labels: list[str]) -> str:
    items = "".join(f"<li>{html.escape(label)}</li>" for label in labels)
    return (
        '<div style="max-height:10rem;overflow-y:auto;margin:0.25rem 0 0.75rem">'
        f'<ul style="margin:0;padding-left:1.25rem">{items}</ul>'
        "</div>"
    )


def _clear_pending() -> None:
    st.session_state.pop(_PENDING, None)


@st.dialog("Delete companies", icon=":material/delete:", on_dismiss=_clear_pending)
def _confirm_delete(
    pending: list[dict[str, str]],
    *,
    session_key: str,
    catalog_key: str,
) -> None:
    count = len(pending)
    noun = "company" if count == 1 else "companies"
    st.write(f"Delete {count} {noun} from analyzed data?")
    st.html(company_list_html([str(item.get("label") or "") for item in pending]))
    cancel_column, confirm_column = st.columns(2)
    if cancel_column.button("Cancel", key="analyzed_delete_cancel", width="stretch"):
        _clear_pending()
        st.rerun()
    if confirm_column.button(
        "Delete",
        type="primary",
        icon=":material/delete:",
        key="analyzed_delete_confirm",
        width="stretch",
    ):
        error = _delete_selected(pending, session_key=session_key, catalog_key=catalog_key)
        if error:
            st.error(error)
            return
        _clear_pending()
        push_success(session_key, f"Deleted {count} {noun}.")
        st.rerun()


def _delete_selected(
    pending: list[dict[str, str]],
    *,
    session_key: str,
    catalog_key: str,
) -> str:
    store = get_company_store()
    if store is None:
        return "Supabase is not configured, so nothing was deleted."
    orgs = [str(item.get("organization_number") or "") for item in pending]
    outcome = store.delete_companies(orgs)
    if outcome.error:
        logger.warning("Could not delete companies: %s", outcome.error)
        return "Deleting from the database failed."
    forget_deleted_companies(
        st.session_state,
        session_key=session_key,
        catalog_key=catalog_key,
        organization_numbers=set(orgs),
    )
    return ""
