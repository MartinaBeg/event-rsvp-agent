"""Normalize raw Apify LinkedIn profile dicts into ProfileRecord."""

from __future__ import annotations

from typing import Any

from .models import Experience, ProfileRecord

UNIVERSITY_MARKERS = (
    "university",
    "université",
    "universidade",
    "universidad",
    "universität",
    "école",
    "ecole",
    "institute of technology",
    "polytechnic",
    "polytechnique",
    "college",
    "school of",
    "academia",
    "mit",
    "stanford",
    "berkeley",
    "caltech",
    "cmu",
    "carnegie mellon",
    "harvard",
    "princeton",
    "yale",
    "oxford",
    "cambridge",
    "eth zurich",
    "epfl",
    "tsinghua",
    "peking university",
    "imperial college",
    "ucl",
    "ucla",
    "nyu",
    "columbia",
    "uchicago",
    "georgia tech",
    "uiuc",
    "umich",
    "uw",
)


def _first_str(*candidates: Any) -> str | None:
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None


def _experiences(raw: dict[str, Any]) -> list[Experience]:
    """Pull the top experiences out of the raw payload, in order."""
    items = (
        raw.get("experience")
        or raw.get("experiences")
        or raw.get("positions")
        or raw.get("workExperience")
        or []
    )
    out: list[Experience] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = _first_str(it.get("title"), it.get("position"), it.get("role"))
        company = _first_str(
            it.get("companyName"),
            it.get("company"),
            it.get("organization"),
            it.get("orgName"),
        )
        if title or company:
            out.append(Experience(title=title, company=company))
    return out


def _skills(raw: dict[str, Any]) -> list[str]:
    items = raw.get("skills") or raw.get("topSkills") or []
    skills: list[str] = []
    for s in items:
        if isinstance(s, str) and s.strip():
            skills.append(s.strip())
        elif isinstance(s, dict):
            name = _first_str(s.get("name"), s.get("skill"), s.get("title"))
            if name:
                skills.append(name)
    return skills


def _university_markers(text_blob: str, experiences: list[Experience]) -> list[str]:
    blob = text_blob.lower()
    found: list[str] = []
    for marker in UNIVERSITY_MARKERS:
        if marker in blob:
            found.append(marker)
    for e in experiences:
        if not e.company:
            continue
        c = e.company.lower()
        for marker in UNIVERSITY_MARKERS:
            if marker in c and marker not in found:
                found.append(marker)
    return found


def normalize_profile(raw: dict[str, Any] | None) -> ProfileRecord:
    """Normalize whatever the actor returned into a tidy ProfileRecord.

    Best-effort: missing fields are `None`, but the function does not raise.
    """
    if not isinstance(raw, dict):
        return ProfileRecord(error="no_profile_returned", raw={})

    name = _first_str(
        raw.get("fullName"),
        raw.get("name"),
        " ".join(filter(None, [raw.get("firstName"), raw.get("lastName")])).strip() or None,
    )
    headline = _first_str(raw.get("headline"), raw.get("subTitle"), raw.get("subtitle"))
    about = _first_str(raw.get("about"), raw.get("summary"), raw.get("description"))

    experiences = _experiences(raw)
    top_experience = experiences[:3]

    current_title = _first_str(
        raw.get("currentTitle"),
        raw.get("jobTitle"),
        top_experience[0].title if top_experience else None,
    )
    current_company = _first_str(
        raw.get("currentCompany"),
        raw.get("companyName"),
        top_experience[0].company if top_experience else None,
    )

    skills = _skills(raw)

    text_blob = " ".join(
        x
        for x in [
            name or "",
            headline or "",
            about or "",
            current_title or "",
            current_company or "",
        ]
        if x
    )
    uni_markers = _university_markers(text_blob, experiences)

    return ProfileRecord(
        name=name,
        headline=headline,
        current_title=current_title,
        current_company=current_company,
        top_experience=top_experience,
        skills=skills,
        about=about,
        university_markers=uni_markers,
        raw=raw,
    )
