import httpx

from lead_finder.config import Settings
from lead_finder.providers.website_crawl import WebsiteCrawler

HOME = """
<html>
  <body>
    <a href="mailto:info@aquasvea.se">info@aquasvea.se</a>
    <a href="/om-oss">Om oss</a>
    <a href="/referenser">Referenser</a>
    <p>Välkommen till Aquasvea, din partner inom vatten och miljö.</p>
  </body>
</html>
"""
ABOUT = "<html><body><p>Om oss: VA-processteknik och projekt.</p></body></html>"
PROJECTS = "<html><body><p>Referenser: membranteknik i två vattenverk.</p></body></html>"


def _crawler() -> WebsiteCrawler:
    pages = {"/": HOME, "/om-oss": ABOUT, "/referenser": PROJECTS}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        html = pages.get(request.url.path)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WebsiteCrawler(
        Settings(website_crawl_max_pages=4, website_crawl_requests_per_window=100),
        client=client,
    )


def test_crawls_om_oss_and_referenser() -> None:
    profile = _crawler().crawl("https://aquasvea.se/", source="google")
    assert profile.url == "https://aquasvea.se/"
    assert profile.suggested_recipient == "info@aquasvea.se"
    assert "vatten och miljö" in (profile.about_text or "")
    assert "VA-processteknik" in (profile.about_text or "")
    assert "membranteknik" in (profile.projects_text or "")
    assert "https://aquasvea.se/om-oss" in profile.pages_fetched
    assert "https://aquasvea.se/referenser" in profile.pages_fetched


def test_kontakt_page_is_checked_for_a_generic_email() -> None:
    home = """
    <html><body>
      <a href="/projekt">Projekt</a>
      <a href="/kontakt">Kontakta oss</a>
    </body></html>
    """
    contact = '<html><body><a href="mailto:info@arkitema.com">info</a></body></html>'
    project = "<html><body><p>Hotel Ottilia</p></body></html>"
    pages = {"/": home, "/kontakt": contact, "/projekt": project}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        html = pages.get(request.url.path)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html)

    crawler = WebsiteCrawler(
        Settings(website_crawl_max_pages=2, website_crawl_requests_per_window=100),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    profile = crawler.crawl("https://arkitema.se/")
    assert profile.suggested_recipient == "info@arkitema.com"
    assert "https://arkitema.se/kontakt" in profile.pages_fetched
