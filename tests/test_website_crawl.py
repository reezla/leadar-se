import threading
import time

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
        Settings(website_crawl_max_pages=4, website_crawl_host_gap_seconds=0),
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
        Settings(website_crawl_max_pages=2, website_crawl_host_gap_seconds=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    profile = crawler.crawl("https://arkitema.se/")
    assert profile.suggested_recipient == "info@arkitema.com"
    assert "https://arkitema.se/kontakt" in profile.pages_fetched


def test_kontakt_page_fornamn_template_becomes_a_first_name_address() -> None:
    home = """
    <html><body>
      <a href="/kontakta-oss-2/">Kontakta oss</a>
    </body></html>
    """
    contact = """
    <html><body>
      <h3>Adesso Bygg AB</h3>
      <h4>Roger Andersen</h4>
      <p>E.post: förnamn@adessobygg.se</p>
      <h4>Nic Larson</h4>
      <p>E.post: förnamn@adessobygg.se</p>
    </body></html>
    """
    pages = {"/": home, "/kontakta-oss-2/": contact}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        html = pages.get(request.url.path)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html)

    crawler = WebsiteCrawler(
        Settings(website_crawl_max_pages=2, website_crawl_host_gap_seconds=0),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    profile = crawler.crawl("https://www.adessobygg.se/")
    assert profile.suggested_recipient == "roger@adessobygg.se"
    assert "https://www.adessobygg.se/kontakta-oss-2/" in profile.pages_fetched


def test_extra_pages_are_fetched_together() -> None:
    home = """
    <html><body>
      <a href="/om-oss">Om oss</a>
      <a href="/referenser">Referenser</a>
    </body></html>
    """
    in_flight = 0
    peak = 0
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        if request.url.path.endswith("robots.txt"):
            return httpx.Response(404)
        if request.url.path in {"/om-oss", "/referenser"}:
            with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            time.sleep(0.05)
            with lock:
                in_flight -= 1
        page = home if request.url.path == "/" else "<html><body><p>x</p></body></html>"
        return httpx.Response(200, text=page)

    crawler = WebsiteCrawler(
        Settings(
            website_crawl_max_pages=4,
            website_crawl_host_gap_seconds=0,
            website_crawl_per_host_in_flight=3,
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    crawler.crawl("https://aquasvea.se/")
    assert peak == 2


def test_connect_timeout_is_shorter_than_the_read_timeout() -> None:
    crawler = WebsiteCrawler(Settings())
    try:
        timeout = crawler.client.timeout
        assert timeout.connect == 5
        assert timeout.read == 10
    finally:
        crawler.close()


def test_interesting_links_skip_fragment_and_slash_duplicates() -> None:
    from lead_finder.providers.website_crawl import interesting_links

    html = """
    <a href="/kontakta-oss/">Kontakt</a>
    <a href="/kontakta-oss/#content">Kontakt</a>
    <a href="/kontakta-oss">Kontakt</a>
    <a href="https://example.se/projekt/">Projekt</a>
    """
    links = interesting_links("https://example.se/kontakta-oss/", html)
    assert links == ["https://example.se/projekt/"]


def test_start_url_moves_contact_page_to_root() -> None:
    from lead_finder.providers.website_crawl import start_url

    assert start_url("https://kartverkstan.se/kontakta-oss/") == "https://kartverkstan.se/"
    assert start_url("https://structor.se/geoteknik/") == "https://structor.se/geoteknik/"
    assert start_url("https://example.se/#top") == "https://example.se/"
