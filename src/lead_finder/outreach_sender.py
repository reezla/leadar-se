from __future__ import annotations

from pathlib import Path

from lead_finder.config import get_settings

SENDERS = ("norrpoint", "metricop")


def normalize_sender(value: str | None) -> str:
    raw = (value or "norrpoint").strip().casefold()
    return raw if raw in SENDERS else "norrpoint"


def sender_label(value: str | None) -> str:
    return "Metricop" if normalize_sender(value) == "metricop" else "Norrpoint"


def email_shape() -> str:
    return (
        "Plain text. Blank line between each part. Under 90 words. "
        "Parts, in order: "
        "1) Hej, "
        "2) Observation: one sentence, one real fact from their site, their world. "
        "3) Job: one or two sentences on the practical friction that fact creates. No product. "
        "4) Offer: one sentence tying that job to the product. No feature list. "
        "5) Ask: one question they can answer in a line. Not a demo or a meeting. "
        "6) Vänliga hälsningar, then the brand on the next line. "
        "Subject: 2-4 lowercase words, specific, not a pitch. "
        "Also set customer_fit from the website text only. Empty site text "
        "is weak. Do not invent instrument or measurement work. "
        "customer_fit_reason: one short English sentence citing the site. "
        'Return JSON only: {"subject": "...", "body": "...", '
        '"customer_fit": "weak|moderate|strong", "customer_fit_reason": "..."}.'
    )


def system_prompt(sender: str, *, prompt_path: Path | None = None) -> str:
    if normalize_sender(sender) != "metricop":
        path = prompt_path or get_settings().norrpoint_prompt_path
        return path.read_text(encoding="utf-8").strip()
    shape = email_shape()
    return (
        "You write short Swedish B2B cold emails from Metricop. "
        "Metricop sells survey accessories, not software and not scanners: "
        "prismor, trefötter, monitoreringsfästen, kablar, batterier, SMR and lasertracker "
        "parts that fit the instruments they already use "
        "(Leica, Trimble, Topcon, Sokkia). "
        "Voice: practical, compatibility first, no hype. "
        "Observation from fält, totalstation, tunnel, bro, järnväg, industri, or monitorering. "
        "The ask is to send instrument model or article number so you can check fit. "
        "Do not pitch LiDAR or 3D-models. No invented SKUs. "
        "customer_fit is for survey accessories: strong if the site names "
        "totalstation, monitoring, or field survey; weak if the site is empty "
        "or shows no instrument work. Do not invent field work. "
        "Still write the email if fit is weak. "
        f"{shape}"
    )


def offer_line(sender: str) -> str:
    if normalize_sender(sender) == "metricop":
        return (
            "Metricop survey accessories: prismor, trefötter, monitorering, "
            "SMR and lasertracker parts compatible with existing instruments"
        )
    return "Norrpoint handheld LiDAR scanners with high precision"
