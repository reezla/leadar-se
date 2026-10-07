from lead_finder.config import Settings
from lead_finder.models import Company, OutreachDraft, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_outreach import generate_outreach, resolve_outreach_selection
from lead_finder.use_outreach_rewrite import rewrite_outreach


class FakeWriter:
    def __init__(self) -> None:
        self.sender: str | None = None
        self.previous = ""
        self.profiles: list[WebsiteProfile] = []

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
        self.profiles.append(profile)
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


def _crawled(org: str, name: str, *, status: str = "crawled", detail: str = "") -> ScoredCompany:
    profile = (
        None
        if status == "no_website"
        else WebsiteProfile(
            url="https://aquasvea.se/",
            about_text="Om oss",
            projects_text="VA-projekt",
        )
    )
    return _company(org, name, domain=None if profile is None else profile.url).model_copy(
        update={"website": profile, "crawl_status": status, "crawl_detail": detail}
    )


def test_outreach_drafts_from_stored_crawl() -> None:
    writer = FakeWriter()
    selected = _crawled("5560000001", "Aquasvea AB")
    other = _company("5560000002", "Other AB")
    result = generate_outreach(
        _result(selected, other),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        writer=writer,
    )
    drafted = result.companies[0]
    assert drafted.outreach is not None
    assert drafted.outreach.status == "drafted"
    assert drafted.outreach.body == "Hej Aquasvea AB"
    assert writer.profiles[0].about_text == "Om oss"
    assert writer.profiles[0].projects_text == "VA-projekt"
    assert result.companies[1].outreach is None


def test_outreach_skips_rows_that_were_not_crawled() -> None:
    writer = FakeWriter()
    result = generate_outreach(
        _result(_company("5560000001", "Aquasvea AB")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        writer=writer,
    )
    assert writer.profiles == []
    assert result.companies[0].outreach is None


def test_missing_website_sets_status_without_calling_writer() -> None:
    writer = FakeWriter()
    missed = _crawled(
        "5560000001",
        "Aquasvea AB",
        status="no_website",
        detail="No official website found.",
    )
    result = generate_outreach(
        _result(missed),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20),
        writer=writer,
    )
    assert writer.profiles == []
    assert result.companies[0].outreach is not None
    assert result.companies[0].outreach.status == "no_website"
    assert result.companies[0].outreach.detail == "No official website found."


def test_click_uses_stored_then_clears_it() -> None:
    chosen, persist = resolve_outreach_selection([], ["5560000001"], clicked=True)
    assert chosen == ["5560000001"]
    assert persist == []


def test_click_uses_current_selection_and_clears_stored() -> None:
    chosen, persist = resolve_outreach_selection(["5560000002"], ["5560000001"], clicked=True)
    assert chosen == ["5560000002"]
    assert persist == []


def test_deselect_clears_stored_selection_when_not_clicked() -> None:
    chosen, persist = resolve_outreach_selection([], ["5560000001"], clicked=False)
    assert chosen == []
    assert persist == []


def test_crawl_failure_still_writes_a_draft() -> None:
    result = generate_outreach(
        _result(
            _crawled(
                "5560000001",
                "Aquasvea AB",
                status="crawl_failed",
                detail="crawl_failed: robots.txt disallows https://aquasvea.se/",
            )
        ),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        writer=FakeWriter(),
    )
    draft = result.companies[0].outreach
    assert draft is not None
    assert draft.status == "drafted"
    assert draft.body
    assert "crawl_failed" in draft.detail


def test_ai_failure_is_reported_and_kept_on_the_draft() -> None:
    class FailingWriter(FakeWriter):
        def write(
            self,
            company: Company,
            profile: WebsiteProfile,
            match: object,
            sender: str = "norrpoint",
            previous: str = "",
        ) -> OutreachDraft:
            draft = super().write(company, profile, match, sender, previous)
            return draft.model_copy(update={"detail": "AI generation failed: HTTP 429."})

    notices: list[str] = []
    company = _crawled("5560000001", "Aquasvea AB").model_copy(
        update={"crawl_detail": "crawl_failed: timeout"}
    )
    result = generate_outreach(
        _result(company),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        writer=FailingWriter(),
        on_notice=notices.append,
    )
    draft = result.companies[0].outreach
    assert draft is not None
    assert draft.detail == "AI generation failed: HTTP 429."
    assert notices == ["AI generation failed: HTTP 429."]


def test_generate_passes_sender_to_writer() -> None:
    writer = FakeWriter()
    generate_outreach(
        _result(_crawled("5560000001", "Aquasvea AB")),
        ["5560000001"],
        settings=Settings(outreach_max_selected=20, openai_api_key="x"),
        writer=writer,
        sender="metricop",
    )
    assert writer.sender == "metricop"


def test_rewrite_uses_stored_crawl_and_previous_draft() -> None:
    writer = FakeWriter()
    company = _company("5560000001", "Arkitema AB", domain="https://www.arkitema.com/se")
    company = company.model_copy(
        update={
            "website": WebsiteProfile(
                url="https://www.arkitema.com/se",
                projects_text="Hotel Ottilia",
            ),
            "crawl_status": "crawled",
            "outreach": OutreachDraft(
                subject="hotel ottilia",
                body="Hej,\n\nKort utkast.",
                status="drafted",
                website=WebsiteProfile(url="https://www.arkitema.com/se"),
            ),
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
    assert writer.profiles[0].projects_text == "Hotel Ottilia"
    assert result.companies[0].outreach is not None
    assert result.companies[0].outreach.body == "Hej Arkitema AB"
