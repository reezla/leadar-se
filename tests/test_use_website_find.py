from lead_finder.config import Settings
from lead_finder.models import Company, ScoredCompany, ScoreReason
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_website_find import assign_serper_websites, miss_notice


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def post(self, url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
        assert isinstance(json, list)
        self.queries = [item["q"] for item in json]
        payload = [
            {"organic": [{"link": "https://toofab.se/"}]},
            {"organic": []},
        ]
        return FakeResponse(payload)


def _company(org: str, name: str, domain: str | None = None) -> ScoredCompany:
    return ScoredCompany(
        company=Company(organization_number=org, name=name, domain=domain),
        score=10,
        reasons=[ScoreReason(label="Relevant SNI", points=10)],
    )


def _result(*companies: ScoredCompany) -> SearchResult:
    return SearchResult(
        companies=list(companies),
        summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
    )


def test_assign_saves_serper_url_on_the_matching_company() -> None:
    client = FakeClient()
    result = assign_serper_websites(
        _result(
            _company("5560000001", "Toofab AB"),
            _company("5560000002", "Trafikia AB"),
            _company("5560000003", "Already AB", domain="https://already.se"),
        ),
        ["5560000001", "5560000002", "5560000003"],
        settings=Settings(serper_api_key="test-key"),
        client=client,
    )
    saved = {item.company.name: item.company.domain for item in result.result.companies}
    assert saved["Toofab AB"] == "https://toofab.se/"
    assert saved["Trafikia AB"] is None
    assert saved["Already AB"] == "https://already.se"
    assert result.found == 1
    assert result.missed == ["Trafikia AB"]
    assert client.queries == ["Toofab AB", "Trafikia AB"]
    assert result.result.companies[0].crawl_status is None


def test_assign_skips_serper_when_every_row_has_a_website() -> None:
    class Unused:
        def post(self, url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
            raise AssertionError("Serper was called")

    result = assign_serper_websites(
        _result(_company("5560000001", "Toofab AB", domain="https://toofab.se")),
        ["5560000001"],
        settings=Settings(serper_api_key="test-key"),
        client=Unused(),
    )
    assert result.found == 0
    assert result.missed == []


def test_miss_notice_names_the_first_companies() -> None:
    notice = miss_notice(["A", "B", "C", "D", "E", "F"])
    assert notice == "No website for A, B, C, D, E, and 1 more."
