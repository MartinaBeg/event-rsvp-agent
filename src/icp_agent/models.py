"""Pydantic models for the ICP pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal[
    "Startup Founder",
    "Investor",
    "Industry Researcher",
    "Engineer",
    "Faculty",
    "Other",
]
Priority = Literal["P1", "P2", "P3", "P4", "P5"]
DecisionLabel = Literal["Approve", "Waitlist", "Reject"]


class RsvpRow(BaseModel):
    """A row read from the sheet that needs processing."""

    row_number: int
    name: str
    linkedin_url: str
    decision: str | None = None
    category: str | None = None
    priority: str | None = None
    notes: str | None = None


class Experience(BaseModel):
    title: str | None = None
    company: str | None = None


class ProfileRecord(BaseModel):
    """Normalized LinkedIn profile data, framework-agnostic."""

    name: str | None = None
    headline: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    top_experience: list[Experience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    about: str | None = None
    university_markers: list[str] = Field(default_factory=list)
    error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    """The final classification verdict for one RSVP."""

    row_number: int
    name: str
    linkedin_url: str
    category: Category
    priority: Priority
    decision: DecisionLabel
    role: str = ""
    notes: str
    score: int = 0
