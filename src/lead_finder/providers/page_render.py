from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from queue import Queue
from typing import Protocol

logger = logging.getLogger(__name__)

_Job = tuple[str, Future[str | None]]


class PageRenderer(Protocol):
    def render(self, url: str) -> str | None:
        """Return the HTML after client-side scripts have run."""
        ...

    def close(self) -> None:
        """Stop the browser."""
        ...


class PlaywrightRenderer:
    """One Chromium, used from a single thread, for pages httpx cannot read."""

    def __init__(self, *, user_agent: str, timeout_seconds: float) -> None:
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._timeout_ms = max(1, int(timeout_seconds * 1000))
        self._queue: Queue[_Job | None] = Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()

    def render(self, url: str) -> str | None:
        self._ensure_started()
        future: Future[str | None] = Future()
        self._queue.put((url, future))
        try:
            return future.result(timeout=self._timeout_seconds + 15)
        except Exception:
            logger.warning("Render failed url=%s", url, exc_info=True)
            return None

    def close(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._queue.put(None)
        thread.join(timeout=self._timeout_seconds + 5)

    def _ensure_started(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="page-render", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        playwright, browser = _launch()
        try:
            while True:
                item = self._queue.get()
                if item is None:
                    return
                url, future = item
                if future.done():
                    continue
                try:
                    html = _read(browser, url, self._user_agent, self._timeout_ms)
                except Exception:
                    logger.warning("Could not render url=%s", url, exc_info=True)
                    html = None
                future.set_result(html)
        finally:
            try:
                if browser is not None:
                    browser.close()
            finally:
                if playwright is not None:
                    playwright.stop()


def _launch() -> tuple[object | None, object | None]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed; JavaScript sites stay unread")
        return None, None
    playwright = None
    try:
        playwright = sync_playwright().start()
        return playwright, playwright.chromium.launch(headless=True)
    except Exception:
        logger.warning("Chromium failed to start; JavaScript sites stay unread", exc_info=True)
        if playwright is not None:
            playwright.stop()
        return None, None


def _read(browser: object | None, url: str, user_agent: str, timeout_ms: int) -> str | None:
    if browser is None:
        return None
    context = browser.new_context(user_agent=user_agent, locale="sv-SE")
    try:
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_function(
                "() => (document.body && document.body.innerText || '').trim().length > 80",
                timeout=min(8_000, timeout_ms),
            )
        except Exception:
            logger.debug("Rendered page stayed thin url=%s", url)
        return str(page.content())
    finally:
        context.close()
