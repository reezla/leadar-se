import threading
import time

from lead_finder.models import Company, ScoredCompany, ScoreReason
from lead_finder.use_company_search import SearchResult, SearchSummary
from lead_finder.use_lead_job import clear_lead_job, request_stop, start_lead_job


def test_request_stop_is_visible_to_the_worker() -> None:
    started = threading.Event()

    def work(job) -> None:
        started.set()
        while not job.stop.is_set():
            time.sleep(0.01)
        with job.lock:
            job.phase = "done"
            job.summary = "Crawl stopped at 0 of 1."

    result = SearchResult(
        companies=[
            ScoredCompany(
                company=Company(organization_number="1", name="Akustikforum AB"),
                score=1,
                reasons=[ScoreReason(label="Relevant SNI", points=1)],
            )
        ],
        summary=SearchSummary(fetched=1, matched=1, incomplete=0),
    )
    job = start_lead_job("test-stop", result, ["1"], work=work)
    assert started.wait(1)
    request_stop("test-stop")
    deadline = time.time() + 2
    while time.time() < deadline and job.snapshot()["phase"] != "done":
        time.sleep(0.01)
    assert job.snapshot()["summary"] == "Crawl stopped at 0 of 1."
    clear_lead_job("test-stop")
