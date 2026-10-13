from __future__ import annotations

from lead_finder.models import ScoredCompany
from lead_finder.use_company_search import SearchResult

DONE_STATUSES = {"crawled", "crawl_failed", "no_website"}
FINISHED_STATUSES = DONE_STATUSES | {"search_failed"}
SECONDS_PER_COMPANY = 20


def companies_to_crawl(result: SearchResult, org_numbers: list[str]) -> list[str]:
    known = {item.company.organization_number for item in result.companies}
    return [org for org in dict.fromkeys(org_numbers) if org in known]


def take_batch(pending: list[str], size: int) -> tuple[list[str], list[str]]:
    return pending[:size], pending[size:]


def finished_orgs(companies: list[ScoredCompany], org_numbers: list[str]) -> list[str]:
    by_org = {item.company.organization_number: item for item in companies}
    return [org for org in org_numbers if by_org[org].crawl_status in FINISHED_STATUSES]


def estimate_crawl_seconds(
    count: int,
    *,
    batch_size: int,
    pause_seconds: int,
    seconds_per_company: int = SECONDS_PER_COMPANY,
    concurrency: int = 5,
) -> int:
    if count <= 0 or batch_size <= 0:
        return 0
    workers = max(1, concurrency)
    waves = (count + workers - 1) // workers
    batches = (count + batch_size - 1) // batch_size
    return waves * seconds_per_company + max(0, batches - 1) * pause_seconds


def lead_success_message(
    records: list[dict[str, object]],
    *,
    total: int,
    summary: str,
    error: str,
) -> str | None:
    if error or not summary.startswith("Crawled ") or total <= 0:
        return None
    crawled = sum(1 for record in records if record.get("crawl_status") == "crawled")
    if crawled <= 0:
        return None
    if crawled == total:
        noun = "company" if crawled == 1 else "companies"
        return f"Leads generated for {crawled} {noun}."
    return f"Leads generated for {crawled} of {total} companies."


def format_crawl_estimate(seconds: int) -> str:
    minutes = max(1, round(seconds / 60)) if seconds else 1
    if minutes < 60:
        return f"about {minutes} min"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"about {hours} h"
    return f"about {hours} h {rest} min"


def after_batch(
    pending: list[str],
    batch_orgs: list[str],
    finished: list[str],
    *,
    done: int,
    stopped: bool,
) -> tuple[list[str], int, str]:
    new_done = done + len(finished)
    if stopped:
        return [], new_done, "idle"
    finished_set = set(finished)
    retry = [org for org in batch_orgs if org not in finished_set]
    rest = [org for org in pending if org not in batch_orgs]
    new_pending = retry + rest
    phase = "idle" if not new_pending else "wait"
    return new_pending, new_done, phase
