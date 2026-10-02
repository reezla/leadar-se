from __future__ import annotations

import httpx

from lead_finder.config import Settings
from lead_finder.models import Company, OutreachDraft, ProductMatch, WebsiteProfile
from lead_finder.outreach_parse import parse_openai_content
from lead_finder.outreach_sender import (
    offer_line,
    sender_label,
    system_prompt,
)


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
            except Exception:
                pass
        return template_draft(company, profile, match, sender)

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
        detail="template",
        suggested_recipient=profile.suggested_recipient,
        website=profile,
    )


def user_prompt(
    company: Company,
    profile: WebsiteProfile,
    match: ProductMatch | None,
    sender: str = "norrpoint",
    previous: str = "",
) -> str:
    job = ""
    if match is not None and match.job:
        job = match.job
    size = company.employee_class or "unknown size"
    sni = ", ".join(company.sni_codes) or "unknown SNI"
    about = (profile.about_text or "No about text extracted.")[:2_500]
    projects = (profile.projects_text or "No project text extracted.")[:2_500]
    spoken = spoken_company_name(company.name)
    text = (
        f"Sender: {sender_label(sender)}\n"
        f"Offer: {offer_line(sender)}\n"
        f"Company: {company.name}\n"
        f"Spoken name: {spoken}\n"
        f"Website: {profile.url}\n"
        f"SNI: {sni}\n"
        f"Size: {size}\n"
        f"Catalog job (optional context, do not force a SKU): {job or 'none'}\n\n"
        f'First sentence must start: "Jag såg att ni på {spoken} …" '
        "Do not include AB.\n"
        "Estimate customer_fit from About and Projects only. "
        "Empty or missing site text = weak. Do not infer measurement work. "
        "Do not trust SNI, company name, or catalog job.\n\n"
        f"About:\n{about}\n\n"
        f"Projects / references:\n{projects}\n"
    )
    if previous.strip():
        text += (
            "\nPrevious draft to replace. Write a different email from the same research. "
            "Do not copy its sentences.\n"
            f"{previous.strip()}\n"
        )
    return text


_LEGAL_SUFFIXES = (
    "aktiebolag",
    "handelsbolag",
    "kommanditbolag",
    "(publ)",
    "ab",
    "hb",
    "kb",
)


def spoken_company_name(name: str) -> str:
    text = " ".join(name.split()).rstrip(" ,.")
    lowered = text.casefold()
    if lowered.startswith("ab "):
        text = text[3:].strip()
    while True:
        lowered = text.casefold()
        for suffix in _LEGAL_SUFFIXES:
            token = f" {suffix}"
            if lowered.endswith(token):
                text = text[: -len(token)].rstrip(" ,.")
                break
        else:
            break
    return text or name


def _snippet(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    chunks = [" ".join(chunk.split()) for chunk in text.split("\n\n") if chunk.strip()]
    usable = [chunk for chunk in chunks if "current slide" not in chunk.casefold()]
    chosen = max(usable or chunks, key=len)
    if len(chosen) <= limit:
        return chosen
    return chosen[:limit].rsplit(" ", 1)[0] + "…"
