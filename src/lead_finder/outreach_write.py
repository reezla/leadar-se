from __future__ import annotations

import logging

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, OutreachDraft, ProductMatch, WebsiteProfile
from lead_finder.outreach_parse import parse_openai_content
from lead_finder.outreach_prompt import user_prompt
from lead_finder.outreach_sender import sender_label, system_prompt

logger = logging.getLogger(__name__)


class OutreachWriter:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=45, follow_redirects=True)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def write(
        self,
        company: Company,
        profile: WebsiteProfile,
        match: ProductMatch | None,
        sender: str = "norrpoint",
        previous: str = "",
    ) -> OutreachDraft:
        if self.settings.openai_api_key:
            try:
                return self._openai_write(company, profile, match, sender, previous)
            except Exception as error:
                logger.exception("OpenAI outreach generation failed for %s", company.name)
                return template_draft(
                    company,
                    profile,
                    match,
                    sender,
                    detail=openai_error_detail(error),
                )
        return template_draft(
            company,
            profile,
            match,
            sender,
            detail="AI generation unavailable: OPENAI_API_KEY is not configured.",
        )

    def _openai_write(
        self,
        company: Company,
        profile: WebsiteProfile,
        match: ProductMatch | None,
        sender: str,
        previous: str = "",
    ) -> OutreachDraft:
        request: dict[str, object] = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt(sender)},
                {
                    "role": "user",
                    "content": user_prompt(
                        company, profile, match, sender, previous=previous
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        if previous:
            request["temperature"] = 0.9
        response = self.client.post(
            self.settings.openai_api_url,
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json=request,
        )
        response.raise_for_status()
        subject, body, fit, reason = parse_openai_content(
            response.json()["choices"][0]["message"]["content"]
        )
        return OutreachDraft(
            subject=subject,
            body=body,
            status="drafted",
            suggested_recipient=profile.suggested_recipient,
            website=profile,
            customer_fit=fit,
            customer_fit_reason=reason,
        )


def template_draft(
    company: Company,
    profile: WebsiteProfile,
    match: ProductMatch | None,
    sender: str = "norrpoint",
    *,
    detail: str = "template",
) -> OutreachDraft:
    brand = sender_label(sender)
    snippet = _snippet(profile.about_text or profile.projects_text)
    observed = f"{snippet}\n\n" if snippet else ""
    if sender_label(sender) == "Metricop":
        subject = "fältillbehör"
        job = (
            "När uppställningen redan är totalstation eller monitorering "
            "är det fäste och offset som avgör."
        )
        offer = (
            "Metricop tar fram prismor, fästen och SMR "
            "som passar instrumenten ni redan använder."
        )
        ask = "Skicka modell eller artikelnummer så kollar vi passform."
    else:
        subject = "3d-scanning hos er"
        job = "På den sortens hus tar trånga utrymmen tid med stativ."
        offer = "Norrpoints handhållna LiDAR är till för just det, med hög precision."
        ask = "Vore det värt att jämföra mot hur ni mäter inomhus idag?"
    body = (
        f"Hej {company.name},\n\n"
        f"{observed}"
        f"{job}\n\n"
        f"{offer}\n\n"
        f"{ask}\n\n"
        f"Vänliga hälsningar\n{brand}"
    )
    return OutreachDraft(
        subject=subject,
        body=body,
        status="drafted",
        detail=detail,
        suggested_recipient=profile.suggested_recipient,
        website=profile,
    )


def openai_error_detail(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 401:
            return "AI generation failed: OpenAI rejected OPENAI_API_KEY (HTTP 401)."
        if status == 403:
            return "AI generation failed: OpenAI denied model or account access (HTTP 403)."
        if status == 429:
            return "AI generation failed: OpenAI rate limit or quota exceeded (HTTP 429)."
        return f"AI generation failed: OpenAI returned HTTP {status}."
    if isinstance(error, httpx.RequestError):
        return "AI generation failed: could not connect to OpenAI."
    return "AI generation failed: OpenAI returned an invalid response."


def _snippet(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    chunks = [" ".join(chunk.split()) for chunk in text.split("\n\n") if chunk.strip()]
    usable = [chunk for chunk in chunks if "current slide" not in chunk.casefold()]
    chosen = max(usable or chunks, key=len)
    if len(chosen) <= limit:
        return chosen
    return chosen[:limit].rsplit(" ", 1)[0] + "…"
