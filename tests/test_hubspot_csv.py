import csv
import io

from lead_finder.exporters.hubspot_csv import export_hubspot_csv
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
    rows = list(csv.DictReader(io.StringIO(content)))

    assert len(rows) == 1
    assert rows[0]["Organization number"] == "5561234567"
    assert rows[0]["Company domain name"] == "example.se"
    assert rows[0]["Lead score"] == "60"
    assert "Recommended product" not in rows[0]


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

    rows = list(csv.DictReader(io.StringIO(export_hubspot_csv([scored]))))

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
    rows = list(csv.DictReader(io.StringIO(export_hubspot_csv([scored]))))
    assert rows[0]["Website url"] == "https://aquasvea.se/"
    assert rows[0]["Outreach status"] == "drafted"
    assert rows[0]["Customer fit"] == "weak"
    assert "wind-tunnel" in rows[0]["Customer fit reason"]
    assert rows[0]["Outreach subject"] == "va scanning"
    assert rows[0]["Suggested recipient"] == "info@aquasvea.se"
