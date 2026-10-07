from __future__ import annotations

import json
from collections.abc import Callable

from lead_finder.models import Company, ScoredCompany, WebsiteProfile

ProgressCallback = Callable[[int, int, str], None]


def store_crawl(
    scored: ScoredCompany,
    status: str,
    detail: str,
    done: int,
    total: int,
    on_progress: ProgressCallback | None,
    *,
    profile: WebsiteProfile | None,
    company: Company | None = None,
    notify: bool = True,
) -> tuple[ScoredCompany, dict[str, object]]:
    if notify:
        notify_progress(on_progress, done, total, f"{scored.company.name}: {detail or status}")
    stored_company = scored.company if company is None else company
    record = crawl_record(
        stored_company.name,
        profile,
        status=status,
        crawl_detail=detail,
    )
    return (
        scored.model_copy(
            update={
                "company": stored_company,
                "website": profile,
                "crawl_status": status,
                "crawl_detail": detail,
            }
        ),
        record,
    )


def crawl_record(
    company_name: str,
    profile: WebsiteProfile | None,
    *,
    status: str,
    crawl_detail: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "company": company_name,
        "crawl_status": status,
        "website": None if profile is None else profile.model_dump(mode="json"),
    }
    if crawl_detail:
        payload["crawl_detail"] = crawl_detail
    print(
        "Website crawl result:",
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        flush=True,
    )
    return payload


def notify_progress(
    on_progress: ProgressCallback | None,
    done: int,
    total: int,
    message: str,
) -> None:
    if on_progress is None:
        return
    on_progress(done, max(total, 1), message)
