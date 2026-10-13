from lead_finder.models import Company, OutreachDraft, ScoredCompany, ScoreReason, WebsiteProfile
from lead_finder.ui.copy_field import website_href
from lead_finder.ui.result_rows import crawled_table, score_explanation
from lead_finder.ui.results import _columns, _row


def test_website_href_opens_a_bare_domain() -> None:
    assert website_href("aquasvea.se") == "https://aquasvea.se"
    assert website_href("https://aquasvea.se/om") == "https://aquasvea.se/om"
    assert website_href("") is None
    assert website_href("Not set") is None


def test_row_omits_why_and_matches_column_list() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Test AB"),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
    )
    row = _row(scored, include_match=False)
    assert "Why" not in row
    assert list(row) == _columns(include_match=False)
    assert "Website" in row
    assert row["Email"] == ""
    assert row["Analyzed"] == ""


def test_row_strips_anstallda_from_employees() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="5561234567",
            name="Test AB",
            employee_class="20-49 anställda",
        ),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
    )
    assert _row(scored, include_match=False)["Employees"] == "20-49"


def test_outreach_row_includes_fit() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Inclined Labs AB"),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
        outreach=OutreachDraft(
            subject="indoor flight",
            body="Hej,",
            status="drafted",
            customer_fit="weak",
            suggested_recipient="info@inclined.ws",
        ),
    )
    row = _row(scored, include_match=False, include_outreach=True)
    assert row["Fit"] == "weak"
    assert row["Email"] == "info@inclined.ws"
    assert row["Email body"] == "Hej,"
    assert list(row) == _columns(include_match=False, include_outreach=True)


def test_crawl_row_includes_about_and_projects() -> None:
    scored = ScoredCompany(
        company=Company(
            organization_number="5561234567",
            name="Aquasvea AB",
            domain="https://aquasvea.se/",
        ),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
        website=WebsiteProfile(
            url="https://aquasvea.se/",
            about_text="VA-projekt",
            projects_text="Vattenverk",
            suggested_recipient="info@aquasvea.se",
        ),
        crawl_status="crawled",
    )
    row = _row(scored, include_match=False, include_crawl=True)
    assert row["About"] == "VA-projekt"
    assert row["Projects"] == "Vattenverk"
    assert row["Website"] == "https://aquasvea.se/"
    assert row["Email"] == "info@aquasvea.se"
    assert row["Analyzed"] == "Yes"
    assert scored.crawled is True
    assert list(row) == _columns(include_match=False, include_crawl=True)


def test_crawled_table_matches_the_find_companies_crawl_columns() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Aquasvea AB"),
        score=40,
        reasons=[ScoreReason(label="Relevant SNI", points=40)],
        website=WebsiteProfile(url="https://aquasvea.se/", about_text="VA-projekt"),
        crawl_status="crawled",
    )
    rows, columns = crawled_table([scored])
    assert columns == _columns(include_match=False, include_crawl=True)
    assert rows[0]["About"] == "VA-projekt"
    assert "Status" not in rows[0]


def test_score_cell_is_the_number_only() -> None:
    scored = ScoredCompany(
        company=Company(organization_number="5561234567", name="Test AB"),
        score=65,
        reasons=[
            ScoreReason(label="Relevant SNI 68201", points=40),
            ScoreReason(label="Company size indicates purchasing capacity", points=25),
        ],
    )
    assert _row(scored, include_match=False)["Score"] == 65
    assert score_explanation(scored) == [
        "Relevant SNI 68201 (+40)",
        "Company size indicates purchasing capacity (+25)",
    ]
