from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from lead_finder.config import get_settings


class ProductFamily(BaseModel):
    id: str
    brand: str
    name: str


class JobRule(BaseModel):
    id: str
    name: str
    brand: str
    priority: int
    sni_prefixes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    require_keywords: bool = False
    primary: str | None = None
    alternative: str | None = None
    employee_min: int | None = None
    employee_max: int | None = None
    sni_only_status: str = "matched"


class MatchingCatalog(BaseModel):
    families: dict[str, ProductFamily]
    jobs: list[JobRule]

    @model_validator(mode="after")
    def validate_family_refs(self) -> MatchingCatalog:
        for job in self.jobs:
            for family_id in (job.primary, job.alternative):
                if family_id and family_id not in self.families:
                    raise ValueError(f"Job {job.id} references unknown family {family_id}")
        return self

    def family_name(self, family_id: str | None) -> str | None:
        if family_id is None:
            return None
        return self.families[family_id].name


@lru_cache
def load_matching_catalog(
    products_path: Path | None = None,
    jobs_path: Path | None = None,
) -> MatchingCatalog:
    settings = get_settings()
    with (products_path or settings.products_path).open(encoding="utf-8") as file:
        families_raw = yaml.safe_load(file)["families"]
    with (jobs_path or settings.jobs_path).open(encoding="utf-8") as file:
        jobs_raw = yaml.safe_load(file)["jobs"]
    families = {
        family_id: ProductFamily(id=family_id, **payload)
        for family_id, payload in families_raw.items()
    }
    jobs = [JobRule.model_validate(item) for item in jobs_raw]
    return MatchingCatalog(families=families, jobs=sorted(jobs, key=lambda job: job.priority))
