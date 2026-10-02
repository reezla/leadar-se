from lead_finder.config import Settings
from lead_finder.models import Company, OutreachDraft, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_outreach import generate_outreach, resolve_outreach_selection
from lead_finder.use_outreach_rewrite import rewrite_outreach


class FakeFinder:
    def __init__(self, urls: dict[str, str | None]) -> None:
        self.urls = urls
        self.names: list[str] = []

    def find_website(self, company: Company) -> str | None:
        self.names.append(company.name)
        if company.domain:
            return company.domain
        return self.urls.get(company.name)


class FakeCrawler:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        self.urls.append(url)
        return WebsiteProfile(url=url, about_text="Om oss", source=source)


class FakeWriter:
    def __init__(self) -> None:
        self.sender: str | None = None
        self.previous = ""

    def write(
        self,
        company: Company,
        profile: WebsiteProfile,
        match: object,
        sender: str = "norrpoint",
        previous: str = "",
    ) -> OutreachDraft:
        self.sender = sender
        self.previous = previous
        return OutreachDraft(
            subject="va scanning",
            body=f"Hej {company.name}",
            status="drafted",
            website=profile,
        )


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


def test_existing_domain_skips_search_mapping_and_writes_draft() -> None:
    finder = FakeFinder({"Other AB": "https://other.se/"})
    crawler = FakeCrawler()
    selected = _company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/")
    other = _company("5560000002", "Other AB")
    result = generate_outreach(
        _result(selected, other),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        finder=finder,
        crawler=crawler,
        writer=FakeWriter(),
    )
    drafted = result.companies[0]
    assert drafted.outreach is not None
    assert drafted.outreach.status == "drafted"
    assert drafted.company.domain == "https://aquasvea.se/"
    assert crawler.urls == ["https://aquasvea.se/"]
    assert result.companies[1].outreach is None


def test_missing_website_sets_status_and_leaves_others() -> None:
    finder = FakeFinder({"Aquasvea AB": None})
    result = generate_outreach(
        _result(_company("5560000001", "Aquasvea AB"), _company("5560000002", "Other AB")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        finder=finder,
        crawler=FakeCrawler(),
        writer=FakeWriter(),
    )
    assert result.companies[0].outreach is not None
    assert result.companies[0].outreach.status == "no_website"
    assert result.companies[0].outreach.detail == "No official website found."
    assert result.companies[1].outreach is None


def test_click_uses_stored_then_clears_it() -> None:
    chosen, persist = resolve_outreach_selection([], ["5560000001"], clicked=True)
    assert chosen == ["5560000001"]
    assert persist == []


def test_click_uses_current_selection_and_clears_stored() -> None:
    chosen, persist = resolve_outreach_selection(
        ["5560000002"], ["5560000001"], clicked=True
    )
    assert chosen == ["5560000002"]
    assert persist == []


def test_deselect_clears_stored_selection_when_not_clicked() -> None:
    chosen, persist = resolve_outreach_selection([], ["5560000001"], clicked=False)
    assert chosen == []
    assert persist == []


class RaisingCrawler:
    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        raise LookupError(f"robots.txt disallows {url}")


def test_crawl_failure_still_writes_a_draft() -> None:
    result = generate_outreach(
        _result(_company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        finder=FakeFinder({}),
        crawler=RaisingCrawler(),
        writer=FakeWriter(),
    )
    draft = result.companies[0].outreach
    assert draft is not None
    assert draft.status == "drafted"
    assert draft.body
    assert "crawl_failed" in draft.detail


def test_generate_passes_sender_to_writer() -> None:
    writer = FakeWriter()
    generate_outreach(
        _result(_company("5560000001", "Aquasvea AB", domain="https://aquasvea.se/")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        finder=FakeFinder({}),
        crawler=FakeCrawler(),
        writer=writer,
        sender="metricop",
    )
    assert writer.sender == "metricop"


def test_rewrite_uses_stored_crawl_and_previous_draft() -> None:
    writer = FakeWriter()
    company = _company("5560000001", "Arkitema AB", domain="https://www.arkitema.com/se")
    company = company.model_copy(
        update={
            "outreach": OutreachDraft(
                subject="hotel ottilia",
                body="Hej,\n\nKort utkast.",
                status="drafted",
                website=WebsiteProfile(
                    url="https://www.arkitema.com/se",
                    projects_text="Hotel Ottilia",
                ),
            )
        }
    )
    result = rewrite_outreach(
        _result(company),
        "5560000001",
        sender="Norrpoint",
        settings=Settings(openai_api_key="x"),
        writer=writer,
    )
    assert writer.previous == "Hej,\n\nKort utkast."
    assert writer.sender == "norrpoint"
    assert result.companies[0].outreach is not None
    assert result.companies[0].outreach.body == "Hej Arkitema AB"
