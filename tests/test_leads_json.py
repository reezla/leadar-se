import json

from lead_finder.exporters.leads_json import export_leads_json
from lead_finder.models import (
    Company,
    OutreachDraft,
    ProductMatch,
    ScoredCompany,
    ScoreReason,
    WebsiteProfile,
)


def test_json_export_deduplicates_and_keeps_nested_fields() -> None:
    company = Company(
        organization_number="556123-4567",
        name="Nordisk Mätteknik AB",
        sni_codes=["71120"],
        municipality="Göteborg",
        domain="https://www.example.se/contact",
    )
    payload = json.loads(
        export_leads_json(
            [
                ScoredCompany(
                    company=company,
                    score=40,
                    reasons=[ScoreReason(label="Relevant SNI", points=40)],
                ),
                ScoredCompany(
                    company=company,
                    score=60,
                    reasons=[ScoreReason(label="Relevant SNI and text", points=60)],
                ),
            ]
        )
    )

    assert payload["count"] == 1
    record = payload["companies"][0]
    assert record["score"] == 60
    assert record["company"]["organization_number"] == "5561234567"
    assert record["company"]["sni_codes"] == ["71120"]
    assert record["product_match"] is None


def test_json_export_includes_product_match() -> None:
    payload = json.loads(
        export_leads_json(
            [
                ScoredCompany(
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
            ]
        )
    )

    match = payload["companies"][0]["product_match"]
    assert match["brand"] == "norrpoint"
    assert match["primary"] == "S2"
    assert match["status"] == "matched"


def test_json_export_includes_outreach_draft() -> None:
    payload = json.loads(
        export_leads_json(
            [
                ScoredCompany(
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
                        website=WebsiteProfile(url="https://aquasvea.se/"),
                        customer_fit="strong",
                        customer_fit_reason="They document existing plants.",
                    ),
                )
            ]
        )
    )
    draft = payload["companies"][0]["outreach"]
    assert draft["status"] == "drafted"
    assert draft["subject"] == "va scanning"
    assert draft["website"]["url"] == "https://aquasvea.se/"
    assert draft["customer_fit"] == "strong"
    assert draft["customer_fit_reason"] == "They document existing plants."


def test_json_export_empty_list() -> None:
    assert json.loads(export_leads_json([])) == {"count": 0, "companies": []}
