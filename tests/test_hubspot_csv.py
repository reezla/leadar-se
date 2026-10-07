import csv
import io

from lead_finder.exporters.hubspot_csv import DELIMITER, export_hubspot_csv
from lead_finder.models import (
    Company,
    OutreachDraft,
    ProductMatch,
    ScoredCompany,
    ScoreReason,
    WebsiteProfile,
)


def test_export_deduplicates_by_organization_number_and_normalizes_domain() -> None:
    company = Company(
        organization_number="556123-4567",
        name="Nordisk Mätteknik AB",
        sni_codes=["71120"],
        municipality="Göteborg",
        domain="https://www.example.se/contact",
    )
    lower_score = ScoredCompany(
        company=company,
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
    )
    higher_score = ScoredCompany(
        company=company,
        score=60,
        reasons=[ScoreReason(label="Relevant SNI and text", points=60)],
    )

    content = export_hubspot_csv([lower_score, higher_score])
    rows = _rows([lower_score, higher_score])

    assert content.splitlines()[0].startswith(
        "Company name;Company domain name;Suggested recipient;Organization number;"
    )
    assert "Data completeness warnings" not in content
    assert len(rows) == 1
    assert list(rows[0])[:4] == [
        "Company name",
        "Company domain name",
        "Suggested recipient",
        "Organization number",
    ]
    assert rows[0]["Organization number"] == "5561234567"
    assert rows[0]["Company domain name"] == "example.se"
    assert rows[0]["Suggested recipient"] == ""
    assert rows[0]["Lead score"] == "60"
    assert "Lead score reasons" not in rows[0]
    assert "Recommended product" not in rows[0]
    assert "About text" not in rows[0]


def test_export_includes_match_columns_after_analysis() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="556123-4567",
            name="Tunnel Entreprenad AB",
            sni_codes=["42130"],
        ),
        score=80,
        reasons=[ScoreReason(label="Relevant SNI", points=80)],
        product_match=ProductMatch(
            job="Tunnel, under jord och gruva",
            brand="norrpoint",
            primary="S2",
            alternative="T1",
            confidence="low",
            evidence=["Tunnel, under jord och gruva → S2 (SNI 42130)"],
            status="matched",
        ),
    )

    rows = _rows([scored])

    assert rows[0]["Recommended brand"] == "norrpoint"
    assert rows[0]["Recommended product"] == "S2"
    assert rows[0]["Alternative product"] == "T1"
    assert rows[0]["Match status"] == "matched"


def test_export_includes_outreach_columns_after_draft() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="556123-4567",
            name="Aquasvea AB",
            domain="https://aquasvea.se/",
        ),
        score=80,
        reasons=[ScoreReason(label="Relevant SNI", points=80)],
        outreach=OutreachDraft(
            subject="va scanning",
            body="Hej,",
            status="drafted",
            suggested_recipient="info@aquasvea.se",
            website=WebsiteProfile(url="https://aquasvea.se/"),
            customer_fit="weak",
            customer_fit_reason="Indoor wind-tunnel entertainment, not scanning.",
        ),
    )
    rows = _rows([scored])
    assert rows[0]["Website url"] == "https://aquasvea.se/"
    assert rows[0]["Outreach status"] == "drafted"
    assert rows[0]["Customer fit"] == "weak"
    assert "wind-tunnel" in rows[0]["Customer fit reason"]
    assert rows[0]["Outreach subject"] == "va scanning"
    assert rows[0]["Suggested recipient"] == "info@aquasvea.se"
    assert "Lead score reasons" not in rows[0]


def test_export_includes_crawled_website_text_without_outreach() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="556123-4567",
            name="Aquasvea AB",
            domain="https://aquasvea.se/",
        ),
        score=80,
        reasons=[ScoreReason(label="Relevant SNI", points=80)],
        crawl_status="crawled",
        website=WebsiteProfile(
            url="https://aquasvea.se/",
            about_text="VA-projekt",
            projects_text="Vattenverk",
            pages_fetched=["https://aquasvea.se/", "https://aquasvea.se/kontakt"],
            suggested_recipient="info@aquasvea.se",
        ),
    )
    rows = _rows([scored])
    assert rows[0]["About text"] == "VA-projekt"
    assert rows[0]["Projects text"] == "Vattenverk"
    assert rows[0]["Pages fetched"] == "https://aquasvea.se/; https://aquasvea.se/kontakt"
    assert rows[0]["Suggested recipient"] == "info@aquasvea.se"
    assert "Outreach subject" not in rows[0]


def _rows(companies: list[ScoredCompany]) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(export_hubspot_csv(companies)), delimiter=DELIMITER))
