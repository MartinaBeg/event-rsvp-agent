"""Orchestrates: read xlsx → batch-scrape → classify → cap pass → write xlsx."""

from __future__ import annotations

import time
from collections import Counter

from .config import Settings, load_settings
from .excel import ExcelClient, WorkbookClient
from .log import get_logger
from .models import Decision, ProfileRecord, RsvpRow
from .rules import apply_cap_pass, classify
from .scraper import ApifyLinkedInScraper, ProfileScraper

log = get_logger(__name__)


def run(
    settings: Settings | None = None,
    workbook: WorkbookClient | None = None,
    scraper: ProfileScraper | None = None,
) -> dict[str, int]:
    """Run one full pass. Returns a counter dict for callers/tests."""
    settings = settings or load_settings()
    if workbook is None:
        workbook = ExcelClient(
            file_path=settings.resolved_excel_path(),
            tab_name=settings.excel_tab,
        )
    if scraper is None:
        scraper = ApifyLinkedInScraper(
            token=settings.apify_token,
            actor_id=settings.apify_actor_id,
            batch_size=settings.apify_batch_size,
        )

    started = time.perf_counter()
    rows = workbook.read_unprocessed()
    if not rows:
        log.info("pipeline.complete", rows=0, approved=0, waitlisted=0, rejected=0, duration_ms=0)
        return {"rows": 0, "approved": 0, "waitlisted": 0, "rejected": 0}

    urls = sorted({r.linkedin_url for r in rows if r.linkedin_url})
    profiles_by_url: dict[str, ProfileRecord] = scraper.scrape(urls)

    raw_decisions: list[Decision] = []
    for row in rows:
        profile = profiles_by_url.get(
            row.linkedin_url,
            ProfileRecord(error="profile_not_returned", raw={}),
        )
        raw_decisions.append(classify(row, profile))

    final = apply_cap_pass(raw_decisions, cap=settings.approval_cap)

    if settings.dry_run:
        log.info("pipeline.dry_run", count=len(final))
    else:
        workbook.write_decisions(final)

    summary = _summarize(final)
    duration_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "pipeline.complete",
        rows=summary["rows"],
        approved=summary["approved"],
        waitlisted=summary["waitlisted"],
        rejected=summary["rejected"],
        duration_ms=duration_ms,
    )
    return summary


def _summarize(decisions: list[Decision]) -> dict[str, int]:
    counter = Counter(d.decision for d in decisions)
    return {
        "rows": len(decisions),
        "approved": int(counter.get("Approve", 0)),
        "waitlisted": int(counter.get("Waitlist", 0)),
        "rejected": int(counter.get("Reject", 0)),
    }


__all__ = ["run", "RsvpRow", "Decision", "ProfileRecord"]
