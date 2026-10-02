from __future__ import annotations

from collections.abc import Mapping

# Catalog/SNI-2007 mixup: 71.11 Arkitektverksamhet is detaljgrupp 71.110.
SNI_CANONICAL = {"71111": "71110"}


def canonical_sni_prefix(prefix: str) -> str:
    return SNI_CANONICAL.get(prefix, prefix)


def resolve_industry_codes(
    prefixes: list[str],
    catalog: Mapping[str, str] | None = None,
) -> list[str]:
    table = catalog or {}
    codes: list[str] = []
    for prefix in prefixes:
        codes.extend(_resolve_prefix(prefix, table))
    return list(dict.fromkeys(codes))


def expand_sni_prefixes(
    prefixes: list[str],
    catalog: Mapping[str, str] | None = None,
) -> list[str]:
    return list(dict.fromkeys([*prefixes, *resolve_industry_codes(prefixes, catalog)]))


def _resolve_prefix(prefix: str, catalog: Mapping[str, str]) -> list[str]:
    if len(prefix) != 5:
        matches = [code for code in catalog if code.startswith(prefix)]
        return matches or [prefix]
    if prefix in catalog:
        return [prefix]
    aliases = [SNI_CANONICAL[prefix]] if prefix in SNI_CANONICAL else []
    if catalog:
        aliases = [code for code in aliases if code in catalog]
        padded = f"{prefix[:4]}0"
        if padded in catalog and padded not in aliases:
            aliases.append(padded)
        if aliases:
            return aliases
        siblings = [code for code in catalog if code.startswith(prefix[:4])]
        return siblings or [prefix]
    return aliases or [prefix]
