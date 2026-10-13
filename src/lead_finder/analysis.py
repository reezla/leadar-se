"""Post-crawl analysis: which Norrpoint scanner(s) to recommend to a crawled company.

Runs after the website crawl and before the email draft. With an OpenAI key the model
reads the site text against config/scanners.yaml; without one (or on failure) the
rules in config/jobs.yaml are applied to the same text.
"""

from __future__ import annotations

import json
import logging

import httpx

from lead_finder.config import Settings, get_settings
from lead_finder.matching import match_company
from lead_finder.matching_catalog import MatchingCatalog, load_matching_catalog
from lead_finder.models import CompanyAnalysis, ProductMatch, ProductPick, ScoredCompany
from lead_finder.outreach_parse import normalize_customer_fit
from lead_finder.outreach_prompt import spoken_company_name
from lead_finder.scanner_catalog import ScannerCatalog, load_scanner_catalog

logger = logging.getLogger(__name__)

BUYER_TYPES = ("performs_measurement", "orders_measurement", "not_relevant", "unknown")
BUYER_LABELS = {
    "performs_measurement": "Mäter själva",
    "orders_measurement": "Beställer mätning",
    "not_relevant": "Ej relevant",
    "unknown": "Okänt",
}
SCANNING_WORDS = (
    "laserskanning",
    "laserscanning",
    "3d-skanning",
    "3d-scanning",
    "punktmoln",
    "skanning",
    "scanning",
    "lidar",
)
TEXT_BUDGET = 3_000
MAX_ALTERNATIVES = 2

SYSTEM_PROMPT = """You analyze Swedish companies for Norrpoint, which sells FJD handheld and
mobile LiDAR scanners. Decide which scanner(s) Norrpoint should recommend to this company,
using ONLY the website text provided. SNI code and company name are weak hints, never evidence.

Return JSON only:
{"recommended_product": "<one name from the catalog, or null>",
 "alternatives": [{"product": "<catalog name>", "reason": "<short English reason>"}],
 "reason": "<one English sentence: why the main pick fits, citing the site>",
 "buyer_type": "performs_measurement | orders_measurement | not_relevant | unknown",
 "customer_fit": "weak | moderate | strong",
 "customer_fit_reason": "<one English sentence citing a fact from the site>",
 "already_scans": true | false,
 "evidence": ["<short quote copied verbatim from the site>", "..."],
 "outreach_angle": "<one Swedish sentence: the concrete measuring problem in their work>"}

Rules:
- Product names must be exactly one of: {names}.
- At most 2 alternatives, different from the main pick. Order by fit.
- buyer_type: performs_measurement = they measure, survey, scan, document or build on site
  themselves; orders_measurement = they manage projects, act for the client or design but buy
  measuring from others; not_relevant = nothing physical to document (software, holding,
  entertainment, retail, staffing).
- customer_fit strong = the site names surveying, as-built, scan-to-BIM, laser scanning,
  stockpile volumes, tunnels or 3D documentation; moderate = a real adjacent site job
  (earthworks, renovation of existing buildings, plants, roads) without 3D capture;
  weak = no site work named, or the text is empty.
- already_scans = the site says they already do laser scanning, point clouds or drone scanning.
  Then prefer a scanner that complements what they have (e.g. handheld for interiors and
  underground) and say so in reason.
- Small companies (under 5 employees) without heavy demands: prefer V4e or C1.
- If buyer_type is not_relevant or the text is empty, recommended_product may be null.
- evidence: up to 3 quotes, each under 120 characters, copied from the text. Never invent.
- outreach_angle: Swedish, plain, no product name, no hype. Base it on a named project or
  service from the text if one exists.

Scanner catalog:
{catalog}"""


