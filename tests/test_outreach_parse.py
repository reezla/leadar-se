import json

from lead_finder.outreach_parse import normalize_customer_fit, parse_openai_content


def test_parse_json_includes_customer_fit() -> None:
    subject, body, fit, reason = parse_openai_content(
        json.dumps(
            {
                "subject": "va scanning",
                "body": "Hej,\n\nNi bygger vattenverk.",
                "customer_fit": "STRONG",
                "customer_fit_reason": "  Water plants need as-built interiors.  ",
            }
        )
    )
    assert subject == "va scanning"
    assert "vattenverk" in body
    assert fit == "strong"
    assert reason == "Water plants need as-built interiors."


def test_parse_aliases_medium_to_moderate() -> None:
    assert normalize_customer_fit("medium") == "moderate"
    assert normalize_customer_fit("low") == "weak"
    assert normalize_customer_fit("unknown") == ""


def test_parse_inclined_style_weak_fit() -> None:
    _, _, fit, reason = parse_openai_content(
        json.dumps(
            {
                "subject": "indoor flight",
                "body": "Hej,\n\nJag såg att ni bygger inclined wind tunnels.",
                "customer_fit": "weak",
                "customer_fit_reason": (
                    "The site is indoor wingsuit flying in wind tunnels, not surveying."
                ),
            }
        )
    )
    assert fit == "weak"
    assert "wind tunnels" in reason


def test_plain_email_leaves_fit_empty() -> None:
    email = "Hej,\n\nNorra Tornen är ett befintligt hus.\n\nVänliga hälsningar,\nNorrpoint"
    subject, body, fit, reason = parse_openai_content(email)
    assert subject == "norra tornen är ett"
    assert body == email
    assert fit == ""
    assert reason == ""
