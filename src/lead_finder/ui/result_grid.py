from __future__ import annotations

import streamlit as st

from lead_finder.ui.result_rows import (
    result_columns,
    result_row,
    score_explanation,
    website_profile,
)
from lead_finder.ui.result_table import render_result_table
from lead_finder.ui.selection_follow import render_selection_follow
from lead_finder.use_company_search import SearchResult
from lead_finder.use_result_selection import selection_needs_app_rerun
from lead_finder.use_table_page import displayed_bounds

_GRID_KEY = "results_grid"
_REFRESH_KEY = "refresh_rows"
_SCRIPT = """\
<script>
(function () {
  var token = "__TOKEN__";
  var slot = window.__leadGridRefresh || (window.__leadGridRefresh = {});
  if (slot[token]) {
    return;
  }
  slot[token] = true;
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    var button = document.querySelector('[class*="st-key-refresh_rows"] button');
    if (button) {
      clearInterval(timer);
      button.click();
      return;
    }
    if (tries > 20) {
      clearInterval(timer);
    }
  }, 50);
})();
</script>
"""


def render_result_grid(session_key: str, widget_key: str) -> list[int]:
    st.button(
        "Refresh rows",
        key=_REFRESH_KEY,
        on_click=_refresh_grid,
    )
    return _grid(session_key, widget_key)


def queue_grid_refresh(session_key: str) -> None:
    counter_key = f"{session_key}_grid_refresh"
    token = int(st.session_state.get(counter_key, 0) or 0) + 1
    st.session_state[counter_key] = token
    if st.session_state.get(f"{session_key}_pinned_orgs"):
        st.session_state[f"{session_key}_follow_selection"] = True
    st.html(_SCRIPT.replace("__TOKEN__", str(token)), unsafe_allow_javascript=True)


def _refresh_grid() -> None:
    st.rerun(_GRID_KEY)


@st.fragment(key=_GRID_KEY)
def _grid(session_key: str, widget_key: str) -> list[int]:
    stored = st.session_state.get(session_key)
    if not isinstance(stored, SearchResult):
        return []
    rows, available, explanations = _table_model(stored)
    start, end = displayed_bounds(st.session_state, session_key, len(rows))
    selected = render_result_table(
        rows[start:end],
        available=available,
        widget_key=widget_key,
        explanations=explanations[start:end],
    )
    selected = [start + index for index in selected]
    if st.session_state.get(f"{session_key}_follow_selection"):
        render_selection_follow(session_key)
    else:
        _publish_selection(session_key, selected)
    return selected


def _publish_selection(session_key: str, selected: list[int]) -> None:
    key = f"{session_key}_published_selection"
    current = list(selected)
    previous = st.session_state.get(key)
    st.session_state[key] = current
    if not selection_needs_app_rerun(previous, current, in_fragment=_in_fragment()):
        return
    st.rerun(scope="app")


def _in_fragment() -> bool:
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    context = get_script_run_ctx()
    return bool(context and context.fragment_ids_this_run)


def _table_model(
    result: SearchResult,
) -> tuple[list[dict[str, object]], list[str], list[list[str]]]:
    include_match = any(item.product_match is not None for item in result.companies)
    include_crawl = any(item.crawl_status is not None for item in result.companies) or any(
        website_profile(item) is not None for item in result.companies
    )
    rows = [
        result_row(
            item,
            include_match=include_match,
            include_crawl=include_crawl,
            include_outreach=False,
        )
        for item in result.companies
    ]
    columns = result_columns(
        include_match=include_match,
        include_crawl=include_crawl,
        include_outreach=False,
    )
    explanations = [score_explanation(item) for item in result.companies]
    return rows, columns, explanations
