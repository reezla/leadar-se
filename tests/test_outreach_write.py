import json

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, ProductMatch, WebsiteProfile
from lead_finder.outreach_prompt import spoken_company_name, user_prompt
from lead_finder.outreach_sender import system_prompt
from lead_finder.outreach_write import OutreachWriter


def test_user_prompt_includes_product_and_site_text() -> None:
    prompt = user_prompt(
        Company(organization_number="5560000001", name="Aquasvea AB", sni_codes=["42910"]),
        WebsiteProfile(
            url="https://aquasvea.se/",
            about_text="VA-projekt",
            projects_text="Membran",
        ),
        ProductMatch(brand="norrpoint", primary="P2 Vision+", job="Energi och termografi"),
        "norrpoint",
    )
    assert "Sender: Norrpoint" in prompt
    assert "handheld LiDAR" in prompt
    assert "VA-projekt" in prompt
    assert "Membran" in prompt
    assert "Energi och termografi" in prompt
    assert "Empty or missing site text = weak" in prompt
    assert "customer_fit" in prompt
    assert "Spoken name: Aquasvea" in prompt
    assert "Jag såg att ni på Aquasvea" in prompt
    assert "Aquasvea AB" in prompt


def test_writer_parses_json_draft_and_does_not_send_mail() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        payload = {
            "subject": "va scanning",
            "body": "Hej,\n\nNi bygger vattenverk. Intresserade?",
            "customer_fit": "strong",
            "customer_fit_reason": (
                "They build water treatment plants that need as-built interiors."
            ),
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    writer = OutreachWriter(
        Settings(openai_api_key="test-key", openai_api_url="https://api.openai.com/v1/chat/completions"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    draft = writer.write(
        Company(organization_number="5560000001", name="Aquasvea AB"),
        WebsiteProfile(url="https://aquasvea.se/", suggested_recipient="info@aquasvea.se"),
        None,
    )
    assert draft.status == "drafted"
    assert draft.subject == "va scanning"
    assert "vattenverk" in draft.body
    assert draft.customer_fit == "strong"
    assert "water treatment" in draft.customer_fit_reason
    assert draft.suggested_recipient == "info@aquasvea.se"
    assert captured[0].url.path.endswith("/chat/completions")
    assert captured[0].headers["authorization"] == "Bearer test-key"
    sent = json.loads(captured[0].content)
    assert sent["response_format"] == {"type": "json_object"}


def test_writer_without_api_key_returns_sell_template() -> None:
    draft = OutreachWriter(Settings(openai_api_key=None)).write(
        Company(organization_number="5560000001", name="Aquasvea AB"),
        WebsiteProfile(url="https://aquasvea.se/", about_text="VA-projekt och vattenverk"),
        None,
    )
    assert draft.status == "drafted"
    assert draft.subject == "3d-scanning hos er"
    assert "Aquasvea AB" in draft.body
    assert "VA-projekt" in draft.body
    assert "Norrpoint" in draft.body
    assert "OPENAI_API_KEY is not configured" in draft.detail


def test_metricop_template_signs_off_as_metricop() -> None:
    draft = OutreachWriter(Settings(openai_api_key=None)).write(
        Company(organization_number="5560000001", name="Aquasvea AB"),
        WebsiteProfile(url="https://aquasvea.se/", about_text="VA-projekt"),
        None,
        "metricop",
    )
    assert "Metricop" in draft.body
    assert "Norrpoint" not in draft.body
    assert "prismor" in draft.body.casefold()
    assert "3d-modell" not in draft.body.casefold()
    assert "LiDAR" not in draft.body


def test_norrpoint_prompt_is_the_official_file() -> None:
    prompt = system_prompt("norrpoint")
    assert prompt.startswith("You are an expert B2B cold-email writer")
    assert 'Return JSON only:' in prompt
    assert "Never include the subject in the body." in prompt
    assert "you MUST cite one real project name" in prompt
    assert '"customer_fit"' in prompt
    assert "Inclined Labs" in prompt
    assert "wind tunnels" in prompt
    assert "Jag såg att ni på {spoken name}" in prompt
    assert "without AB" in prompt
    assert "No about/project text extracted" in prompt
    assert "general measurement tasks" in prompt


def test_norrpoint_writer_sends_the_file_and_parses_fit() -> None:
    captured: list[httpx.Request] = []
    payload = {
        "subject": "norra tornen",
        "body": "Hej,\n\nNorra Tornen är ett befintligt hus.\n\nVänliga hälsningar,\nNorrpoint",
        "customer_fit": "moderate",
        "customer_fit_reason": "Named existing building, but no surveying or as-built work stated.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    writer = OutreachWriter(
        Settings(
            openai_api_key="test-key",
            openai_api_url="https://api.openai.com/v1/chat/completions",
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    draft = writer.write(
        Company(organization_number="5560000001", name="AB Projit"),
        WebsiteProfile(url="https://projit.se/", projects_text="Norra Tornen"),
        None,
        "norrpoint",
    )
    sent = json.loads(captured[0].content)
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0]["content"].startswith("You are an expert B2B cold-email writer")
    assert "Norra Tornen" in sent["messages"][1]["content"]
    assert draft.body == payload["body"]
    assert draft.subject == "norra tornen"
    assert draft.customer_fit == "moderate"


def test_metricop_system_prompt_is_accessories_not_software() -> None:
    prompt = system_prompt("metricop")
    assert "prismor" in prompt
    assert "compatibility" in prompt
    assert "field software" not in prompt.casefold()
    assert "customer_fit" in prompt


def test_spoken_company_name_strips_legal_form() -> None:
    assert spoken_company_name("Inclined Labs AB") == "Inclined Labs"
    assert spoken_company_name("AB Projit") == "Projit"
    assert spoken_company_name("Väg & Miljö") == "Väg & Miljö"


def test_writer_falls_back_to_template_when_openai_fails() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    writer = OutreachWriter(
        Settings(openai_api_key="test-key", openai_api_url="https://api.openai.com/v1/chat/completions"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    draft = writer.write(
        Company(organization_number="5560000001", name="Aquasvea AB"),
        WebsiteProfile(url="https://aquasvea.se/"),
        None,
    )
    assert draft.status == "drafted"
    assert "Hej Aquasvea AB" in draft.body
    assert draft.detail == "AI generation failed: OpenAI returned HTTP 500."


def test_writer_explains_rejected_openai_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    writer = OutreachWriter(
        Settings(openai_api_key="bad-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    draft = writer.write(
        Company(organization_number="5560000001", name="Aquasvea AB"),
        WebsiteProfile(url="https://aquasvea.se/"),
        None,
    )
    assert draft.subject == "3d-scanning hos er"
    assert draft.detail == (
        "AI generation failed: OpenAI rejected OPENAI_API_KEY (HTTP 401)."
    )
