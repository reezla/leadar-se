from __future__ import annotations

import json

_FIT = {"weak", "moderate", "strong"}
_FIT_ALIASES = {"low": "weak", "medium": "moderate", "high": "strong"}


def parse_openai_content(content: str) -> tuple[str, str, str, str]:
    text = content.strip()
    if text.startswith("{"):
        subject, body, fit, reason = _from_json(text)
        if subject and body:
            return subject, body, fit, reason
    if not text:
        raise ValueError("OpenAI returned an empty draft")
    return _subject_line(text), text, "", ""


def normalize_customer_fit(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in _FIT:
        return text
    return _FIT_ALIASES.get(text, "")


def _from_json(text: str) -> tuple[str, str, str, str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return "", "", "", ""
    if not isinstance(payload, dict):
        return "", "", "", ""
    return (
        str(payload.get("subject") or "").strip(),
        str(payload.get("body") or "").strip(),
        normalize_customer_fit(payload.get("customer_fit")),
        _reason(payload.get("customer_fit_reason")),
    )


def _reason(value: object) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= 280:
        return text
    return text[:280].rsplit(" ", 1)[0] + "…"


def _subject_line(body: str) -> str:
    for line in body.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.casefold().startswith("hej"):
            continue
        words = cleaned.split()
        return " ".join(words[:4]).casefold().rstrip(".,")
    return "norrpoint"
