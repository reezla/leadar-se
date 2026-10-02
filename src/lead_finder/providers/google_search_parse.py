from __future__ import annotations

from collections.abc import Iterable
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

from bs4 import BeautifulSoup

SEARCH_HOST_SUFFIXES = (
    "google.com",
    "google.se",
    "googleusercontent.com",
    "duckduckgo.com",
)
DIRECTORY_HOST_SUFFIXES = (
    "allabolag.se",
    "hitta.se",
    "merinfo.se",
    "ratsit.se",
    "proff.se",
    "eniro.se",
    "uc.se",
    "linkedin.com",
    "facebook.com",
    "wikipedia.org",
    "youtube.com",
)


def hostname(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.").casefold()


def is_allabolag(url: str) -> bool:
    return _host_matches(url, ("allabolag.se",))


def is_google_host(url: str) -> bool:
    return _host_matches(url, SEARCH_HOST_SUFFIXES)


def is_directory_host(url: str) -> bool:
    return _host_matches(url, DIRECTORY_HOST_SUFFIXES)


def unwrap_href(href: str) -> str | None:
    value = unescape(href.strip())
    if value.startswith("/url?"):
        query = parse_qs(urlparse(value).query)
        value = (query.get("q") or query.get("url") or [""])[0]
    parsed = urlparse(value)
    uddg = parse_qs(parsed.query).get("uddg")
    if uddg:
        value = unquote(uddg[0])
    if value.startswith("//"):
        value = f"https:{value}"
    if not value.startswith(("http://", "https://")):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or is_google_host(value):
        return None
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, "")
    )


def parse_organic_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        url = unwrap_href(str(tag["href"]))
        if url is None or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def first_usable_website(urls: Iterable[str]) -> str | None:
    seen_hosts: set[str] = set()
    for url in urls:
        host = hostname(url)
        if not host or is_directory_host(url) or host in seen_hosts:
            continue
        seen_hosts.add(host)
        return url
    return None


def _host_matches(url: str, suffixes: tuple[str, ...]) -> bool:
    host = hostname(url)
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)
