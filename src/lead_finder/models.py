from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class Company(BaseModel):
    organization_number: str
    name: str
    workplace_name: str | None = None
    sni_codes: list[str] = Field(default_factory=list)
    activity_description: str | None = None
    municipality: str | None = None
    county: str | None = None
    postal_address: str | None = None
    employee_class: str | None = None
    employee_min: int | None = None
    employee_max: int | None = None
    revenue_class: str | None = None
    revenue_min_sek: int | None = None
    revenue_max_sek: int | None = None
    active: bool = True
    domain: str | None = None
    source: str = "SCB Företagsregistret"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("organization_number")
    @classmethod
    def normalize_organization_number(cls, value: str) -> str:
        return "".join(character for character in value if character.isdigit())

    @field_validator("sni_codes")
    @classmethod
    def normalize_sni_codes(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.replace(".", "").strip() for value in values if value))


class CompanySearchFilters(BaseModel):
    sni_prefixes: list[str] = Field(default_factory=list)
    counties: list[str] = Field(default_factory=list)
    municipalities: list[str] = Field(default_factory=list)
    employee_min: int | None = None
    employee_max: int | None = None
    revenue_min_sek: int | None = None
    revenue_max_sek: int | None = None
    active_only: bool = True
    text_query: str | None = None
    limit: int = Field(default=500, ge=1, le=10_000)


class ScoreReason(BaseModel):
    label: str
    points: int


class ScoredCompany(BaseModel):
    company: Company
    score: int
    reasons: list[ScoreReason]
    missing_data: list[str] = Field(default_factory=list)
