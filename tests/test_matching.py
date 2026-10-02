from lead_finder.matching import match_company
from lead_finder.models import Company


def test_property_manager_maps_to_c1() -> None:
    match = match_company(_company(sni_codes=["68201"], name="Bostadsförvaltning AB"))
    assert match.status == "matched"
    assert match.brand == "norrpoint"
    assert match.primary == "C1"
    assert match.confidence == "low"


def test_tunnel_contractor_maps_to_s2() -> None:
    match = match_company(_company(sni_codes=["42130"], name="Tunnel Entreprenad AB"))
    assert match.primary == "S2"
    assert match.alternative == "T1"
    assert match.job == "Tunnel, under jord och gruva"


def test_forestry_maps_to_s1() -> None:
    match = match_company(_company(sni_codes=["02409"], name="Skogsservice AB"))
    assert match.primary == "S1"


def test_surveyor_without_job_signals_needs_review() -> None:
    match = match_company(_company(sni_codes=["71121"], name="VBK Konsulterande ingenjörer AB"))
    assert match.status == "needs_review"
    assert match.brand == "none"
    assert match.primary is None
    assert match.job == "Allmän mätning"


def test_surveyor_with_bim_maps_to_p2() -> None:
    match = match_company(
        _company(
            sni_codes=["71121"],
            name="Nordisk Mätteknik AB",
            activity_description="Scan-to-BIM och punktmoln",
        )
    )
    assert match.status == "matched"
    assert match.primary == "P2"
    assert match.confidence == "high"


def test_energy_consultant_without_thermal_maps_to_p2() -> None:
    match = match_company(_company(sni_codes=["71124"], name="Energi & VVS AB"))
    assert match.primary == "P2"
    assert match.alternative == "P2 Vision+"


def test_thermal_keywords_map_to_p2_vision() -> None:
    match = match_company(
        _company(
            sni_codes=["71124"],
            name="Energi & VVS AB",
            activity_description="Termografi och energideklaration",
        )
    )
    assert match.primary == "P2 Vision+"
    assert match.confidence == "high"


def test_architect_71110_maps_to_c1() -> None:
    match = match_company(_company(sni_codes=["71110"], name="White arkitekter Aktiebolag"))
    assert match.status == "matched"
    assert match.primary == "C1"


def test_secondary_sni_does_not_pick_product() -> None:
    match = match_company(
        _company(
            sni_codes=["56222", "71121", "42110", "68201"],
            name="Arboga kommunalteknik AB",
        )
    )
    assert match.primary is None
    assert match.status == "needs_review"


def test_matkonsult_name_maps_to_s1_and_metricop() -> None:
    match = match_company(_company(sni_codes=["71121"], name="Clinton Mätkonsult Aktiebolag"))
    assert match.status == "matched"
    assert match.brand == "norrpoint; metricop"
    assert match.primary == "S1"
    assert match.alternative == "Metricop fält"
    assert "Metricop fält" in "; ".join(match.evidence)


def test_leica_signal_routes_to_metricop() -> None:
    match = match_company(_company(sni_codes=["71121"], name="Leica Mätcenter AB"))
    assert match.status == "matched"
    assert match.brand == "norrpoint; metricop"
    assert match.primary == "S1"
    assert match.alternative == "Metricop fält"


def test_instrument_brand_without_survey_name_is_metricop() -> None:
    match = match_company(_company(sni_codes=["71121"], name="Trimble Partner AB"))
    assert match.status == "matched"
    assert match.brand == "metricop"
    assert match.primary == "Metricop fält"


def _company(
    *,
    sni_codes: list[str],
    name: str,
    activity_description: str | None = None,
    employee_min: int | None = None,
    employee_max: int | None = None,
) -> Company:
    return Company(
        organization_number="556123-4567",
        name=name,
        sni_codes=sni_codes,
        activity_description=activity_description,
        employee_min=employee_min,
        employee_max=employee_max,
    )
