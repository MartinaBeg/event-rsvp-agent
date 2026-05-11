"""End-to-end smoke test of the pipeline with fakes for Apify and the workbook."""

from __future__ import annotations

from icp_agent.config import Settings
from icp_agent.models import Decision, Experience, ProfileRecord, RsvpRow
from icp_agent.pipeline import run


class FakeWorkbook:
    def __init__(self, rows: list[RsvpRow]) -> None:
        self.rows = rows
        self.written: list[Decision] = []

    def read_unprocessed(self) -> list[RsvpRow]:
        return list(self.rows)

    def write_decisions(self, decisions: list[Decision]) -> None:
        self.written = list(decisions)


class FakeScraper:
    def __init__(self, profiles_by_url: dict[str, ProfileRecord]) -> None:
        self.profiles_by_url = profiles_by_url

    def scrape(self, urls: list[str]) -> dict[str, ProfileRecord]:
        out: dict[str, ProfileRecord] = {}
        for url in urls:
            out[url] = self.profiles_by_url.get(
                url, ProfileRecord(error="not_in_fixture", raw={})
            )
        return out


def _settings(approval_cap: int = 3) -> Settings:
    s = Settings()
    s.approval_cap = approval_cap
    s.dry_run = False
    return s


def _profile_industry_t1(name: str) -> ProfileRecord:
    return ProfileRecord(
        name=name,
        headline="Research Scientist at OpenAI · LLMs, RLHF",
        current_title="Research Scientist",
        current_company="OpenAI",
        top_experience=[Experience(title="Research Scientist", company="OpenAI")],
        skills=["LLM", "RLHF"],
        about="Working on alignment.",
    )


def _profile_engineer_t2() -> ProfileRecord:
    return ProfileRecord(
        name="DB Eng",
        headline="Senior Software Engineer at Databricks",
        current_title="Senior Software Engineer",
        current_company="Databricks",
        top_experience=[Experience(title="Senior Software Engineer", company="Databricks")],
        skills=["Distributed Systems"],
        about="Data platform infra.",
    )


def _profile_pure_student() -> ProfileRecord:
    return ProfileRecord(
        name="Pure Student",
        headline="PhD Student at Stanford University · NLP",
        current_title="PhD Student",
        current_company="Stanford University",
        top_experience=[Experience(title="PhD Student", company="Stanford University")],
        skills=["NLP"],
        about="Researching low-resource NLP.",
        university_markers=["university", "stanford"],
    )


def test_pipeline_cap_pass_splits_p3():
    """5 P1s + 3 P3s, cap=6 → all P1s approve, top 1 P3 approves, 2 P3s waitlist."""
    rows = []
    profiles: dict[str, ProfileRecord] = {}

    for i in range(5):
        url = f"https://www.linkedin.com/in/p1-{i}/"
        rows.append(RsvpRow(row_number=2 + i, name=f"P1-{i}", linkedin_url=url))
        profiles[url] = _profile_industry_t1(f"P1-{i}")

    for i in range(3):
        url = f"https://www.linkedin.com/in/p3-{i}/"
        rows.append(RsvpRow(row_number=10 + i, name=f"P3-{i}", linkedin_url=url))
        profiles[url] = _profile_engineer_t2()

    workbook = FakeWorkbook(rows)
    scraper = FakeScraper(profiles)
    summary = run(settings=_settings(approval_cap=6), workbook=workbook, scraper=scraper)

    assert summary["rows"] == 8
    assert summary["approved"] == 6  # 5 P1 + 1 P3 fills the cap
    assert summary["waitlisted"] == 2  # remaining 2 P3 flip to waitlist
    assert summary["rejected"] == 0


def test_pipeline_writes_back():
    rows = [
        RsvpRow(row_number=2, name="A", linkedin_url="https://www.linkedin.com/in/a/"),
        RsvpRow(row_number=3, name="B", linkedin_url="https://www.linkedin.com/in/b/"),
    ]
    profiles = {
        "https://www.linkedin.com/in/a/": _profile_industry_t1("A"),
        "https://www.linkedin.com/in/b/": _profile_pure_student(),
    }
    workbook = FakeWorkbook(rows)
    scraper = FakeScraper(profiles)

    run(settings=_settings(), workbook=workbook, scraper=scraper)

    assert len(workbook.written) == 2
    by_row = {d.row_number: d for d in workbook.written}
    assert by_row[2].decision == "Approve"
    assert by_row[3].decision == "Reject"


def test_pipeline_dry_run_skips_write():
    rows = [
        RsvpRow(row_number=2, name="A", linkedin_url="https://www.linkedin.com/in/a/"),
    ]
    profiles = {"https://www.linkedin.com/in/a/": _profile_industry_t1("A")}
    settings = _settings()
    settings.dry_run = True

    workbook = FakeWorkbook(rows)
    scraper = FakeScraper(profiles)
    run(settings=settings, workbook=workbook, scraper=scraper)

    assert workbook.written == []  # nothing written


def test_pipeline_handles_duplicate_urls():
    """Duplicate LinkedIn URLs: first wins, rest become Waitlist with duplicate note."""
    url = "https://www.linkedin.com/in/dupe/"
    rows = [
        RsvpRow(row_number=2, name="A", linkedin_url=url),
        RsvpRow(row_number=3, name="A again", linkedin_url=url),
    ]
    profiles = {url: _profile_industry_t1("A")}
    workbook = FakeWorkbook(rows)
    scraper = FakeScraper(profiles)

    summary = run(settings=_settings(), workbook=workbook, scraper=scraper)

    assert summary["rows"] == 2
    by_row = {d.row_number: d for d in workbook.written}
    assert by_row[2].decision == "Approve"
    assert by_row[3].decision == "Waitlist"
    assert "Duplicate" in by_row[3].notes


def test_pipeline_handles_scrape_failure_per_profile():
    rows = [
        RsvpRow(row_number=2, name="OK", linkedin_url="https://www.linkedin.com/in/ok/"),
        RsvpRow(row_number=3, name="Bad", linkedin_url="https://www.linkedin.com/in/bad/"),
    ]
    profiles = {
        "https://www.linkedin.com/in/ok/": _profile_industry_t1("OK"),
        "https://www.linkedin.com/in/bad/": ProfileRecord(error="actor_error", raw={}),
    }
    workbook = FakeWorkbook(rows)
    scraper = FakeScraper(profiles)

    summary = run(settings=_settings(), workbook=workbook, scraper=scraper)

    assert summary["approved"] == 1
    assert summary["rejected"] == 1


def test_pipeline_no_rows_is_noop():
    workbook = FakeWorkbook([])
    scraper = FakeScraper({})
    summary = run(settings=_settings(), workbook=workbook, scraper=scraper)
    assert summary == {"rows": 0, "approved": 0, "waitlisted": 0, "rejected": 0}
    assert workbook.written == []
