import csv
import io

from lead_finder.exporters.hubspot_csv import export_hubspot_csv
from lead_finder.models import Company, ScoredCompany, ScoreReason


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
