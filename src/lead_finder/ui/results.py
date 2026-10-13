from __future__ import annotations

import streamlit as st

from lead_finder.models import ScoredCompany
from lead_finder.ui.company_sheet import render_company_sheet
from lead_finder.ui.delete_companies import render_delete_button, render_delete_dialog
from lead_finder.ui.export_bar import render_export_bar
from lead_finder.ui.outreach_bar import render_outreach_bar
from lead_finder.ui.result_grid import render_result_grid
from lead_finder.ui.result_rows import result_columns, result_row
from lead_finder.ui.result_select import render_select_more
from lead_finder.ui.table_pager import render_table_pager
from lead_finder.ui.table_sort_bridge import (
    render_table_order_field,
    render_table_order_script,
)
from lead_finder.use_company_search import SearchResult
from lead_finder.use_result_selection import results_editor_key
from lead_finder.use_table_page import remember_table_page

_columns = result_columns
_row = result_row


def render_results(
    result: SearchResult,
    *,
    download_name: str,
    session_key: str,
    show_save: bool = True,
    show_display: bool = False,
    show_fetched: bool = True,
    catalog_key: str | None = None,
    page_size: int | None = None,
) -> None:
    _summary(result, show_fetched=show_fetched)
    nonce = int(st.session_state.get(f"{session_key}_nonce", 0) or 0)
    page, pages, start, end = remember_table_page(
        st.session_state,
        session_key,
        len(result.companies),
        size=page_size,
    )
    shown = result.companies[start:end]
    widget_key = results_editor_key(session_key, nonce, page)
    visual_order = render_table_order_field(session_key, len(shown))
    render_select_more(
        [scored.crawled for scored in shown],
        widget_key=widget_key,
        session_key=session_key,
        visual_order=visual_order,
    )
    selected = render_result_grid(session_key, widget_key)
    render_table_pager(
        session_key,
        page=page,
        pages=pages,
        start=start,
        end=end,
        total=len(result.companies),
    )
    render_table_order_script(widget_key, session_key, len(shown))
    chosen = _selected_companies(result.companies, selected)
    result = _render_table_actions(
        result,
        selected,
        chosen,
        session_key=session_key,
        download_name=download_name,
        show_save=show_save,
        show_display=show_display,
        catalog_key=catalog_key,
    )
    if show_display:
        _display_sheet(result, chosen, session_key=session_key)


def _summary(result: SearchResult, *, show_fetched: bool) -> SearchResult:
    if not show_fetched:
        return result
    summary = result.summary
    crawled = sum(scored.crawl_status is not None for scored in result.companies)
    drafted = sum(scored.outreach is not None for scored in result.companies)
    st.metric("Fetched", summary.fetched)
    if crawled:
        st.caption(f"Website data gathered for {crawled} companies.")
    if drafted:
        st.caption(f"Outreach drafted for {drafted} companies. Review them on Write emails.")
    return result


def _render_table_actions(
    result: SearchResult,
    selected: list[int],
    chosen: list[ScoredCompany],
    *,
    session_key: str,
    download_name: str,
    show_save: bool,
    show_display: bool,
    catalog_key: str | None,
) -> SearchResult:
    with st.container(
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
        gap="small",
        wrap=False,
    ):
        actions = st.container(
            horizontal=True,
            width="content",
            gap="small",
            vertical_alignment="center",
        )
        exports = st.container(
            horizontal=True,
            width="content",
            gap="small",
            vertical_alignment="center",
        )
    with actions:
        if show_display and st.button(
            "Display it",
            disabled=not chosen,
            key=f"display_it_{session_key}",
            help="Show the selected company under the table.",
        ):
            org = chosen[0].company.organization_number
            st.session_state[f"{session_key}_display_org"] = org
            st.session_state[f"sheet_pick_{session_key}"] = org
            st.rerun()
    result = render_outreach_bar(
        result,
        selected,
        session_key=session_key,
        widget_key=download_name,
        button_slots=(actions, actions, actions if show_save else None, actions),
    )
    with exports:
        render_export_bar(
            result.companies,
            selected=chosen,
            download_name=download_name,
        )
        if catalog_key is not None:
            render_delete_button(chosen, session_key=session_key)
    if catalog_key is not None:
        render_delete_dialog(session_key=session_key, catalog_key=catalog_key)
    return result


def _display_sheet(
    result: SearchResult,
    chosen: list[ScoredCompany],
    *,
    session_key: str,
) -> None:
    org = st.session_state.get(f"{session_key}_display_org")
    if not isinstance(org, str) or not org:
        return
    shown = next(
        (item for item in result.companies if item.company.organization_number == org),
        None,
    )
    if shown is None:
        return
    render_company_sheet(shown, session_key=session_key, alternatives=chosen)


def _selected_companies(companies: list[ScoredCompany], indices: list[int]) -> list[ScoredCompany]:
    return [companies[index] for index in indices if 0 <= index < len(companies)]
