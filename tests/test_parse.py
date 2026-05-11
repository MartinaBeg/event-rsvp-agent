"""Tests for parse.normalize_profile against representative Apify outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from icp_agent.parse import normalize_profile

FIXTURE = Path(__file__).parent / "fixtures" / "apify_profile_examples.json"


def _load_examples() -> list[dict]:
    return json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("example", _load_examples(), ids=lambda e: e["case_id"])
def test_normalize_shape(example: dict) -> None:
    record = normalize_profile(example["raw"])
    raw = example["raw"]

    expected_name = raw.get("fullName") or raw.get("name")
    assert record.name == expected_name
    assert record.headline == raw.get("headline")
    assert record.current_title == raw.get("currentTitle")
    assert record.current_company == raw.get("currentCompany")
    assert record.error is None
    assert record.raw == raw  # preserved verbatim
    assert isinstance(record.skills, list)
    assert isinstance(record.top_experience, list)
    assert len(record.top_experience) <= 3


def test_normalize_handles_none() -> None:
    record = normalize_profile(None)
    assert record.error == "no_profile_returned"
    assert record.name is None


def test_university_markers_detected_for_phd_student() -> None:
    examples = _load_examples()
    phd = next(e for e in examples if e["case_id"] == "phd_student_pure_academic")
    record = normalize_profile(phd["raw"])
    assert record.university_markers, "expected university markers for Stanford PhD student"


def test_no_university_markers_for_industry_engineer() -> None:
    examples = _load_examples()
    eng = next(e for e in examples if e["case_id"] == "engineer_databricks")
    record = normalize_profile(eng["raw"])
    assert record.university_markers == [], (
        f"unexpected university markers: {record.university_markers}"
    )
