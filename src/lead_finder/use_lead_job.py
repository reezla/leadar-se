from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from lead_finder.config import get_settings
from lead_finder.providers.website_crawl import WebsiteCrawler
from lead_finder.providers.website_search import build_website_finder
from lead_finder.use_company_search import SearchResult
from lead_finder.use_lead_crawl import generate_leads
from lead_finder.use_lead_queue import finished_orgs

logger = logging.getLogger(__name__)

Work = Callable[["LeadJob"], None]


@dataclass
class LeadJob:
    result: SearchResult
    pending: list[str]
    total: int
    stop: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    phase: str = "running"
    done: int = 0
    message: str = "Starting crawl..."
    summary: str = ""
    stopped: bool = False
    error: str = ""
    records: list[dict[str, object]] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    delivered: int = 0
    client: httpx.Client | None = None

    def add_notice(self, message: str) -> None:
        with self.lock:
            if message not in self.notices:
                self.notices.append(message)

    def pull_notices(self) -> list[str]:
        with self.lock:
            fresh = self.notices[self.delivered :]
            self.delivered = len(self.notices)
            return fresh

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            return {
                "phase": self.phase,
                "done": self.done,
                "total": self.total,
                "message": self.message,
                "summary": self.summary,
                "stopped": self.stopped,
                "error": self.error,
                "result": self.result,
                "records": list(self.records),
            }


_jobs: dict[str, LeadJob] = {}


def get_lead_job(session_key: str) -> LeadJob | None:
    return _jobs.get(session_key)


def clear_lead_job(session_key: str) -> None:
    _jobs.pop(session_key, None)


def request_stop(session_key: str) -> None:
    job = _jobs.get(session_key)
    if job is None:
        return
    job.stop.set()
    client = job.client
    if client is not None:
        client.close()


def start_lead_job(
    session_key: str,
    result: SearchResult,
    pending: list[str],
    *,
    work: Work | None = None,
) -> LeadJob:
    job = LeadJob(result=result, pending=list(pending), total=len(pending))
    _jobs[session_key] = job
    thread = threading.Thread(
        target=work or _crawl_pending,
        args=(job,),
        name=f"lead-crawl-{session_key}",
        daemon=True,
    )
    thread.start()
    return job


def _crawl_pending(job: LeadJob) -> None:
    settings = get_settings()
    finder = build_website_finder(settings)
    crawler = WebsiteCrawler(settings, client=finder.client)
    job.client = finder.client
    done = 0
    result = job.result
    try:
        for org in job.pending:
            if job.stop.is_set():
                break
            batch = generate_leads(
                result,
                [org],
                settings=settings,
                finder=finder,
                crawler=crawler,
                on_progress=lambda _done, _total, message: _set_message(job, message),
                on_notice=job.add_notice,
                should_stop=job.stop.is_set,
            )
            result = batch.result
            if finished_orgs(result.companies, [org]):
                done += 1
            with job.lock:
                job.result = result
                job.done = done
                job.records = [*job.records, *batch.records]
            if batch.stopped or job.stop.is_set():
                with job.lock:
                    job.stopped = batch.stopped and not job.stop.is_set()
                break
        _finish(job, done)
    except Exception as error:
        if job.stop.is_set():
            _finish(job, done)
            return
        logger.exception("Lead crawl failed")
        job.add_notice(f"Lead crawl failed: {error}")
        with job.lock:
            job.error = str(error)
            job.phase = "done"
    finally:
        finder.close()
        job.client = None


def _set_message(job: LeadJob, message: str) -> None:
    with job.lock:
        job.message = message


def _finish(job: LeadJob, done: int) -> None:
    with job.lock:
        job.done = done
        job.phase = "done"
        if job.stop.is_set():
            job.summary = f"Crawl stopped at {done} of {job.total}."
        elif job.stopped:
            job.summary = f"Crawl stopped after {done} of {job.total}."
        else:
            job.summary = f"Crawled {done} of {job.total}."
