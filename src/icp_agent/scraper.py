"""Apify LinkedIn scraper wrapper.

Calls the actor in batches and tolerates per-profile failures: bad URLs are
returned with `error=...` so the rule engine can still produce a decision.
"""

from __future__ import annotations

from typing import Any, Protocol

from apify_client import ApifyClient

from .log import get_logger
from .models import ProfileRecord
from .parse import normalize_profile

log = get_logger(__name__)


class ProfileScraper(Protocol):
    def scrape(self, urls: list[str]) -> dict[str, ProfileRecord]: ...


class ApifyLinkedInScraper:
    """Synchronous Apify-backed scraper. One run per batch of `batch_size` URLs."""

    def __init__(
        self,
        token: str,
        actor_id: str = "2SyF0bVxmgGr8IVCZ",
        batch_size: int = 25,
    ) -> None:
        if not token:
            raise RuntimeError("APIFY_TOKEN is not set.")
        self._client = ApifyClient(token)
        self._actor_id = actor_id
        self._batch_size = max(1, batch_size)

    def scrape(self, urls: list[str]) -> dict[str, ProfileRecord]:
        """Return a dict keyed by input URL. Missing profiles get an error sentinel."""
        url_to_record: dict[str, ProfileRecord] = {}
        if not urls:
            return url_to_record

        for batch_start in range(0, len(urls), self._batch_size):
            batch = urls[batch_start : batch_start + self._batch_size]
            log.info(
                "scraper.batch.start",
                batch_index=batch_start // self._batch_size,
                size=len(batch),
            )
            try:
                items = self._run_actor(batch)
            except Exception as e:  # noqa: BLE001 - we want to keep the run alive
                log.error("scraper.batch.failed", error=str(e), size=len(batch))
                for url in batch:
                    url_to_record[url] = ProfileRecord(error=f"actor_call_failed: {e}", raw={})
                continue

            matched = self._match_items_to_urls(batch, items)
            for url in batch:
                raw = matched.get(url)
                if raw is None:
                    url_to_record[url] = ProfileRecord(error="no_profile_returned", raw={})
                else:
                    url_to_record[url] = normalize_profile(raw)
            log.info(
                "scraper.batch.done",
                size=len(batch),
                matched=sum(1 for r in url_to_record.values() if not r.error),
            )

        return url_to_record

    def _run_actor(self, batch: list[str]) -> list[dict[str, Any]]:
        run_input = {"profileUrls": batch}
        run = self._client.actor(self._actor_id).call(run_input=run_input)
        if not run or not run.get("defaultDatasetId"):
            return []
        dataset = self._client.dataset(run["defaultDatasetId"])
        items = list(dataset.iterate_items())
        return items

    @staticmethod
    def _match_items_to_urls(
        batch: list[str],
        items: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Match Apify result items back to input URLs by normalized identifier."""
        by_handle: dict[str, dict[str, Any]] = {}
        for item in items:
            handle = _profile_handle(item.get("linkedinUrl") or item.get("url") or item.get("profileUrl") or "")
            if handle:
                by_handle[handle] = item
        out: dict[str, dict[str, Any]] = {}
        leftover = list(items)
        for url in batch:
            handle = _profile_handle(url)
            if handle and handle in by_handle:
                out[url] = by_handle[handle]
            elif leftover:
                # best-effort fallback: positional pop
                out[url] = leftover.pop(0)
        return out


def _profile_handle(url: str) -> str:
    """Extract the LinkedIn vanity slug from a URL, lowercased."""
    if not url:
        return ""
    cleaned = url.strip().rstrip("/")
    marker = "/in/"
    idx = cleaned.lower().find(marker)
    if idx < 0:
        return ""
    return cleaned[idx + len(marker) :].split("/")[0].split("?")[0].lower()
