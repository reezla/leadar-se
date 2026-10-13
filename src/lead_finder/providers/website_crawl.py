from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from lead_finder.config import Settings
from lead_finder.models import WebsiteProfile
from lead_finder.providers.email_extract import suggested_email
from lead_finder.providers.google_search_parse import hostname
from lead_finder.providers.js_shell import is_js_shell
from lead_finder.providers.page_render import PageRenderer, PlaywrightRenderer
from lead_finder.providers.rate_limit import HostRequestGate

CONTACT_HINTS = ("kontakta oss", "kontakta-oss", "kontakt")
ABOUT_HINTS = ("om-oss", "omoss", "about-us", "about")
PROJECT_HINTS = ("referens", "projekt", "project", "uppdrag", "pagaende", "pågående")
PAGE_HINTS = (*CONTACT_HINTS, *ABOUT_HINTS, *PROJECT_HINTS)
TEXT_LIMIT = 4_000


class WebsiteCrawler:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        gate: HostRequestGate | None = None,
        renderer: PageRenderer | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._renderer = renderer
        self._owns_renderer = False
        self._renderer_lock = threading.Lock()
        self._robots: dict[str, RobotFileParser | None] = {}
        self._robots_lock = threading.Lock()
        self.gate = gate or HostRequestGate(
            max_in_flight=settings.website_crawl_max_in_flight,
            per_host_in_flight=settings.website_crawl_per_host_in_flight,
            host_gap_seconds=settings.website_crawl_host_gap_seconds,
        )
        self.client = client or httpx.Client(
            timeout=_timeout(settings),
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=max(1, settings.website_crawl_max_in_flight),
                max_keepalive_connections=max(1, settings.website_crawl_max_in_flight),
            ),
            headers={
                "User-Agent": settings.allabolag_user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()
        with self._renderer_lock:
            renderer = self._renderer if self._owns_renderer else None
            if self._owns_renderer:
                self._renderer = None
        if renderer is not None:
            renderer.close()

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        url = start_url(url)
        homepage = self._fetch(url, required=True)
        pages = [url]
        about = [visible_text(homepage)]
        projects: list[str] = []
        recipient = suggested_email(homepage, page_url=url)
        for link, html in self._fetch_pages(url, homepage):
            if html is None:
                continue
            pages.append(link)
            recipient = recipient or suggested_email(html, page_url=link)
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

    def _fetch_pages(self, url: str, homepage: str) -> list[tuple[str, str | None]]:
        room = self.settings.website_crawl_max_pages - 1
        if room <= 0:
            return []
        links = interesting_links(url, homepage)[:room]
        if len(links) <= 1:
            return [(link, self._fetch(link, required=False)) for link in links]
        workers = min(len(links), self.settings.website_crawl_per_host_in_flight)
        html_by_url: dict[str, str | None] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._fetch, link, required=False): link for link in links}
            for future in as_completed(futures):
                html_by_url[futures[future]] = future.result()
        return [(link, html_by_url[link]) for link in links]

    def _fetch(self, url: str, *, required: bool) -> str | None:
        if not self._allowed(url):
            if required:
                raise LookupError(f"robots.txt disallows {url}")
            return None
        with self.gate.slot(hostname(url) or url):
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
            return self._with_shell(url, response.text)

    def _with_shell(self, url: str, html: str) -> str:
        if not is_js_shell(html):
            return html
        rendered = self._render_shell(url)
        if not rendered or (is_js_shell(rendered) and len(rendered) <= len(html)):
            return html
        return rendered

    def _render_shell(self, url: str) -> str | None:
        renderer = self._shell_renderer()
        if renderer is None:
            return None
        return renderer.render(url)

    def _shell_renderer(self) -> PageRenderer | None:
        if self._renderer is not None:
            return self._renderer
        with self._renderer_lock:
            if self._renderer is None:
                self._renderer = PlaywrightRenderer(
                    user_agent=self.settings.allabolag_user_agent,
                    timeout_seconds=self.settings.website_render_timeout_seconds,
                )
                self._owns_renderer = True
            return self._renderer

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        with self._robots_lock:
            if robots_url in self._robots:
                parser = self._robots[robots_url]
                return parser is None or parser.can_fetch(self.settings.allabolag_user_agent, url)
        parser = self._load_robots(robots_url)
        with self._robots_lock:
            self._robots.setdefault(robots_url, parser)
            parser = self._robots[robots_url]
        return parser is None or parser.can_fetch(self.settings.allabolag_user_agent, url)

    def _load_robots(self, url: str) -> RobotFileParser | None:
        try:
            with self.gate.slot(hostname(url) or url):
                response = self.client.get(url)
                if response.status_code >= 400:
                    return None
                text = response.text
        except httpx.HTTPError:
            return None
        parser = RobotFileParser()
        parser.parse(text.splitlines())
        return parser


def interesting_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = {_page_key(base_url)}
    for tag in soup.find_all("a", href=True):
        absolute = urldefrag(urljoin(base_url, str(tag["href"]))).url
        key = _page_key(absolute)
        if hostname(absolute) != hostname(base_url) or key in seen:
            continue
        blob = f"{urlparse(absolute).path} {tag.get_text(' ', strip=True)}".casefold()
        if not any(hint in blob for hint in PAGE_HINTS):
            continue
        seen.add(key)
        found.append(absolute)
    found.sort(key=lambda url: 0 if _classify(url) == "contact" else 1)
    return found


def start_url(url: str) -> str:
    """Start from the site root when search handed us a contact/about/project subpage."""
    parsed = urlparse(urldefrag(url).url)
    if parsed.path.strip("/") and _classify(url) != "home":
        return f"{parsed.scheme}://{parsed.netloc}/"
    return urldefrag(url).url


def _page_key(url: str) -> str:
    """Same page regardless of #fragment, trailing slash, scheme or www."""
    parsed = urlparse(urldefrag(url).url)
    host = (parsed.netloc or "").casefold().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{host}{path}{query}"


def visible_text(html: str, limit: int = TEXT_LIMIT) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())[:limit]


def _classify(url: str) -> str:
    path = urlparse(url).path.casefold()
    if any(hint in path for hint in CONTACT_HINTS):
        return "contact"
    if any(hint in path for hint in PROJECT_HINTS):
        return "projects"
    if any(hint in path for hint in ABOUT_HINTS):
        return "about"
    return "home"


def _join(parts: list[str]) -> str | None:
    text = "\n\n".join(part for part in parts if part)
    return text or None


def _timeout(settings: Settings) -> httpx.Timeout:
    read = settings.website_crawl_timeout_seconds
    connect = settings.website_crawl_connect_timeout_seconds
    return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)
