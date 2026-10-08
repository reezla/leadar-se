from __future__ import annotations

import json

import streamlit as st

_COPY_ICON = (
    '<svg class="copy" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 '
    "1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z\"/>"
    "</svg>"
)
_CHECK_ICON = (
    '<svg class="done" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>'
)


def render_copy_email(text: str, *, key: str) -> None:
    element_id = _element_id(key)
    payload = json.dumps(text).replace("<", "\\u003c")
    st.html(
        f"""
        <button id="{element_id}" type="button" title="Copy email" aria-label="Copy email">
          {_COPY_ICON}{_CHECK_ICON}
        </button>
        <style>
          #{element_id} {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.75rem;
            height: 1.75rem;
            padding: 0;
            border: none;
            border-radius: 0.4rem;
            background: transparent;
            color: rgba(49, 51, 63, 0.55);
            cursor: pointer;
          }}
          #{element_id}:hover {{
            color: rgb(49, 51, 63);
            background: rgba(49, 51, 63, 0.08);
          }}
          #{element_id} svg {{ width: 1.15rem; height: 1.15rem; fill: currentColor; }}
          #{element_id} .done {{ display: none; }}
          #{element_id}[data-copied="1"] {{ color: #2e7d32; }}
          #{element_id}[data-copied="1"] .copy {{ display: none; }}
          #{element_id}[data-copied="1"] .done {{ display: block; }}
        </style>
        <script>
          const button = document.getElementById({json.dumps(element_id)});
          if (button && button.dataset.bound !== "1") {{
            button.dataset.bound = "1";
            button.addEventListener("mousedown", async (event) => {{
              event.preventDefault();
              const area = document.querySelector('textarea[aria-label="Body"]');
              const text = area ? area.value : {payload};
              try {{
                await navigator.clipboard.writeText(text);
              }} catch (error) {{
                const field = document.createElement("textarea");
                field.value = text;
                document.body.appendChild(field);
                field.select();
                document.execCommand("copy");
                field.remove();
              }}
              button.dataset.copied = "1";
              window.setTimeout(() => {{ button.dataset.copied = ""; }}, 1200);
            }});
          }}
        </script>
        """,
        unsafe_allow_javascript=True,
        width="content",
    )


def _element_id(key: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in key)
    return f"copy_email_{cleaned}"
