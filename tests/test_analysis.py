import json

import httpx

from lead_finder.analysis import (
    ProductAnalyzer,
    analyze_scored,
    apply_analysis,
    parse_analysis,
)
from lead_finder.config import Settings
from lead_finder.models import Company, CompanyAnalysis, ProductPick, ScoredCompany, WebsiteProfile
from lead_finder.outreach_prompt import user_prompt
from lead_finder.scanner_catalog import load_scanner_catalog
from lead_finder.use_company_store import analysis_patch, scored_from_store_row

SITE = (
    "Vi utför inmätning, utsättning och laserskanning. Projekt: SCA Ortviken - CTMP-anläggning, "
    "Timrå badhus."
)


def _scored(
    *,
    about: str | None = SITE,
    status: str = "crawled",
    employees: tuple[int, int] = (10, 19),
) -> ScoredCompany:
    return ScoredCompany(
        company=Company(
            organization_number="5567051304",
            name="A. N Mättjänster AB",
            sni_codes=["71121"],
            employee_min=employees[0],
            employee_max=employees[1],
            domain="https://www.mattjanster.se/",
        ),
        score=90,
        reasons=[],
        website=WebsiteProfile(url="https://www.mattjanster.se/", about_text=about),
        crawl_status=status,
    )


def _openai(payload: dict[str, object], seen: list[dict[str, object]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        body = {"choices": [{"message": {"content": json.dumps(payload)}}]}
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_catalog_has_all_nine_scanners() -> None:
    catalog = load_scanner_catalog()
    assert catalog.names() == ["P2", "P2 Vision+", "S1", "S2", "T1", "X1", "V4e", "C1", "V100F"]


def test_canonical_names_accept_marketing_names() -> None:
    catalog = load_scanner_catalog()
    assert catalog.canonical("FJD Trion T1") == "T1"
    assert catalog.canonical("fjd trion p2 vision+") == "P2 Vision+"
    assert catalog.canonical("FJD Trion P2 LiDAR") == "P2"
    assert catalog.canonical("v100f") == "V100F"
    assert catalog.canonical("Leica RTC360") is None


def test_parse_analysis_drops_unknown_products_and_invented_quotes() -> None:
    content = json.dumps(
        {
            "recommended_product": "FJD Trion T1",
            "alternatives": [
                {"product": "T1", "reason": "duplicate"},
                {"product": "Leica BLK", "reason": "not ours"},
                {"product": "V100F", "reason": "GNSS stakeout"},
                {"product": "P2", "reason": "interiors"},
                {"product": "C1", "reason": "too many"},
            ],
            "buyer_type": "performs_measurement",
            "customer_fit": "strong",
            "already_scans": True,
            "evidence": ["laserskanning", "they build rockets"],
            "outreach_angle": "Inne i CTMP-anläggningen tar stativ i varje rum tid.",
        }
    )
    analysis = parse_analysis(content, load_scanner_catalog(), SITE)
    assert analysis.recommended_product == "T1"
    assert [pick.product for pick in analysis.alternatives] == ["V100F", "P2"]
    assert analysis.evidence == ["laserskanning"]
    assert analysis.buyer_type == "performs_measurement"
    assert analysis.source == "ai"


def test_ai_analysis_sends_catalog_and_site_text() -> None:
    seen: list[dict[str, object]] = []
    client = _openai(
        {
            "recommended_product": "T1",
            "alternatives": [{"product": "P2", "reason": "plant interiors"}],
            "reason": "They already scan and survey plants.",
            "buyer_type": "performs_measurement",
            "customer_fit": "strong",
            "customer_fit_reason": "The site lists laserskanning.",
            "already_scans": True,
            "evidence": ["laserskanning"],
            "outreach_angle": "Mätning inne i anläggningar.",
        },
        seen,
    )
    analyzer = ProductAnalyzer(Settings(openai_api_key="sk-test"), client=client)
    result = analyze_scored(_scored(), analyzer)
    assert result.analysis is not None
    assert result.analysis.recommended_product == "T1"
    assert result.product_match is not None
    assert result.product_match.primary == "T1"
    assert result.product_match.alternative == "P2"
    assert result.product_match.confidence == "high"
    system = seen[0]["messages"][0]["content"]
    assert "V100F" in system and "Pick when" in system
    assert "SCA Ortviken" in seen[0]["messages"][1]["content"]


def test_ai_failure_falls_back_to_rules() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(broken))
    analyzer = ProductAnalyzer(Settings(openai_api_key="sk-test"), client=client)
    analysis = analyzer.analyze(_scored())
    assert analysis.source == "rules"
    assert analysis.recommended_product == "T1"
    assert analysis.already_scans is True


def test_empty_site_is_weak_fit() -> None:
    analyzer = ProductAnalyzer(Settings(openai_api_key=None))
    analysis = analyzer.analyze(_scored(about=None))
    assert analysis.customer_fit == "weak"


def test_uncrawled_company_is_not_analyzed() -> None:
    analyzer = ProductAnalyzer(Settings(openai_api_key=None))
    scored = _scored(status="crawl_failed")
    assert analyze_scored(scored, analyzer) is scored


def test_analysis_round_trips_through_store_row() -> None:
    analysis = CompanyAnalysis(
        recommended_product="C1",
        alternatives=[ProductPick(product="P2", reason="larger rooms")],
        reason="Property manager with many apartments.",
        buyer_type="orders_measurement",
        customer_fit="moderate",
        source="ai",
    )
    patch = analysis_patch(analysis)
    assert patch["recommended_product"] == "C1"
    assert patch["alternative_products"] == ["P2"]
    row = {"organization_number": "5560920075", "name": "Ebab AB", **patch}
    scored = scored_from_store_row(row)
    assert scored.analysis is not None
    assert scored.analysis.recommended_product == "C1"
    assert scored.product_match is not None
    assert scored.product_match.primary == "C1"
    assert scored.product_match.job == "Beställer mätning"


def test_email_prompt_includes_analysis() -> None:
    scored = apply_analysis(
        _scored(),
        CompanyAnalysis(
            recommended_product="T1",
            buyer_type="performs_measurement",
            already_scans=True,
            outreach_angle="Stativ i varje rum tar tid.",
        ),
    )
    prompt = user_prompt(
        scored.company,
        scored.website,
        scored.product_match,
        analysis=scored.analysis,
    )
    assert "Recommended scanner: T1" in prompt
    assert "Already scans: yes" in prompt
    assert "Stativ i varje rum tar tid." in prompt


class _NoCrawl:
    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        raise AssertionError(f"{url} should reuse the saved text, not be crawled")


class _FreshCrawl:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def crawl(self, url: str, *, source: str = "google") -> WebsiteProfile:
        self.urls.append(url)
        return WebsiteProfile(url=url, about_text="Vi mäter lagerhögar i täkter.", source=source)


def _job(*companies: ScoredCompany):  # noqa: ANN202
    from lead_finder.use_company_search import SearchResult, SearchSummary
    from lead_finder.use_lead_job import LeadJob

    return LeadJob(
        result=SearchResult(
            companies=list(companies),
            summary=SearchSummary(fetched=len(companies), matched=len(companies), incomplete=0),
        ),
        pending=[item.company.organization_number for item in companies],
        total=len(companies),
    )


def test_generate_leads_reuses_saved_text_and_recommends_scanners() -> None:
    from lead_finder.use_lead_crawl_pool import crawl_pending

    job = _job(_scored())
    analyzer = ProductAnalyzer(Settings(openai_api_key=None))
    crawl_pending(job, settings=Settings(), crawler=_NoCrawl(), analyzer=analyzer)
    scored = job.result.companies[0]
    assert job.snapshot()["summary"] == "Crawled 1 of 1."
    assert scored.analysis is not None
    assert scored.analysis.recommended_product == "T1"
    assert scored.product_match is not None and scored.product_match.primary == "T1"


def test_generate_leads_crawls_new_companies_then_recommends() -> None:
    from lead_finder.use_lead_crawl_pool import crawl_pending

    fresh = _scored(about=None, status="").model_copy(update={"website": None})
    crawler = _FreshCrawl()
    job = _job(fresh)
    crawl_pending(
        job,
        settings=Settings(),
        crawler=crawler,
        analyzer=ProductAnalyzer(Settings(openai_api_key=None)),
    )
    scored = job.result.companies[0]
    assert crawler.urls == ["https://www.mattjanster.se/"]
    assert scored.crawl_status == "crawled"
    assert scored.analysis is not None


def test_alternatives_column_lists_every_alternative() -> None:
    scored = apply_analysis(
        _scored(),
        CompanyAnalysis(
            recommended_product="T1",
            alternatives=[ProductPick(product="P2"), ProductPick(product="V100F")],
        ),
    )
    assert scored.product_match is not None
    assert scored.product_match.alternative == "P2, V100F"


def test_store_saves_without_analysis_columns_before_migration() -> None:
    from lead_finder.company_store_client import HttpCompanyStore

    bodies: list[list[dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        rows = json.loads(request.content)
        bodies.append(rows)
        if "recommended_product" in rows[0]:
            message = "Could not find the 'recommended_product' column (PGRST204)"
            return httpx.Response(400, json={"code": "PGRST204", "message": message})
        return httpx.Response(201)

    store = HttpCompanyStore(
        "https://x.supabase.co", "key", transport=httpx.MockTransport(handler)
    )
    scored = apply_analysis(_scored(), CompanyAnalysis(recommended_product="T1"))
    outcome = store.save_companies([scored], include_crawl=True)
    assert outcome.error == ""
    assert len(bodies) == 2
    assert "recommended_product" not in bodies[1][0]
    assert bodies[1][0]["about_text"] == SITE
