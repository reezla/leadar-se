from lead_finder.config import settings_from_secrets


def test_settings_from_secrets_reads_root_uppercase_keys() -> None:
    values = settings_from_secrets(
        {
            "OPENAI_API_KEY": "sk-cloud",
            "SCB_API_KEY": "scb-cloud",
            "UNRELATED_SECRET": "ignored",
        }
    )

    assert values == {
        "openai_api_key": "sk-cloud",
        "scb_api_key": "scb-cloud",
    }


def test_settings_from_secrets_accepts_field_names() -> None:
    values = settings_from_secrets(
        {
            "openai_api_key": "sk-lowercase",
            "openai_model": "gpt-4o-mini",
        }
    )

    assert values["openai_api_key"] == "sk-lowercase"
    assert values["openai_model"] == "gpt-4o-mini"
