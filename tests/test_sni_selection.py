from lead_finder.sni_catalog import load_sni_catalog
from lead_finder.use_sni_selection import (
    add_sni_prefix,
    format_sni_label,
    parse_sni_prefixes,
    remove_sni_prefix,
    sync_sni_selection,
)


def test_parse_and_toggle_sni_prefixes() -> None:
    assert parse_sni_prefixes("71.121, 71122; 71121") == ["71121", "71122"]
    assert parse_sni_prefixes("71111") == ["71110"]
    assert add_sni_prefix(["71121"], "71122") == ["71121", "71122"]
    assert add_sni_prefix(["71121"], "71121") == ["71121"]
    assert add_sni_prefix([], "71111") == ["71110"]
    assert remove_sni_prefix(["71121", "71122"], "71121") == ["71122"]


def test_sni_labels_and_segment_sync() -> None:
    catalog = load_sni_catalog()
    assert format_sni_label("71121", catalog).startswith("71121 —")
    assert "Arkitektverksamhet" in format_sni_label("71110", catalog)
    assert format_sni_label("71111", catalog).startswith("71110 —")
    assert format_sni_label("99999", catalog) == "99999"

    session: dict[str, object] = {}
    first = sync_sni_selection(
        session, segment_key="surveying", segment_prefixes=["7112"]
    )
    second = sync_sni_selection(
        session, segment_key="surveying", segment_prefixes=["7112"]
    )
    changed = sync_sni_selection(
        session, segment_key="mining", segment_prefixes=["08"]
    )

    assert first == []
    assert second == []
    assert changed == ["08"]
