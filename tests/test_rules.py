"""Tests for the rule engine. Loads rubric_cases.json and asserts on classify()."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from icp_agent.models import ProfileRecord, RsvpRow
from icp_agent.rules import classify

FIXTURE = Path(__file__).parent / "fixtures" / "rubric_cases.json"


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["case_id"])
def test_rubric_case(case: dict) -> None:
    profile_dict = dict(case.get("profile") or {})
    profile = ProfileRecord(**profile_dict)
    expected = case["expected"]

    row_overrides = case.get("row_overrides") or {}
    row = RsvpRow(
        row_number=2,
        name=profile.name or "Test Person",
        linkedin_url=row_overrides.get(
            "linkedin_url", "https://www.linkedin.com/in/test-handle/"
        ),
    )

    decision = classify(row, profile)

    if "category" in expected:
        assert decision.category == expected["category"], (
            f"{case['case_id']} category mismatch: "
            f"got {decision.category!r}, expected {expected['category']!r} "
            f"(score={decision.score})"
        )
    if "priority" in expected:
        assert decision.priority == expected["priority"], (
            f"{case['case_id']} priority mismatch: "
            f"got {decision.priority!r}, expected {expected['priority']!r} "
            f"(score={decision.score})"
        )
    if "decision" in expected:
        assert decision.decision == expected["decision"], (
            f"{case['case_id']} decision mismatch: "
            f"got {decision.decision!r}, expected {expected['decision']!r} "
            f"(score={decision.score})"
        )
    if "notes_contains" in expected:
        assert expected["notes_contains"].lower() in decision.notes.lower(), (
            f"{case['case_id']} notes mismatch: got {decision.notes!r}"
        )


def test_at_least_twelve_cases() -> None:
    cases = _load_cases()
    assert len(cases) >= 12, "Spec requires at least 12 rubric cases"
