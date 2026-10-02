from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    scb_api_url: str = "https://apiafr.scb.se"
    scb_api_key: str | None = None
    scb_timeout_seconds: float = 30
    scb_page_size: int = 2_000
    scb_requests_per_window: int = 10
    scb_rate_limit_window_seconds: float = 10
    segments_path: Path = Path("config/segments.yaml")
    sni_catalog_path: Path = Path("config/sni_catalog.yaml")
    products_path: Path = Path("config/products.yaml")
    jobs_path: Path = Path("config/jobs.yaml")
    norrpoint_prompt_path: Path = Path("write-email-norrpoint.md")
    allabolag_base_url: str = "https://www.allabolag.se"
    allabolag_timeout_seconds: float = 30
    allabolag_requests_per_window: int = 4
    allabolag_rate_limit_window_seconds: float = 10
    allabolag_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_api_url: str = "https://api.openai.com/v1/chat/completions"
    website_search_provider: str = "google"
    google_search_url: str = "https://www.google.com/search"
    duckduckgo_search_url: str = "https://html.duckduckgo.com/html/"
    google_search_timeout_seconds: float = 20
    google_requests_per_window: int = 4
    google_rate_limit_window_seconds: float = 10
    website_crawl_timeout_seconds: float = 20
    website_crawl_max_pages: int = 4
    website_crawl_requests_per_window: int = 4
    website_crawl_rate_limit_window_seconds: float = 10
    outreach_max_selected: int = 20


class Segment(BaseModel):
    name: str
    description: str
    sni_prefixes: list[str]
    keywords: list[str] = Field(default_factory=list)
    weights: dict[str, int] = Field(default_factory=dict)


@lru_cache
def get_settings() -> Settings:
    return Settings(**_streamlit_settings())


def _streamlit_settings() -> dict[str, Any]:
    try:
        import streamlit as st

        return settings_from_secrets(st.secrets)
    except Exception:
        return {}


def settings_from_secrets(secrets: Mapping[str, object]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_name in Settings.model_fields:
        for key in (field_name.upper(), field_name):
            if key in secrets:
                values[field_name] = secrets[key]
                break
    return values


def load_segments(path: Path | None = None) -> dict[str, Segment]:
    settings = get_settings()
    config_path = path or settings.segments_path
    with config_path.open(encoding="utf-8") as file:
        raw_segments = yaml.safe_load(file)["segments"]
    return {key: Segment.model_validate(value) for key, value in raw_segments.items()}
