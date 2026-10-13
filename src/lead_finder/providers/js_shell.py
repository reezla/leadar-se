from __future__ import annotations

from bs4 import BeautifulSoup

_TEXT_LIMIT = 400
_LINK_LIMIT = 2
_MOUNTS = "#root, #app, #__next, #__nuxt"


def is_js_shell(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    if not _boots_in_browser(soup):
        return False
    if len(soup.find_all("a", href=True)) > _LINK_LIMIT:
        return False
    return _visible_length(soup) < _TEXT_LIMIT


def _boots_in_browser(soup: BeautifulSoup) -> bool:
    if soup.select_one(_MOUNTS) is not None:
        return True
    for tag in soup.find_all("script"):
        kind = str(tag.get("type") or "").lower()
        if kind == "module" and tag.get("src"):
            return True
    return False


def _visible_length(soup: BeautifulSoup) -> int:
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return len(" ".join(soup.get_text(" ", strip=True).split()))