class ProductAnalyzer:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
        scanners: ScannerCatalog | None = None,
        rules: MatchingCatalog | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.scanners = scanners or load_scanner_catalog()
        self.rules = rules or load_matching_catalog()
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def analyze(self, scored: ScoredCompany) -> CompanyAnalysis:
        text = site_text(scored)
        if not text:
            analysis = self._rules(scored, text)
            return analysis.model_copy(
                update={
                    "customer_fit": "weak",
                    "customer_fit_reason": "The crawl has no usable website text.",
                }
            )
        if not self.settings.openai_api_key:
            return self._rules(scored, text)
        try:
            return self._ai(scored, text)
        except Exception:
            logger.exception("Product analysis failed for %s", scored.company.name)
            return self._rules(scored, text)

    def _ai(self, scored: ScoredCompany, text: str) -> CompanyAnalysis:
        system = SYSTEM_PROMPT.replace("{names}", ", ".join(self.scanners.names())).replace(
            "{catalog}", self.scanners.prompt_text()
        )
        response = self.client.post(
            self.settings.openai_api_url,
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json={
                "model": self.settings.analysis_model or self.settings.openai_model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt(scored, text)},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return parse_analysis(content, self.scanners, text)

    def _rules(self, scored: ScoredCompany, text: str) -> CompanyAnalysis:
        match = match_company(scored.company, self.rules, extra_text=text)
        primary = self.scanners.canonical(match.primary)
        alternative = self.scanners.canonical(match.alternative)
        alternatives = []
        if alternative and alternative != primary:
            alternatives.append(ProductPick(product=alternative, reason="Rule alternative"))
        return CompanyAnalysis(
            recommended_product=primary,
            alternatives=alternatives,
            reason="; ".join(match.evidence),
            buyer_type="unknown",
            already_scans=mentions_scanning(text),
            evidence=match.evidence[:3],
            source="rules",
        )


def user_prompt(scored: ScoredCompany, text: str) -> str:
    company = scored.company
    return (
        f"Company: {spoken_company_name(company.name)}\n"
        f"Legal name: {company.name}\n"
        f"Website: {company.domain or ''}\n"
        f"SNI (weak hint): {', '.join(company.sni_codes) or 'unknown'}\n"
        f"Size: {company.employee_class or 'unknown'}\n"
        f"Municipality: {company.municipality or 'unknown'}\n\n"
        f"Website text:\n{text}\n"
    )


def site_text(scored: ScoredCompany) -> str:
    profile = scored.website
    if profile is None:
        return ""
    parts = []
    if profile.about_text and profile.about_text.strip():
        parts.append("About:\n" + profile.about_text.strip()[:TEXT_BUDGET])
    if profile.projects_text and profile.projects_text.strip():
        parts.append("Projects / references:\n" + profile.projects_text.strip()[:TEXT_BUDGET])
    return "\n\n".join(parts)


def mentions_scanning(text: str) -> bool:
    folded = text.casefold()
    return any(word in folded for word in SCANNING_WORDS)


def parse_analysis(content: str, scanners: ScannerCatalog, text: str = "") -> CompanyAnalysis:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Analysis is not a JSON object")
    primary = scanners.canonical(payload.get("recommended_product"))
    alternatives: list[ProductPick] = []
    for item in payload.get("alternatives") or []:
        name = scanners.canonical(item.get("product") if isinstance(item, dict) else item)
        if not name or name == primary or any(pick.product == name for pick in alternatives):
            continue
        reason = _line(item.get("reason")) if isinstance(item, dict) else ""
        alternatives.append(ProductPick(product=name, reason=reason))
    if primary is None and alternatives:
        primary = alternatives.pop(0).product
    buyer = str(payload.get("buyer_type") or "unknown").strip().casefold()
    folded = " ".join(text.split()).casefold()
    evidence = [
        quote
        for raw in payload.get("evidence") or []
        if (quote := _line(raw, 160)) and _quoted_from(quote, folded)
    ]
    return CompanyAnalysis(
        recommended_product=primary,
        alternatives=alternatives[:MAX_ALTERNATIVES],
        reason=_line(payload.get("reason")),
        buyer_type=buyer if buyer in BUYER_TYPES else "unknown",
        customer_fit=normalize_customer_fit(payload.get("customer_fit")),
        customer_fit_reason=_line(payload.get("customer_fit_reason")),
        already_scans=bool(payload.get("already_scans")),
        evidence=evidence[:3],
        outreach_angle=_line(payload.get("outreach_angle")),
        source="ai",
    )


def apply_analysis(scored: ScoredCompany, analysis: CompanyAnalysis) -> ScoredCompany:
    return scored.model_copy(
        update={"analysis": analysis, "product_match": match_from_analysis(analysis)}
    )


def match_from_analysis(analysis: CompanyAnalysis) -> ProductMatch:
    alternative = ", ".join(pick.product for pick in analysis.alternatives) or None
    confidence = {"strong": "high", "moderate": "medium"}.get(analysis.customer_fit, "low")
    evidence = [analysis.reason] if analysis.reason else []
    evidence.extend(f'"{quote}"' for quote in analysis.evidence)
    return ProductMatch(
        job=BUYER_LABELS.get(analysis.buyer_type, ""),
        brand="norrpoint" if analysis.recommended_product else "none",
        primary=analysis.recommended_product,
        alternative=alternative,
        confidence=confidence,
        evidence=evidence,
        status="matched" if analysis.recommended_product else "needs_review",
    )


def analyze_scored(scored: ScoredCompany, analyzer: ProductAnalyzer | None) -> ScoredCompany:
    """Analyze a freshly crawled company. Anything not crawled is returned unchanged."""
    if analyzer is None or scored.crawl_status != "crawled":
        return scored
    try:
        return apply_analysis(scored, analyzer.analyze(scored))
    except Exception:
        logger.exception("Could not analyze %s", scored.company.name)
        return scored


def _quoted_from(quote: str, folded_text: str) -> bool:
    """Keep only evidence the model actually copied from the site text."""
    if not folded_text:
        return True
    return " ".join(quote.rstrip("…").split()).casefold() in folded_text


def _line(value: object, limit: int = 300) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
