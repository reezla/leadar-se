from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    scb_api_url: str = "https://api.scb.se/foretagsregistret/v1/foretag"
    scb_cert_path: Path | None = None
    scb_key_path: Path | None = None
    scb_cert_password: str | None = None
    scb_timeout_seconds: float = 30
    scb_page_size: int = 2_000
    scb_requests_per_window: int = 10
    scb_rate_limit_window_seconds: float = 10
    segments_path: Path = Path("config/segments.yaml")
    sni_catalog_path: Path = Path("config/sni_catalog.yaml")
    allabolag_base_url: str = "https://www.allabolag.se"
    allabolag_timeout_seconds: float = 30
    allabolag_requests_per_window: int = 4
    allabolag_rate_limit_window_seconds: float = 10
    allabolag_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )


class Segment(BaseModel):
    name: str
    description: str
    sni_prefixes: list[str]
    keywords: list[str] = Field(default_factory=list)
    weights: dict[str, int] = Field(default_factory=dict)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_segments(path: Path | None = None) -> dict[str, Segment]:
    settings = get_settings()
    config_path = path or settings.segments_path
    with config_path.open(encoding="utf-8") as file:
        raw_segments = yaml.safe_load(file)["segments"]
    return {key: Segment.model_validate(value) for key, value in raw_segments.items()}
