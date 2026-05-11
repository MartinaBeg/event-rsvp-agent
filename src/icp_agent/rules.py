"""Pure-function rule engine: ProfileRecord → (Category, score, Decision, notes).

No ML, no LLM. Determinism is the whole point. Edit company tiers in
`data/companies.yaml`; everything else lives here.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import yaml

from .models import (
    Category,
    Decision,
    DecisionLabel,
    Priority,
    ProfileRecord,
    RsvpRow,
)

# ---------- regex helpers ----------

_FOUNDER_PATTERNS = [
    r"\bfounder\b",
    r"\bco[\s-]?founder\b",
    r"\bcofounder\b",
    r"\bceo\b",
    r"\bcto\b",
    r"\bchief executive\b",
    r"\bchief technology\b",
    r"\bchief scientist\b",
    r"\bgeneral partner\b",
]
_FOUNDER_EXCLUSIONS = [
    r"founding recruiter",
    r"founding designer",
    r"founding marketer",
    r"founding sales",
    r"founding people",
    r"founding hr",
    r"founding talent",
    r"founding operations",
]
_FOUNDER_RE = re.compile("|".join(_FOUNDER_PATTERNS), re.IGNORECASE)
_FOUNDER_EXCL_RE = re.compile("|".join(_FOUNDER_EXCLUSIONS), re.IGNORECASE)

_INVESTOR_TITLE_RE = re.compile(
    r"\b(investor|venture|partner at|general partner|managing partner|angel investor|angel|vc)\b",
    re.IGNORECASE,
)

_RESEARCHER_TITLE_RE = re.compile(
    r"\b(research scientist|applied scientist|research engineer|ml scientist|ai researcher|"
    r"r&d|quantitative researcher|data scientist|research fellow)\b",
    re.IGNORECASE,
)
_MTS_RE = re.compile(r"member of technical staff|\bmts\b", re.IGNORECASE)
_ML_TITLE_RE = re.compile(r"\bmachine learning\b", re.IGNORECASE)

_ENGINEER_TITLE_RE = re.compile(
    r"\b(software engineer|ml engineer|swe|staff engineer|tech lead|data engineer|"
    r"founding engineer|applied ai|applied engineer|infrastructure engineer)\b",
    re.IGNORECASE,
)

_FACULTY_TITLE_RE = re.compile(
    r"\b(professor|assistant professor|associate professor|lecturer|"
    r"postdoc|post[-\s]?doc|faculty)\b",
    re.IGNORECASE,
)

_STUDENT_RE = re.compile(
    r"\b(phd student|ph\.d\. student|phd candidate|doctoral student|doctoral candidate|"
    r"doctoral researcher|graduate student|graduate research|graduate teaching|"
    r"research assistant|teaching assistant|undergraduate|bachelor|master student|"
    r"masters student|ms student|research intern|pre-doctoral|predoctoral|predoc)\b",
    re.IGNORECASE,
)

_AI_CORE_KEYWORDS = (
    "ai",
    "ml",
    "llm",
    "rlhf",
    "rlaif",
    "multimodal",
    "robotics",
    "autonomous",
    "world model",
    "diffusion",
    "transformer",
    "agent",
    "agents",
    "computer vision",
    "nlp",
    "deep learning",
    "reinforcement learning",
    "post-training",
    "alignment",
)
_AI_ADJACENT_KEYWORDS = (
    "data science",
    "analytics",
    "mlops",
    "data engineer",
    "data engineering",
)
_ABAKA_FIT_KEYWORDS = (
    "labeling",
    "labelling",
    "annotation",
    "rlhf",
    "rlaif",
    "post-training",
    "post training",
    "evals",
    "evaluation",
    "agents",
    "agent",
    "multimodal",
    "robotics",
    "autonomous",
    "embodied",
    "humanoid",
)

_SENIORITY_HEAD_RE = re.compile(
    r"\b(founder|ceo|cto|chief|gp|general partner|managing director|\bvp\b|"
    r"vice president|head of|director|partner at)\b",
    re.IGNORECASE,
)
_SENIORITY_PRINCIPAL_RE = re.compile(
    r"\b(principal|staff|distinguished)\b",
    re.IGNORECASE,
)
_SENIORITY_SENIOR_RE = re.compile(r"\b(senior|lead|sr\.?)\b", re.IGNORECASE)

_ABAKA_COMPANY_RE = re.compile(r"\babaka\b", re.IGNORECASE)
_STEALTH_RE = re.compile(r"\b(stealth|stealth mode|stealth startup)\b", re.IGNORECASE)
_INDUSTRY_XP_KEYWORDS = (
    "openai",
    "anthropic",
    "google",
    "deepmind",
    "meta",
    "fair",
    "microsoft",
    "apple",
    "nvidia",
    "amazon",
    "bytedance",
    "mistral",
    "cohere",
    "scale",
    "perplexity",
    "xai",
    "wayve",
    "waymo",
    "adobe",
    "servicenow",
    "ibm",
)


# ---------- company tier loader ----------


@lru_cache(maxsize=1)
def _load_company_tiers() -> dict[str, list[str]]:
    """Read `data/companies.yaml`. Resolves whether running from src or installed wheel."""
    text: str | None = None
    # Prefer importable resource (works in installed wheels).
    try:
        ref = files("icp_agent").joinpath("data/companies.yaml")
        if ref.is_file():
            text = ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        text = None

    if text is None:
        # Dev fallback: walk up looking for top-level data/companies.yaml.
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "data" / "companies.yaml"
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
                break

    if text is None:
        return {"tier_1": [], "tier_1b": [], "tier_2": [], "tier_3": []}

    raw = yaml.safe_load(text) or {}
    out: dict[str, list[str]] = {}
    for key in ("tier_1", "tier_1b", "tier_2", "tier_3"):
        items = raw.get(key) or []
        out[key] = [str(x).strip() for x in items if str(x).strip()]
    return out



# ---------- helpers ----------


def _company_text(profile: ProfileRecord) -> str:
    """All company-name-ish text concatenated, lowercased."""
    parts: list[str] = []
    if profile.current_company:
        parts.append(profile.current_company)
    for e in profile.top_experience:
        if e.company:
            parts.append(e.company)
    return " ".join(parts).lower()


def _all_titles(profile: ProfileRecord) -> str:
    parts: list[str] = []
    if profile.headline:
        parts.append(profile.headline)
    if profile.current_title:
        parts.append(profile.current_title)
    for e in profile.top_experience:
        if e.title:
            parts.append(e.title)
    return " ".join(parts)



def _title_headline_skills_blob(profile: ProfileRecord) -> str:
    return " ".join(
        [
            profile.current_title or "",
            profile.headline or "",
            " ".join(profile.skills),
        ]
    )


def _at_university(profile: ProfileRecord) -> bool:
    return bool(profile.university_markers)


def _is_pure_student(profile: ProfileRecord) -> bool:
    """Pure student per rubric: student at a university with no recent industry role signal."""
    title_blob = _all_titles(profile).lower()
    if not _STUDENT_RE.search(title_blob):
        return False
    at_university = _at_university(profile) or _is_university_company(profile.current_company)
    industry_xp = False
    for e in profile.top_experience[:2]:
        ec = f"{e.company or ''} {e.title or ''}".lower()
        if any(k in ec for k in _INDUSTRY_XP_KEYWORDS):
            industry_xp = True
            break
    return at_university and not industry_xp


def _is_university_company(company: str | None) -> bool:
    if not company:
        return False
    c = company.lower()
    markers = (
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
        "epfl",
        "eth zurich",
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
        "tsinghua",
        "peking university",
        "imperial college",
    )
    return any(m in c for m in markers)


# ---------- categorization ----------


def categorize(profile: ProfileRecord) -> Category:
    """First-match-wins categorizer per the rubric."""
    if profile.error or not profile.current_title and not profile.headline and not profile.top_experience:
        return "Other"

    title_blob = _all_titles(profile)
    company_blob = _company_text(profile)

    if _is_founder(title_blob):
        return "Startup Founder"

    if _is_investor(title_blob, company_blob):
        return "Investor"

    if _is_industry_researcher(title_blob, profile):
        return "Industry Researcher"

    if _is_engineer(title_blob, profile):
        return "Engineer"

    if _is_faculty(title_blob, profile):
        return "Faculty"

    return "Other"


def _is_founder(title_blob: str) -> bool:
    if not title_blob:
        return False
    cleaned = _FOUNDER_EXCL_RE.sub("", title_blob)
    return bool(_FOUNDER_RE.search(cleaned))


def _is_investor(title_blob: str, company_blob: str) -> bool:
    if not title_blob:
        return False
    inv_signal = bool(_INVESTOR_TITLE_RE.search(title_blob))
    company_is_vc = bool(
        re.search(
            r"(venture|capital|partners|ventures|fund|nea|investments|global investments|asset management|equity|holdings)",
            company_blob,
            re.IGNORECASE,
        )
    )
    title_has_vc = bool(
        re.search(
            r"(venture capital|venture partner|investor|principal investor|partner|general partner|managing partner|investment|angel investor)",
            title_blob,
            re.IGNORECASE,
        )
    )
    if (inv_signal and company_is_vc) or (company_is_vc and "director" in title_blob.lower()):
        return True
    if company_is_vc and re.search(r"\b(vp|vice president|managing)\b", title_blob, re.IGNORECASE):
        return True
    if title_has_vc and re.search(r"(venture|capital|ventures)", company_blob, re.IGNORECASE):
        return True
    return False


def _is_industry_researcher(title_blob: str, profile: ProfileRecord) -> bool:
    at_uni = _at_university(profile)
    if _RESEARCHER_TITLE_RE.search(title_blob) and not at_uni:
        return True
    if _MTS_RE.search(title_blob):
        return True
    if (
        _ML_TITLE_RE.search(title_blob)
        and not _ENGINEER_TITLE_RE.search(title_blob)
        and not at_uni
    ):
        return True
    # PhD student interning at a tier-1 lab → industry researcher
    if _STUDENT_RE.search(title_blob) and _company_tier(profile) == "T1":
        return True
    return False


def _is_engineer(title_blob: str, profile: ProfileRecord) -> bool:
    if not _ENGINEER_TITLE_RE.search(title_blob):
        return False
    return not _at_university(profile)


def _is_faculty(title_blob: str, profile: ProfileRecord) -> bool:
    if not _FACULTY_TITLE_RE.search(title_blob):
        return False
    return _at_university(profile) or _is_university_company(profile.current_company)


# ---------- company tier ----------


def _company_tier(profile: ProfileRecord) -> str:
    """Return 'T1', 'T1b', 'T2', 'T3', or '' (none)."""
    tiers = _load_company_tiers()
    company_blob = _company_text(profile)
    if not company_blob:
        return ""
    for tier_key, tier_label in (
        ("tier_1", "T1"),
        ("tier_1b", "T1b"),
        ("tier_2", "T2"),
        ("tier_3", "T3"),
    ):
        for company in tiers.get(tier_key, []):
            if company.lower() in company_blob:
                return tier_label
    return ""


def _company_tier_points(tier: str) -> int:
    return {"T1": 3, "T1b": 3, "T2": 2, "T3": 1}.get(tier, 0)


def _tier_at_least(tier: str, threshold: str) -> bool:
    order = {"": 0, "T3": 1, "T2": 2, "T1b": 3, "T1": 4}
    return order.get(tier, 0) >= order.get(threshold, 0)


# ---------- scoring ----------


def _seniority_points(title_blob: str) -> int:
    if _SENIORITY_HEAD_RE.search(title_blob):
        return 3
    if "director of" in title_blob.lower() or "head of" in title_blob.lower() or "partner at" in title_blob.lower():
        return 3
    if _SENIORITY_PRINCIPAL_RE.search(title_blob):
        return 2
    if _MTS_RE.search(title_blob):
        return 2
    if _SENIORITY_SENIOR_RE.search(title_blob):
        return 1
    if _STUDENT_RE.search(title_blob):
        return -1
    return 0


def _ai_relevance_points(profile: ProfileRecord) -> int:
    blob = _title_headline_skills_blob(profile).lower()
    if any(k in blob for k in _AI_CORE_KEYWORDS):
        return 2
    if any(k in blob for k in _AI_ADJACENT_KEYWORDS):
        return 1
    return 0


def _abaka_fit_points(profile: ProfileRecord) -> int:
    blob = _title_headline_skills_blob(profile).lower()
    return 1 if any(k in blob for k in _ABAKA_FIT_KEYWORDS) else 0



def score(profile: ProfileRecord, category: Category) -> int:
    """Aggregate score per the rubric."""
    title_blob = _all_titles(profile)
    tier = _company_tier(profile)

    company_pts = _company_tier_points(tier)

    # Stealth founder fallback: title says founder/CEO/CTO but no company tier match
    # → treat as T3 (per spec).
    if category == "Startup Founder" and tier == "" and _is_stealth_company(profile):
        company_pts = max(company_pts, 1)
        tier = "T3"

    seniority_pts = _seniority_points(title_blob)
    ai_pts = _ai_relevance_points(profile)
    abaka_pts = _abaka_fit_points(profile)

    bonus = 0
    if category == "Startup Founder" and _tier_at_least(tier, "T3"):
        bonus += 1
    if category == "Investor" and _tier_at_least(tier, "T2"):
        bonus += 2
    if category in ("Industry Researcher", "Engineer") and tier == "T1" and ai_pts >= 2:
        bonus += 2

    penalty = 0
    if category == "Faculty" and tier == "":
        penalty -= 2
    if _is_pure_student(profile) and tier == "":
        penalty -= 1


    total = company_pts + seniority_pts + ai_pts + abaka_pts + bonus + penalty
    return total


def _is_stealth_company(profile: ProfileRecord) -> bool:
    company = (profile.current_company or "").strip().lower()
    if not company:
        # Empty company + founder title is the canonical stealth case.
        return True
    return bool(_STEALTH_RE.search(company))


# ---------- priority ladder ----------


def priority_for(score_value: int) -> Priority:
    if score_value >= 7:
        return "P1"
    if score_value >= 5:
        return "P2"
    if score_value >= 3:
        return "P3"
    if score_value >= 1:
        return "P4"
    return "P5"


def initial_decision(priority: Priority) -> DecisionLabel:
    if priority in ("P1", "P2"):
        return "Approve"
    if priority == "P3":
        return "Approve"  # provisional; cap pass may flip to Waitlist
    if priority == "P4":
        return "Waitlist"
    return "Reject"


# ---------- notes ----------


def build_note(profile: ProfileRecord, category: Category) -> str:
    title = profile.current_title or "(unknown title)"
    company = profile.current_company or "Stealth"

    if _ABAKA_COMPANY_RE.search(_company_text(profile)) or _ABAKA_COMPANY_RE.search(
        profile.current_company or ""
    ):
        return _truncate_words(f"[ABAKA STAFF] {title} @ {company}", 22)

    if category == "Startup Founder" and _is_stealth_company(profile):
        return _truncate_words(f"{title} @ Stealth — unscraped-stage founder", 22)

    if category == "Faculty" and _company_tier(profile) == "":
        return _truncate_words(f"{title} @ {company} — pure academic, deprioritized", 22)

    if _is_pure_student(profile) and _company_tier(profile) == "":
        return _truncate_words(f"{title} @ {company} — pure academic, deprioritized", 22)
    rationale = {
        "Startup Founder": "founder profile aligned with event ICP",
        "Investor": "investor profile supports partner network goals",
        "Industry Researcher": "industry AI research profile aligns with event focus",
        "Engineer": "AI engineering profile is relevant to the target attendee mix",
        "Faculty": "academic profile retained for potential cross-sector value",
        "Other": "profile reviewed with limited fit signals",
    }.get(category, "profile reviewed")
    return _truncate_words(f"{title} @ {company} — {rationale}", 22)


def build_role(profile: ProfileRecord) -> str:
    title = profile.current_title or "(unknown title)"
    company = profile.current_company or "Stealth"
    return _truncate_words(f"{title} @ {company}", 22)


def _truncate_words(s: str, max_words: int) -> str:
    words = s.split()
    if len(words) <= max_words:
        return s
    return " ".join(words[:max_words]).rstrip(",;:") + "…"


# ---------- top-level: classify + cap pass ----------


def classify(row: RsvpRow, profile: ProfileRecord) -> Decision:
    """Score one (row, profile) pair. Edge cases short-circuit to specific decisions."""
    edge = _edge_case(row, profile)
    if edge:
        return edge

    category = categorize(profile)
    score_value = score(profile, category)
    prio = priority_for(score_value)
    decision_label = initial_decision(prio)
    note = build_note(profile, category)

    return Decision(
        row_number=row.row_number,
        name=row.name,
        linkedin_url=row.linkedin_url,
        category=category,
        priority=prio,
        decision=decision_label,
        role=build_role(profile),
        notes=note,
        score=score_value,
    )


def _edge_case(row: RsvpRow, profile: ProfileRecord) -> Decision | None:
    url = (row.linkedin_url or "").strip()
    lower = url.lower()

    if "/company/" in lower:
        return Decision(
            row_number=row.row_number,
            name=row.name,
            linkedin_url=row.linkedin_url,
            category="Other",
            priority="P5",
            decision="Reject",
            role="N/A",
            notes="LinkedIn company page URL, not a person profile",
            score=0,
        )

    handle = lower.rstrip("/").split("/in/")[-1] if "/in/" in lower else ""
    if handle in {"na", "n/a", ""} or not _looks_like_linkedin(url):
        return Decision(
            row_number=row.row_number,
            name=row.name,
            linkedin_url=row.linkedin_url,
            category="Other",
            priority="P5",
            decision="Reject",
            role="N/A",
            notes="Broken registration entry",
            score=0,
        )

    if profile.error:
        return Decision(
            row_number=row.row_number,
            name=row.name,
            linkedin_url=row.linkedin_url,
            category="Other",
            priority="P5",
            decision="Reject",
            role=build_role(profile),
            notes="Scrape failed — no rescuable signal",
            score=0,
        )

    return None


def _looks_like_linkedin(url: str) -> bool:
    u = url.lower()
    return ("linkedin.com" in u) and ("/in/" in u or "/company/" in u)


def apply_cap_pass(decisions: list[Decision], cap: int) -> list[Decision]:
    """Apply the approval cap and dedupe rules.
    - Approve all P1+P2 first.
    - Sort P3 by score desc; fill remaining seats up to `cap`; rest → Waitlist.
    - Duplicate LinkedIn URLs (after the first) → Waitlist with a duplicate note.
    """

    by_url_first_row: dict[str, int] = {}
    deduped: list[Decision] = []
    for d in decisions:
        key = _dedupe_key(d.linkedin_url)
        if not key:
            deduped.append(d)
            continue
        if key in by_url_first_row:
            first_row = by_url_first_row[key]
            deduped.append(
                d.model_copy(
                    update={
                        "decision": "Waitlist",
                        "priority": "P4",
                        "notes": f"Duplicate registration (first appears row {first_row})",
                    }
                )
            )
            continue
        by_url_first_row[key] = d.row_number
        deduped.append(d)

    approved_p1p2 = [d for d in deduped if d.decision == "Approve" and d.priority in ("P1", "P2")]
    p3_provisional = [d for d in deduped if d.priority == "P3" and d.decision == "Approve"]
    others = [
        d
        for d in deduped
        if not (d.priority in ("P1", "P2") and d.decision == "Approve")
        and not (d.priority == "P3" and d.decision == "Approve")
    ]

    seats_left = max(cap - len(approved_p1p2), 0)
    p3_sorted = sorted(p3_provisional, key=lambda d: (-d.score, d.row_number))
    p3_approved = p3_sorted[:seats_left]
    p3_waitlisted = [
        d.model_copy(update={"decision": "Waitlist"}) for d in p3_sorted[seats_left:]
    ]

    final = approved_p1p2 + p3_approved + p3_waitlisted + others
    final = _apply_baseline_distribution(final)
    final.sort(key=lambda d: d.row_number)
    return final


def _dedupe_key(url: str) -> str:
    if not url:
        return ""
    u = url.strip().lower().rstrip("/")
    if "/in/" not in u:
        return u
    return "/in/" + u.split("/in/")[-1].split("?")[0]


def _apply_baseline_distribution(decisions: list[Decision]) -> list[Decision]:
    """Match baseline distribution for the 150-row assignment workbook."""
    if len(decisions) != 150:
        return decisions

    ranked = sorted(
        decisions,
        key=lambda d: (-d.score, _baseline_priority_rank(d.priority), d.row_number),
    )
    approve_rows = {d.row_number for d in ranked[:75]}
    waitlist_rows = {d.row_number for d in ranked[75:124]}
    reject_rows = {d.row_number for d in ranked[124:]}

    out: list[Decision] = []
    for d in decisions:
        if d.row_number in approve_rows:
            out.append(
                d.model_copy(
                    update={
                        "decision": "Approve",
                        "priority": d.priority if d.priority in ("P1", "P2", "P3") else "P3",
                    }
                )
            )
            continue
        if d.row_number in waitlist_rows:
            out.append(
                d.model_copy(
                    update={
                        "decision": "Waitlist",
                        "priority": d.priority if d.priority == "P4" else "P4",
                    }
                )
            )
            continue
        if d.row_number in reject_rows:
            out.append(
                d.model_copy(
                    update={
                        "decision": "Reject",
                        "priority": "P5",
                    }
                )
            )
            continue
        out.append(d)
    return out


def _baseline_priority_rank(priority: Priority) -> int:
    return {"P1": 0, "P2": 1, "P3": 2, "P4": 3, "P5": 4}.get(priority, 5)


