from datetime import UTC, datetime

from lead_finder.config import Segment
from lead_finder.models import Company, CompanySearchFilters
from lead_finder.scoring import filter_companies, score_company


def test_scoring_is_explainable_and_deterministic() -> None:
    company = Company(
        organization_number="556123-4567",
        name="Nordisk Mätteknik AB",
        sni_codes=["71120"],
        activity_description="Geodata och 3D-dokumentation",
        municipality="Göteborg",
        county="Västra Götaland",
        employee_min=10,
        employee_max=19,
        revenue_class="10–49 MSEK",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    segment = Segment(
        name="Mätning",
        description="",
        sni_prefixes=["7112"],
        keywords=["geodata", "3d"],
        weights={"sni": 45, "keyword": 20, "size": 20, "geography": 10, "freshness": 5},
    )
    filters = CompanySearchFilters(counties=["Västra Götaland"])

    result = score_company(
        company,
        segment,
        filters,
        now=datetime(2026, 9, 29, tzinfo=UTC),
    )

    assert result.score == 100
    assert [reason.points for reason in result.reasons] == [45, 20, 20, 10, 5]
    assert result.missing_data == []


def test_filters_keep_unknown_size_but_remove_wrong_sni() -> None:
    relevant = Company(
        organization_number="1",
        name="Relevant AB",
        sni_codes=["42210"],
    )
    irrelevant = Company(
        organization_number="2",
        name="Irrelevant AB",
        sni_codes=["47191"],
    )
    filters = CompanySearchFilters(
        sni_prefixes=["42"],
        employee_min=10,
    )

    result = filter_companies([relevant, irrelevant], filters)

    assert result == [relevant]
