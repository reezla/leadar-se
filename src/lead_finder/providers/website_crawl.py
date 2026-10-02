from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from lead_finder.config import Settings
from lead_finder.models import WebsiteProfile
from lead_finder.providers.google_search_parse import hostname
from lead_finder.providers.rate_limit import SlidingWindowRateLimiter

CONTACT_HINTS = ("kontakta oss", "kontakta-oss", "kontakt")
ABOUT_HINTS = ("om-oss", "omoss", "about-us", "about")
PROJECT_HINTS = ("referens", "projekt", "project", "uppdrag", "pagaende", "pågående")
PAGE_HINTS = (*CONTACT_HINTS, *ABOUT_HINTS, *PROJECT_HINTS)
GENERIC_LOCAL_PARTS = {"info", "kontakt", "contact", "hello", "hej", "sales", "order"}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
TEXT_LIMIT = 4_000


class WebsiteCrawler:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._robots: dict[str, RobotFileParser | None] = {}
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            settings.website_crawl_requests_per_window,
            settings.website_crawl_rate_limit_window_seconds,
        )
        self.client = client or httpx.Client(
            timeout=settings.website_crawl_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.allabolag_user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        homepage = self._fetch(url, required=True)
        pages = [url]
        about = [visible_text(homepage)]
        projects: list[str] = []
        recipient = generic_email(homepage)
        for link in interesting_links(url, homepage):
            if len(pages) >= self.settings.website_crawl_max_pages:
                break
            html = self._fetch(link, required=False)
            if html is None:
                continue
            pages.append(link)
            recipient = recipient or generic_email(html)
            if _classify(link) == "contact":
                continue
            text = visible_text(html)
            if _classify(link) == "projects":
                projects.append(text)
            else:
                about.append(text)
        return WebsiteProfile(
            url=url,
            about_text=_join(about),
            projects_text=_join(projects),
            pages_fetched=pages,
            source=source,
            suggested_recipient=recipient,
        )

    def _fetch(self, url: str, *, required: bool) -> str | None:
        if not self._allowed(url):
            if required:
                raise LookupError(f"robots.txt disallows {url}")
            return None
        self.rate_limiter.wait()
        try:
            response = self.client.get(url)
        except httpx.HTTPError as error:
            if required:
                raise LookupError(f"Could not fetch {url}") from error
            return None
        if response.status_code >= 400:
            if required:
                raise LookupError(f"Could not fetch {url}")
            return None
        return response.text

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url not in self._robots:
            self._robots[robots_url] = self._load_robots(robots_url)
        parser = self._robots[robots_url]
        return parser is None or parser.can_fetch(self.settings.allabolag_user_agent, url)

    def _load_robots(self, url: str) -> RobotFileParser | None:
        try:
            self.rate_limiter.wait()
            response = self.client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser


def interesting_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        absolute = urljoin(base_url, str(tag["href"]))
        if hostname(absolute) != hostname(base_url) or absolute in seen:
            continue
        blob = f"{urlparse(absolute).path} {tag.get_text(' ', strip=True)}".casefold()
        if not any(hint in blob for hint in PAGE_HINTS):
            continue
        seen.add(absolute)
        found.append(absolute)
    found.sort(key=lambda url: 0 if _classify(url) == "contact" else 1)
    return found


def visible_text(html: str, limit: int = TEXT_LIMIT) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())[:limit]


def generic_email(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select('a[href^="mailto:"]'):
        address = unquote(str(tag["href"]).split(":", 1)[-1]).split("?", 1)[0]
        if _is_generic(address):
            return address
    for match in EMAIL_RE.findall(html):
        if _is_generic(match):
            return match
    return None


def _classify(url: str) -> str:
    path = urlparse(url).path.casefold()
    if any(hint in path for hint in CONTACT_HINTS):
        return "contact"
    if any(hint in path for hint in PROJECT_HINTS):
        return "projects"
    if any(hint in path for hint in ABOUT_HINTS):
        return "about"
    return "home"


def _is_generic(address: str) -> bool:
    local = address.split("@", 1)[0].casefold()
    return local in GENERIC_LOCAL_PARTS


def _join(parts: list[str]) -> str | None:
    text = "\n\n".join(part for part in parts if part)
    return text or None
