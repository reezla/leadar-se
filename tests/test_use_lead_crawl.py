from lead_finder.config import Settings
from lead_finder.models import Company, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.providers.website_search import SearchBlocked, SearchFailed
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_lead_crawl import SEARCH_BLOCKED_NOTICE, generate_leads
from lead_finder.use_lead_queue import (
    after_batch,
    companies_to_crawl,
    estimate_crawl_seconds,
    format_crawl_estimate,
    take_batch,
)


class FakeFinder:
    def __init__(self, urls: dict[str, str | None]) -> None:
        self.urls = urls

    def find_website(self, company: Company) -> str | None:
        if company.domain:
            return company.domain
        return self.urls.get(company.name)


class FakeCrawler:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        self.urls.append(url)
        return WebsiteProfile(
            url=url,
            about_text="Om oss",
            projects_text="VA-projekt",
            suggested_recipient="info@example.se",
            source=source,
        )


class RaisingCrawler:
    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        raise LookupError(f"robots.txt disallows {url}")


def _result(*companies: ScoredCompany) -> SearchResult:
    return SearchResult(
        companies=list(companies),
        summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
    )


def _company(org: str, name: str, domain: str | None = None) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=name, domain=domain),
        score=50,
        reasons=[ScoreReason(label="Relevant SNI", points=50)],
    )


def test_existing_domain_crawls_without_drafting() -> None:
    finder = FakeFinder({"Other AB": "https://other.se/"})
    crawler = FakeCrawler()
    selected = _company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/")
    other = _company("5560000002", "Other AB")
    batch = generate_leads(
        _result(selected, other),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        finder=finder,
        crawler=crawler,
    )
    crawled = batch.result.companies[0]
    assert crawled.outreach is None
    assert crawled.crawl_status == "crawled"
    assert crawled.company.domain == "https://aquasvea.se/"
    assert crawled.website is not None
    assert crawled.website.about_text == "Om oss"
    assert crawled.website.projects_text == "VA-projekt"
    assert crawler.urls == ["https://aquasvea.se/"]
    assert batch.result.companies[1].crawl_status is None
    assert batch.records[0]["company"] == "Aquasvea AB"
    website = batch.records[0]["website"]
    assert isinstance(website, dict)
    assert website["about_text"] == "Om oss"
    assert website["projects_text"] == "VA-projekt"


