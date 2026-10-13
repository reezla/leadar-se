from __future__ import annotations

from typing import Protocol

import httpx

from lead_finder.config import Settings
from lead_finder.providers.google_search_parse import first_usable_website

BATCH_LIMIT = 100


class SerperSearchError(Exception):
    """Serper did not return a website list."""


class SerperClient(Protocol):
    def post(self, url: str, *, json: object, headers: dict[str, str]) -> httpx.Response:
        """Send one mini-batch."""
        ...


def find_websites(
    names: list[str],
    *,
    settings: Settings,
    client: SerperClient | None = None,
) -> list[str | None]:
    if not settings.serper_api_key:
        raise SerperSearchError("Set SERPER_API_KEY to find websites with Serper.")
    owned = httpx.Client(timeout=settings.serper_timeout_seconds) if client is None else None
    active = owned if owned is not None else client
    try:
        found: list[str | None] = []
        for start in range(0, len(names), BATCH_LIMIT):
            chunk = names[start : start + BATCH_LIMIT]
            found.extend(_batch(chunk, settings=settings, client=active))
        return found
    finally:
        if owned is not None:
            owned.close()


def _batch(
    names: list[str],
    *,
    settings: Settings,
    client: SerperClient,
) -> list[str | None]:
    response = client.post(
        settings.serper_search_url,
        json=[{"q": name, "gl": "se", "hl": "sv", "num": 10} for name in names],
        headers={
            "X-API-KEY": settings.serper_api_key or "",
            "Content-Type": "application/json",
        },
    )
    if response.status_code != 200:
        detail = _error_text(response)
        raise SerperSearchError(detail or f"Serper returned HTTP {response.status_code}.")
    payload = response.json()
    if not isinstance(payload, list) or len(payload) != len(names):
        raise SerperSearchError("Serper returned an unexpected result.")
    return [_website(item) for item in payload]


def _website(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    links: list[str] = []
    graph = item.get("knowledgeGraph")
    if isinstance(graph, dict) and isinstance(graph.get("website"), str):
        links.append(graph["website"])
    organic = item.get("organic")
    if isinstance(organic, list):
        for row in organic:
            link = row.get("link") if isinstance(row, dict) else None
            if isinstance(link, str):
                links.append(link)
    return first_usable_website(links)


def _error_text(response: object) -> str:
    try:
        payload = response.json()
    except Exception:
        return ""
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        return payload["message"]
    return ""
