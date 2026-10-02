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
    limit: int | None = Field(default=500, ge=1, le=10_000)

    def reached(self, count: int) -> bool:
        return self.limit is not None and count >= self.limit


class ScoreReason(BaseModel):
    label: str
    points: int


class ProductMatch(BaseModel):
    job: str | None = None
    brand: str = "none"
    primary: str | None = None
    alternative: str | None = None
    confidence: str = "low"
    evidence: list[str] = Field(default_factory=list)
    status: str = "needs_review"


class WebsiteProfile(BaseModel):
    url: str
    about_text: str | None = None
    projects_text: str | None = None
    pages_fetched: list[str] = Field(default_factory=list)
    source: str = "google"
    suggested_recipient: str | None = None


class OutreachDraft(BaseModel):
    subject: str = ""
    body: str = ""
    status: str = "needs_review"
    detail: str = ""
    suggested_recipient: str | None = None
    website: WebsiteProfile | None = None
    customer_fit: str = ""
    customer_fit_reason: str = ""

    @field_validator("website", mode="before")
    @classmethod
    def _coerce_website(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        dump = getattr(value, "model_dump", None)
        if callable(dump):
            return dump(mode="json")
        return value


class ScoredCompany(BaseModel):
    company: Company
    score: int
    reasons: list[ScoreReason]
    missing_data: list[str] = Field(default_factory=list)
    product_match: ProductMatch | None = None
    outreach: OutreachDraft | None = None
