from lead_finder.sni_resolve import (
    canonical_sni_prefix,
    expand_sni_prefixes,
    resolve_industry_codes,
)


def test_canonical_architect_code() -> None:
    assert canonical_sni_prefix("71111") == "71110"
    assert canonical_sni_prefix("71121") == "71121"


def test_resolve_maps_missing_71111_to_scb_71110() -> None:
    catalog = {"71110": "Arkitektverksamhet", "71121": "Byggteknik"}
    assert resolve_industry_codes(["71111"], catalog) == ["71110"]
    assert resolve_industry_codes(["71121"], catalog) == ["71121"]


def test_resolve_keeps_short_prefix_expansion() -> None:
    catalog = {"71121": "Byggteknik", "71122": "Industri"}
    assert resolve_industry_codes(["7112"], catalog) == ["71121", "71122"]


def test_expand_keeps_user_prefix_and_alias() -> None:
    catalog = {"71110": "Arkitektverksamhet"}
    assert expand_sni_prefixes(["71111"], catalog) == ["71111", "71110"]
