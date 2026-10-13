from __future__ import annotations

import streamlit as st

from lead_finder.config import get_settings
from lead_finder.ui.notices import push_notice, push_success, show_successes
from lead_finder.ui.result_grid import queue_grid_refresh
from lead_finder.use_company_search import SearchResult
from lead_finder.use_company_store import get_company_store
from lead_finder.use_lead_job import (
    clear_lead_job,
    get_lead_job,
    request_stop,
    start_lead_job,
)
from lead_finder.use_lead_queue import (
    companies_to_crawl,
    estimate_crawl_seconds,
    format_crawl_estimate,
    lead_success_message,
)


def continue_lead_queue(result: SearchResult, *, session_key: str) -> SearchResult:
    job = get_lead_job(session_key)
    if job is None:
        return result
    _watch_lead_job(session_key)
    snapshot = job.snapshot()
    current = snapshot["result"]
    if isinstance(current, SearchResult):
        return current
    return result


def start_lead_queue(
    result: SearchResult,
    org_numbers: list[str],
    *,
    session_key: str,
) -> None:
    if get_lead_job(session_key) is not None:
        return
    pending = companies_to_crawl(result, org_numbers)
    if not pending:
        push_notice(session_key, "Select companies to generate leads.")
        return
    st.session_state[f"{session_key}_lead_summary"] = ""
    st.session_state[f"{session_key}_pinned_orgs"] = list(pending)
    start_lead_job(session_key, result, pending, store=get_company_store())


def render_lead_queue_status(session_key: str) -> None:
    if get_lead_job(session_key) is not None:
        return
    summary = st.session_state.get(f"{session_key}_lead_summary")
    if summary:
        st.caption(summary)


@st.fragment(run_every=1)
def _watch_lead_job(session_key: str) -> None:
    job = get_lead_job(session_key)
    if job is None:
        return
    fresh = job.pull_notices()
    for message in fresh:
        st.toast(message, icon=":material/warning:", duration="long")
    snapshot = job.snapshot()
    if snapshot["phase"] == "running":
        _show_progress(session_key, job.stop.is_set(), snapshot)
        return
    _commit(session_key, snapshot)
    clear_lead_job(session_key)
    show_successes(session_key)
    queue_grid_refresh(session_key)


def _show_progress(session_key: str, stopping: bool, snapshot: dict[str, object]) -> None:
    done = int(snapshot["done"])
    total = max(int(snapshot["total"]), 1)
    left = max(int(snapshot["total"]) - done, 0)
    estimate = format_crawl_estimate(
        estimate_crawl_seconds(
            left,
            batch_size=_batch_size(),
            pause_seconds=0,
            concurrency=get_settings().website_crawl_concurrency,
        )
    )
    label = "Stopping crawl..." if stopping else str(snapshot["message"])
    st.progress(min(done / total, 1.0), text=f"{label} · {estimate} left")
    if st.button("Stop crawl", key=f"stop_crawl_{session_key}", disabled=stopping):
        request_stop(session_key)


def _commit(session_key: str, snapshot: dict[str, object]) -> None:
    result = snapshot["result"]
    if isinstance(result, SearchResult):
        st.session_state[session_key] = result
    summary = str(snapshot["summary"])
    st.session_state[f"{session_key}_lead_summary"] = summary
    records = snapshot["records"] if isinstance(snapshot["records"], list) else []
    message = lead_success_message(
        records,
        total=int(snapshot["total"]),
        summary=summary,
        error=str(snapshot["error"]),
    )
    if message:
        push_success(session_key, message)


def _batch_size() -> int:
    return get_settings().outreach_max_selected
