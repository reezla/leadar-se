from __future__ import annotations

import html
import json

import streamlit as st

_STYLES = """
<style>
.sheet-pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  column-gap: 1rem;
  align-items: stretch;
  margin-top: 1.25rem;
}
.sheet-line { margin: 0 0 0.75rem; }
.sheet-line-label {
  margin: 0 0 0.25rem;
  color: rgb(49, 51, 63);
  font-size: 14px;
  line-height: 1.4;
  min-height: 1.4em;
}
.sheet-line-box {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  box-sizing: border-box;
  min-height: 2.5rem;
  padding: 0.35rem 0.35rem 0.35rem 0.75rem;
  border-radius: 0.5rem;
  background: #f0f2f6;
}
.sheet-line-box.multiline { align-items: flex-start; overflow: auto; }
.sheet-line-value {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  padding: 0;
  user-select: text;
  -webkit-user-select: text;
  color: rgb(49, 51, 63);
  font-size: 16px;
  font-weight: 400;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
}
a.sheet-line-value {
  color: #1d4ed8;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
button.sheet-copy-btn {
  all: unset;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 1.75rem;
  width: 1.75rem;
  min-width: 1.75rem;
  height: 1.75rem;
  border-radius: 0.35rem;
  cursor: pointer;
}
button.sheet-copy-btn:hover { background: rgba(49, 51, 63, 0.08); }
.sheet-copy-glyph {
  position: relative;
  display: block;
  width: 14px;
  height: 14px;
}
.sheet-copy-glyph::before,
.sheet-copy-glyph::after {
  content: "";
  position: absolute;
  width: 9px;
  height: 9px;
  box-sizing: border-box;
  border: 1.5px solid #31333f;
  border-radius: 1.5px;
  background: #f0f2f6;
}
.sheet-copy-glyph::before { top: 0; right: 0; }
.sheet-copy-glyph::after { left: 0; bottom: 0; }
.sheet-copy-check { display: none; color: #2e7d32; font-size: 16px; line-height: 1; }
button.sheet-copy-btn[data-copied="1"] .sheet-copy-glyph { display: none; }
button.sheet-copy-btn[data-copied="1"] .sheet-copy-check { display: block; }
</style>
"""


def render_readonly_field(
    label: str,
    text: str,
    *,
    key: str,
    multiline: bool = False,
    height: int = 220,
    link: bool = False,
) -> None:
    _render([_field(label, text, key=key, multiline=multiline, height=height, link=link)])


def render_readonly_pair(
    left: tuple[str, str, str],
    right: tuple[str, str, str],
    *,
    left_link: bool = False,
    right_link: bool = False,
) -> None:
    left_label, left_text, left_key = left
    right_label, right_text, right_key = right
    _render(
        [
            _field(left_label, left_text, key=left_key, link=left_link),
            _field(right_label, right_text, key=right_key, link=right_link),
        ]
    )


def _render(fields: list[str]) -> None:
    body = "".join(fields)
    if len(fields) > 1:
        body = f'<div class="sheet-pair">{body}</div>'
    st.html(_STYLES + body, unsafe_allow_javascript=True)


def _field(
    label: str,
    text: str,
    *,
    key: str,
    multiline: bool = False,
    height: int = 220,
    link: bool = False,
) -> str:
    element_id = _element_id(key)
    payload = json.dumps(text).replace("<", "\\u003c")
    box_class = "sheet-line-box multiline" if multiline else "sheet-line-box"
    max_height = f' style="max-height:{height}px"' if multiline else ""
    return f"""
        <div class="sheet-line">
          <div class="sheet-line-label">{html.escape(label)}</div>
          <div class="{box_class}"{max_height}>
            {_value(text, link=link)}
            <button id="{element_id}" type="button" class="sheet-copy-btn" title="Copy"
              aria-label="Copy {html.escape(label)}">
              <span class="sheet-copy-glyph"></span>
              <span class="sheet-copy-check">✓</span>
            </button>
          </div>
        </div>
        <script>
          (() => {{
            const button = document.getElementById({json.dumps(element_id)});
            if (!button || button.dataset.bound === "1") return;
            button.dataset.bound = "1";
            button.addEventListener("click", async (event) => {{
              event.preventDefault();
              event.stopPropagation();
              const value = {payload};
              try {{
                await navigator.clipboard.writeText(value);
              }} catch (error) {{
                const field = document.createElement("textarea");
                field.value = value;
                document.body.appendChild(field);
                field.select();
                document.execCommand("copy");
                field.remove();
              }}
              button.dataset.copied = "1";
              window.setTimeout(() => {{ button.dataset.copied = ""; }}, 1200);
            }});
          }})();
        </script>
    """


def _value(text: str, *, link: bool) -> str:
    shown = html.escape(text)
    href = website_href(text) if link else None
    if href is None:
        return f'<span class="sheet-line-value">{shown}</span>'
    safe_href = html.escape(href, quote=True)
    return (
        f'<a class="sheet-line-value" href="{safe_href}" target="_blank" '
        f'rel="noopener noreferrer">{shown}</a>'
    )


def website_href(text: str) -> str | None:
    raw = text.strip()
    if not raw or raw.casefold() == "not set":
        return None
    if raw.startswith(("http://", "https://")):
        return raw
    if " " in raw or "." not in raw:
        return None
    return f"https://{raw}"


def _element_id(key: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in key)
    return f"copy_field_{cleaned}"
