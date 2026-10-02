from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lead_finder.models import Company

# Ranges published by GET /v1/kodtabeller/anstklkoder.
EMPLOYEE_CLASSES: dict[str, tuple[str, int | None, int | None]] = {
    "0": ("Uppgift saknas", None, None),
    "1": ("0 anställda", 0, 0),
    "2": ("1-4 anställda", 1, 4),
    "3": ("5-9 anställda", 5, 9),
    "4": ("10-19 anställda", 10, 19),
    "5": ("20-49 anställda", 20, 49),
    "6": ("50-99 anställda", 50, 99),
    "7": ("100-199 anställda", 100, 199),
    "8": ("200-499 anställda", 200, 499),
    "9": ("500-999 anställda", 500, 999),
    "10": ("1000-1499 anställda", 1000, 1499),
    "11": ("1500-1999 anställda", 1500, 1999),
    "12": ("2000-2999 anställda", 2000, 2999),
    "13": ("3000-3999 anställda", 3000, 3999),
    "14": ("4000-4999 anställda", 4000, 4999),
    "15": ("5000-9999 anställda", 5000, 9999),
    "16": ("10000- anställda", 10000, None),
}


def normalize_company(
    record: Mapping[str, Any],
    *,
    counties: Mapping[str, str],
    municipalities: Mapping[str, str],
) -> Company:
    organization_number = _text(record.get("orgNr")) or _text(record.get("peOrgNr"))
    name = _text(record.get("namn"))
    if not organization_number or not name:
        raise ValueError("SCB record is missing organization number or company name")

    employee_class, employee_min, employee_max = _employees(record.get("anstKl"))
    return Company(
        organization_number=organization_number,
        name=name,
        sni_codes=_sni_codes(record),
        municipality=_label(municipalities, record.get("kommunSate")),
        county=_label(counties, record.get("lanSate")),
        postal_address=_address(record.get("postAdress")),
        employee_class=employee_class,
        employee_min=employee_min,
        employee_max=employee_max,
        active=_active(record.get("ftgStat")),
    )


def _sni_codes(record: Mapping[str, Any]) -> list[str]:
    primary = record.get("primarNaringsgren")
    if isinstance(primary, Mapping):
        code = _text(primary.get("naringsgren"))
        return [code] if code else []
    code = _text(primary)
    return [code] if code else []


def _employees(value: Any) -> tuple[str | None, int | None, int | None]:
    if value in (None, ""):
        return None, None, None
    known = EMPLOYEE_CLASSES.get(str(value))
    if known is None:
        return str(value), None, None
    return known


def _active(value: Any) -> bool:
    if value in (None, ""):
        return True
    return str(value) == "1"


def _label(table: Mapping[str, str], value: Any) -> str | None:
    if value in (None, ""):
        return None
    return table.get(str(value), str(value))


def _address(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if not isinstance(value, Mapping):
        return None
    street = _text(value.get("gatuAdress"))
    postal_code = _text(value.get("postNr"))
    city = _text(value.get("postOrt"))
    locality = " ".join(part for part in (postal_code, city) if part)
    parts = [part for part in (street, locality) if part]
    return ", ".join(parts) or None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
