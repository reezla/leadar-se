from __future__ import annotations

from lead_finder.models import Company, ProductMatch, WebsiteProfile
from lead_finder.outreach_sender import offer_line, sender_label

_LEGAL_SUFFIXES = (
    "aktiebolag",
    "handelsbolag",
    "kommanditbolag",
    "(publ)",
    "ab",
    "hb",
    "kb",
)


def user_prompt(
    company: Company,
    profile: WebsiteProfile,
    match: ProductMatch | None,
    sender: str = "norrpoint",
    previous: str = "",
) -> str:
    job = match.job if match is not None and match.job else ""
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


def spoken_company_name(name: str) -> str:
    text = " ".join(name.split()).rstrip(" ,.")
    if text.casefold().startswith("ab "):
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
