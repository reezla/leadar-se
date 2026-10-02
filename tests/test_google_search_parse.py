from pathlib import Path

from lead_finder.providers.google_search_parse import first_usable_website, parse_organic_urls

FIXTURES = Path(__file__).parent / "fixtures"


def test_skips_allabolag_and_picks_next_result() -> None:
    html = (FIXTURES / "google_search_allabolag_first.html").read_text(encoding="utf-8")
    urls = parse_organic_urls(html)
    assert urls[0].startswith("https://www.allabolag.se/")
    assert first_usable_website(urls) == "https://aquasvea.se/"


def test_takes_first_result_when_it_is_not_allabolag() -> None:
    html = (FIXTURES / "google_search_direct.html").read_text(encoding="utf-8")
    assert first_usable_website(parse_organic_urls(html)) == "https://aquasvea.se/"


def test_returns_none_when_only_allabolag() -> None:
    assert first_usable_website(["https://www.allabolag.se/5561234567"]) is None


def test_skips_directory_sites() -> None:
    assert (
        first_usable_website(
            [
                "https://www.hitta.se/3do",
                "https://www.merinfo.se/3do",
                "https://3do.se/",
            ]
        )
        == "https://3do.se/"
    )


def test_unwraps_duckduckgo_uddg_links() -> None:
    html = """
    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2F3do.se%2F">3dO</a>
    """
    assert parse_organic_urls(html) == ["https://3do.se/"]
