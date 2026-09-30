from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from lead_finder.config import get_settings


class SniCode(BaseModel):
    code: str
    name: str
    why: str = ""


class SniGroup(BaseModel):
    id: str
    title: str
    description: str = ""
    codes: list[SniCode]


class SniCatalog(BaseModel):
    groups: list[SniGroup]

    def by_code(self) -> dict[str, SniCode]:
        return {item.code: item for group in self.groups for item in group.codes}

    def codes(self) -> list[str]:
        return [item.code for group in self.groups for item in group.codes]


@lru_cache
def load_sni_catalog(path: Path | None = None) -> SniCatalog:
    settings = get_settings()
    config_path = path or settings.sni_catalog_path
    with config_path.open(encoding="utf-8") as file:
        return SniCatalog.model_validate(yaml.safe_load(file))
