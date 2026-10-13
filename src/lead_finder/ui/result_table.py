from __future__ import annotations

import pandas as pd
import streamlit as st

from lead_finder.ui.copy_field import website_href
from lead_finder.ui.score_popup import open_score_popup_if_clicked
from lead_finder.use_result_selection import analyzed_cell_styles


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
        "Analyzed": st.column_config.TextColumn("Analyzed", width="small"),
        "Website": st.column_config.LinkColumn("Website"),
        "Email": st.column_config.TextColumn("Email"),
        "About": st.column_config.TextColumn("About"),
        "Projects": st.column_config.TextColumn("Projects"),
        "Email body": st.column_config.TextColumn("Email body"),
        "Org. number": compact,
        "SNI": compact,
        "Municipality": compact,
        "Employees": compact,
        "Revenue": compact,
        "Brand": compact,
        "Primary": st.column_config.TextColumn(
            "Scanner",
            help="Norrpoint scanner recommended from the company's website.",
            width="small",
        ),
        "Alternative": st.column_config.TextColumn("Alternatives", width="small"),
        "Confidence": compact,
        "Job": st.column_config.TextColumn(
            "Buyer",
            help="Whether they measure themselves, order measuring, or are not relevant.",
            width="small",
        ),
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


def render_result_table(
    rows: list[dict[str, object]],
    *,
    available: list[str],
    widget_key: str,
    explanations: list[list[str]] | None = None,
) -> list[int]:
    event = st.dataframe(
        _styled_rows(_website_links(rows)),
        hide_index=True,
        width="stretch",
        column_order=available,
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


def _website_links(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    linked: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        item["Website"] = website_href(str(item.get("Website") or ""))
        linked.append(item)
    return linked


def _styled_rows(rows: list[dict[str, object]]) -> pd.DataFrame | pd.io.formats.style.Styler:
    frame = pd.DataFrame(rows)
    if frame.empty or "Analyzed" not in frame.columns:
        return frame
    analyzed_index = list(frame.columns).index("Analyzed")
    return frame.style.apply(
        lambda row: analyzed_cell_styles(list(row), analyzed_index=analyzed_index),
        axis=1,
    )
