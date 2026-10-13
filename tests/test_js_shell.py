import httpx

from lead_finder.config import Settings
from lead_finder.providers.js_shell import is_js_shell
from lead_finder.providers.website_crawl import WebsiteCrawler

SHELL = """
<!doctype html>
<html><head>
  <title>Kompass Mätteknik - Professionella Mättjänster</title>
  <script type="module" src="/assets/index-abc.js"></script>
</head><body><div id="root"></div></body></html>
"""
RENDERED = """
<html><body>
  <a href="/kontakt">Kontakt</a>
  <a href="/projekt">Projekt</a>
  <p>Professionella mättjänster för infrastruktur, byggnader och byggprojekt.</p>
</body></html>
"""
CONTACT = '<html><body><a href="mailto:info@kompassmat.se">info</a></body></html>'
PROJECTS = "<html><body><p>Mätning av broar och tunnlar.</p></body></html>"


class _Renderer:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def render(self, url: str) -> str | None:
        self.urls.append(url)
        return self.pages.get(url)

    def close(self) -> None:
        return None


def test_module_shell_with_no_links_needs_a_browser() -> None:
    assert is_js_shell(SHELL)


def test_server_rendered_page_is_not_a_shell() -> None:
    assert not is_js_shell(RENDERED)


def test_analytics_script_on_a_short_page_is_not_a_shell() -> None:
    html = """
    <html><head><script src="https://www.googletagmanager.com/gtm.js"></script></head>
    <body><p>Kort sida om mätning.</p></body></html>
    """
    assert not is_js_shell(html)


def test_shell_is_rendered_and_inner_pages_are_read() -> None:
    pages = {
        "/": SHELL,
        "/kontakt": SHELL,
        "/projekt": PROJECTS,
    }
    renderer = _Renderer(
        {
            "https://www.kompassmat.se/": RENDERED,
            "https://www.kompassmat.se/kontakt": CONTACT,
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        html = pages.get(request.url.path)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html)

    crawler = WebsiteCrawler(
        Settings(website_crawl_max_pages=4, website_crawl_host_gap_seconds=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        renderer=renderer,
    )
    profile = crawler.crawl("https://www.kompassmat.se/", source="existing_domain")
    assert profile.suggested_recipient == "info@kompassmat.se"
    assert "infrastruktur" in (profile.about_text or "")
    assert "broar" in (profile.projects_text or "")
    assert renderer.urls == [
        "https://www.kompassmat.se/",
        "https://www.kompassmat.se/kontakt",
    ]
    assert "https://www.kompassmat.se/projekt" in profile.pages_fetched


def test_static_site_does_not_open_a_browser() -> None:
    renderer = _Renderer({})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        return httpx.Response(200, text=RENDERED)

    crawler = WebsiteCrawler(
        Settings(website_crawl_host_gap_seconds=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        renderer=renderer,
    )
    profile = crawler.crawl("https://www.kompassmat.se/")
    assert renderer.urls == []
    assert "infrastruktur" in (profile.about_text or "")


def test_failed_render_keeps_the_shell_page() -> None:
    renderer = _Renderer({})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        return httpx.Response(200, text=SHELL)

    crawler = WebsiteCrawler(
        Settings(website_crawl_host_gap_seconds=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        renderer=renderer,
    )
    profile = crawler.crawl("https://www.kompassmat.se/")
    assert renderer.urls == ["https://www.kompassmat.se/"]
    assert profile.suggested_recipient is None
    assert "Kompass Mätteknik" in (profile.about_text or "")