def test_missing_website_sets_crawl_status_and_leaves_others() -> None:
    finder = FakeFinder({"Aquasvea AB": None})
    batch = generate_leads(
        _result(_company("5560000001", "Aquasvea AB"), _company("5560000002", "Other AB")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        finder=finder,
        crawler=FakeCrawler(),
    )
    missed = batch.result.companies[0]
    assert missed.outreach is None
    assert missed.website is None
    assert missed.crawl_status == "no_website"
    assert missed.crawl_detail == "No official website found."
    assert batch.result.companies[1].crawl_status is None
    assert batch.records[0]["crawl_status"] == "no_website"
    assert batch.records[0]["website"] is None


def test_crawl_failure_keeps_url_and_skips_email() -> None:
    batch = generate_leads(
        _result(_company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        finder=FakeFinder({}),
        crawler=RaisingCrawler(),
    )
    crawled = batch.result.companies[0]
    assert crawled.outreach is None
    assert crawled.crawl_status == "crawl_failed"
    assert crawled.website is not None
    assert crawled.website.url == "https://aquasvea.se/"
    assert "crawl_failed" in crawled.crawl_detail
    assert "crawl_failed" in str(batch.records[0]["crawl_detail"])
    assert batch.notices == [
        "Crawl failed for Aquasvea AB: crawl_failed: robots.txt disallows https://aquasvea.se/"
    ]
    assert batch.stopped is False


class BlockingFinder:
    blocked_detail = None
    request_failed = False

    def find_website(self, company: Company) -> str | None:
        raise SearchBlocked("Search blocked this network.")


class FailingFinder:
    blocked_detail = None
    request_failed = False

    def find_website(self, company: Company) -> str | None:
        if company.name == "Aquasvea AB":
            raise SearchFailed("Search returned HTTP 503.")
        return "https://other.se/"


def test_search_block_stops_before_the_next_company() -> None:
    batch = generate_leads(
        _result(
            _company("5560000001", "Aquasvea AB"),
            _company("5560000002", "Other AB"),
        ),
        ["5560000001", "5560000002"],
        settings=Settings(outreach_max_selected=20),
        finder=BlockingFinder(),
        crawler=FakeCrawler(),
    )
    assert batch.stopped is True
    assert batch.notices == [SEARCH_BLOCKED_NOTICE]
    assert batch.result.companies[0].crawl_status is None
    assert batch.result.companies[1].crawl_status is None


def test_search_failure_keeps_going() -> None:
    batch = generate_leads(
        _result(
            _company("5560000001", "Aquasvea AB"),
            _company("5560000002", "Other AB"),
        ),
        ["5560000001", "5560000002"],
        settings=Settings(outreach_max_selected=20),
        finder=FailingFinder(),
        crawler=FakeCrawler(),
    )
    assert batch.stopped is False
    assert batch.notices == ["Search failed for Aquasvea AB: Search returned HTTP 503."]
    assert batch.result.companies[0].crawl_status == "search_failed"
    assert batch.result.companies[1].crawl_status == "crawled"
    assert batch.result.companies[1].website is not None


def test_queue_skips_finished_rows_and_batches_the_rest() -> None:
    done = _company("5560000001", "Aquasvea AB").model_copy(update={"crawl_status": "crawled"})
    failed = _company("5560000002", "Search AB").model_copy(
        update={"crawl_status": "search_failed"}
    )
    waiting = _company("5560000003", "Waiting AB")
    result = _result(done, failed, waiting)
    pending = companies_to_crawl(
        result,
        ["5560000001", "5560000002", "5560000003", "5560000002"],
    )
    assert pending == ["5560000002", "5560000003"]
    batch, rest = take_batch(pending, 1)
    assert batch == ["5560000002"]
    assert rest == ["5560000003"]
    remaining, done_count, phase = after_batch(
        pending,
        batch,
        ["5560000002"],
        done=0,
        stopped=False,
    )
    assert remaining == ["5560000003"]
    assert done_count == 1
    assert phase == "wait"
    stopped, stopped_count, stopped_phase = after_batch(
        pending,
        batch,
        [],
        done=0,
        stopped=True,
    )
    assert stopped == []
    assert stopped_count == 0
    assert stopped_phase == "idle"


def test_should_stop_skips_the_rest_of_the_batch() -> None:
    finder = FakeFinder({})
    crawler = FakeCrawler()
    first = _company("5560000001", "First AB", domain="https://first.se/")
    second = _company("5560000002", "Second AB", domain="https://second.se/")
    calls = {"count": 0}

    def should_stop() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    batch = generate_leads(
        _result(first, second),
        ["5560000001", "5560000002"],
        settings=Settings(outreach_max_selected=20),
        finder=finder,
        crawler=crawler,
        should_stop=should_stop,
    )
    assert crawler.urls == ["https://first.se/"]
    assert batch.stopped is True
    assert batch.result.companies[0].crawl_status == "crawled"
    assert batch.result.companies[1].crawl_status is None


def test_stop_during_search_error_leaves_the_row_untouched() -> None:
    stop = {"now": False}

    class StopFinder:
        blocked_detail = None
        request_failed = False

        def find_website(self, company: Company) -> str | None:
            stop["now"] = True
            raise SearchFailed("Search returned HTTP 202.")

    batch = generate_leads(
        _result(_company("5560000001", "Akustikforum AB")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        finder=StopFinder(),
        crawler=FakeCrawler(),
        should_stop=lambda: stop["now"],
    )
    assert batch.stopped is True
    assert batch.notices == []
    assert batch.result.companies[0].crawl_status is None


def test_crawl_estimate_includes_pauses_between_batches() -> None:
    assert estimate_crawl_seconds(20, batch_size=20, pause_seconds=8) == 400
    assert estimate_crawl_seconds(21, batch_size=20, pause_seconds=8) == 428
    assert estimate_crawl_seconds(0, batch_size=20, pause_seconds=8) == 0
    assert format_crawl_estimate(400) == "about 7 min"
    assert format_crawl_estimate(3600) == "about 1 h"
    assert format_crawl_estimate(3900) == "about 1 h 5 min"
