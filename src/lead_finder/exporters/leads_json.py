from __future__ import annotations

import json

from lead_finder.exporters.unique import unique_scored_companies
from lead_finder.models import ScoredCompany


def export_leads_json(companies: list[ScoredCompany]) -> str:
    records = unique_scored_companies(companies)
    payload = {
        "count": len(records),
        "companies": [item.model_dump(mode="json") for item in records],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
