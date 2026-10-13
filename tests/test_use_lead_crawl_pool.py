import threading

from lead_finder.config import Settings
from lead_finder.models import Company, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.providers.serper_search import SerperSearchError
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_lead_crawl_pool import crawl_pending
from lead_finder.use_lead_job import LeadJob
from lead_finder.use_website_find import WebsiteFind


class RecordingCrawler:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.barrier: threading.Barrier | None = None

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        self.calls.append((url, source))
        if self.barrier is not None:
            self.barrier.wait()
        return WebsiteProfile(url=url, about_text="Om oss", source=source)


def _company(org: str, name: str, domain: str | None = None) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=name, domain=domain),
        score=50,
        reasons=[ScoreReason(label="Relevant SNI", points=50)],
    )


def _job(*companies: ScoredCompany) -> LeadJob:
    return LeadJob(
        result=SearchResult(
            companies=list(companies),
            summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
        ),
        pending=[company.company.organization_number for company in companies],
        total=len(companies),
    )


def test_known_domains_crawl_together_without_a_lookup() -> None:
    crawler = RecordingCrawler()
    crawler.barrier = threading.Barrier(2, timeout=2)

    def resolve(*_args: object, **_kwargs: object) -> WebsiteFind:
        raise AssertionError("lookup should not run when every row has a website")

    job = _job(
        _company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/"),
        _company("5560000002", "Other AB", domain="https://other.se/"),
    )
    crawl_pending(
        job,
        settings=Settings(website_crawl_concurrency=2),
        crawler=crawler,
        resolve_websites=resolve,
    )
    assert job.phase == "done"
    assert job.done == 2
    assert job.snapshot()["summary"] == "Crawled 2 of 2."
    assert set(crawler.calls) == {
        ("https://aquasvea.se/", "existing_domain"),
        ("https://other.se/", "existing_domain"),
    }
    statuses = {item.company.name: item.crawl_status for item in job.result.companies}
    assert statuses == {"Aquasvea AB": "crawled", "Other AB": "crawled"}


def test_serper_urls_are_crawled_and_misses_are_saved() -> None:
    crawler = RecordingCrawler()

    def resolve(result: SearchResult, orgs: list[str], **_kwargs: object) -> WebsiteFind:
        companies = []
        for scored in result.companies:
            if scored.company.organization_number == "5560000001":
                company = scored.company.model_copy(update={"domain": "https://aquasvea.se/"})
                companies.append(scored.model_copy(update={"company": company}))
            else:
                companies.append(scored)
        return WebsiteFind(
            result=SearchResult(companies=companies, summary=result.summary),
            found=1,
            missed=["Other AB"],
        )

    job = _job(_company("5560000001", "Aquasvea AB"), _company("5560000002", "Other AB"))
    crawl_pending(job, settings=Settings(), crawler=crawler, resolve_websites=resolve)
    by_name = {item.company.name: item for item in job.result.companies}
    assert by_name["Aquasvea AB"].crawl_status == "crawled"
    assert by_name["Aquasvea AB"].website is not None
    assert by_name["Aquasvea AB"].website.source == "serper"
    assert by_name["Other AB"].crawl_status == "no_website"
    assert crawler.calls == [("https://aquasvea.se/", "serper")]
    assert job.notices == ["No website for Other AB."]


def test_lookup_failure_still_crawls_rows_that_already_have_a_site() -> None:
    crawler = RecordingCrawler()

    def resolve(*_args: object, **_kwargs: object) -> WebsiteFind:
        raise SerperSearchError("Set SERPER_API_KEY to find websites with Serper.")

    job = _job(
        _company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/"),
        _company("5560000002", "Other AB"),
    )
    crawl_pending(job, settings=Settings(), crawler=crawler, resolve_websites=resolve)
    by_name = {item.company.name: item for item in job.result.companies}
    assert by_name["Aquasvea AB"].crawl_status == "crawled"
    assert by_name["Other AB"].crawl_status == "search_failed"
    assert crawler.calls == [("https://aquasvea.se/", "existing_domain")]
    assert job.notices == ["Set SERPER_API_KEY to find websites with Serper."]


def test_stop_skips_companies_still_waiting() -> None:
    job = _job(
        _company("5560000001", "First AB", domain="https://first.se/"),
        _company("5560000002", "Second AB", domain="https://second.se/"),
    )

    class StoppingCrawler(RecordingCrawler):
        def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
            job.stop.set()
            return WebsiteProfile(url=url, about_text="Om", source=source)

    def resolve(*_args: object, **_kwargs: object) -> WebsiteFind:
        raise AssertionError("lookup should not run when every row has a website")

    crawl_pending(
        job,
        settings=Settings(website_crawl_concurrency=1),
        crawler=StoppingCrawler(),
        resolve_websites=resolve,
    )
    by_name = {item.company.name: item for item in job.result.companies}
    assert by_name["First AB"].crawl_status == "crawled"
    assert by_name["Second AB"].crawl_status is None
    assert job.snapshot()["summary"] == "Crawl stopped at 1 of 2."
