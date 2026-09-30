from __future__ import annotations

from collections.abc import MutableMapping

from lead_finder.sni_catalog import SniCatalog, SniCode

SNI_PREFIXES_KEY = "sni_prefixes"
SNI_SEGMENT_KEY = "sni_segment_key"


def parse_sni_prefixes(value: str) -> list[str]:
    prefixes: list[str] = []
    for raw in value.replace(";", ",").split(","):
        prefix = normalize_sni_prefix(raw)
        if prefix and prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def normalize_sni_prefix(value: str) -> str:
    return value.replace(".", "").strip()


def add_sni_prefix(selected: list[str], prefix: str) -> list[str]:
    normalized = normalize_sni_prefix(prefix)
    if not normalized or normalized in selected:
        return list(selected)
    return [*selected, normalized]


def remove_sni_prefix(selected: list[str], prefix: str) -> list[str]:
    normalized = normalize_sni_prefix(prefix)
    return [item for item in selected if item != normalized]


def format_sni_label(code: str, catalog: SniCatalog | dict[str, SniCode]) -> str:
    lookup = catalog.by_code() if isinstance(catalog, SniCatalog) else catalog
    item = lookup.get(code)
    if item is None:
        return code
    return f"{item.code} — {item.name}"


def sync_sni_selection(
    session: MutableMapping[str, object],
    *,
    segment_key: str,
    segment_prefixes: list[str],
) -> list[str]:
    current = session.get(SNI_PREFIXES_KEY)
    if session.get(SNI_SEGMENT_KEY) != segment_key or not isinstance(current, list):
        prefixes = list(segment_prefixes)
        session[SNI_PREFIXES_KEY] = prefixes
        session[SNI_SEGMENT_KEY] = segment_key
        return prefixes
    return list(current)
