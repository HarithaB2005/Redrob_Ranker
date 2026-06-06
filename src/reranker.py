"""
reranker.py — Final reranking + reasoning generation for top-200 candidates.

No API calls. Reasoning is generated from structured candidate data.

Submission spec Stage 4 checks:
  - Specific facts from candidate profile
  - JD connection
  - Honest concerns (gaps acknowledged)
  - No hallucination
  - Variation across candidates
  - Rank consistency (tone matches rank)
"""

from __future__ import annotations
from typing import Optional


def _describe_availability(row: dict) -> str:
    """Build a short availability descriptor."""
    parts = []
    if row["open_to_work"]:
        parts.append("open to work")
    if row["days_inactive"] <= 7:
        parts.append("active this week")
    elif row["days_inactive"] <= 30:
        parts.append("active this month")
    elif row["days_inactive"] > 180:
        parts.append(f"inactive {row['days_inactive']} days")

    rr = row["response_rate"]
    if rr >= 0.7:
        parts.append(f"high recruiter response rate ({rr:.0%})")
    elif rr < 0.15:
        parts.append(f"low response rate ({rr:.0%})")

    notice = row["notice_days"]
    if notice <= 30:
        parts.append(f"{notice}d notice")
    elif notice > 60:
        parts.append(f"long notice ({notice}d)")

    return "; ".join(parts) if parts else "platform activity neutral"


def _describe_skills(row: dict) -> str:
    """Build skill description from matched skills."""
    must = [s.replace("*", "") for s in row.get("matched_must_skills", [])]
    strong = [s.replace("*", "") for s in row.get("matched_strong_skills", [])]

    parts = []
    if must:
        parts.append(f"matches core JD requirements: {', '.join(must[:3])}")
    if strong:
        parts.append(f"also has {', '.join(strong[:2])}")
    if not parts:
        parts.append("adjacent skills only")
    return "; ".join(parts)


def _build_reasoning(row: dict, rank: int) -> str:
    """
    Build a specific, honest, non-hallucinated 1-2 sentence reasoning.
    Tone is calibrated to rank (top-10 glowing, 50-100 factual/cautious).
    """
    cid = row["candidate_id"]
    yoe = row.get("yoe", 0)
    title = row.get("current_title", "Engineer")
    loc = row.get("location", "")
    country = row.get("country", "")
    location_str = f"{loc}, {country}" if loc and country else (loc or country or "unknown location")

    skill_str = _describe_skills(row)
    avail_str = _describe_availability(row)

    cats = row.get("category_hits", 0)
    domain = row.get("domain_score", 0)
    github = row.get("github_score", 0)
    consulting = row.get("is_mainly_consulting", False)

    # Concerns / red flags
    concerns = []
    if consulting:
        concerns.append("career primarily at consulting firms")
    if row.get("days_inactive", 0) > 180:
        concerns.append(f"inactive for {row['days_inactive']} days")
    if row.get("response_rate", 0.5) < 0.15:
        concerns.append("low recruiter response rate")
    if row.get("notice_days", 30) > 90:
        concerns.append(f"long notice period ({row['notice_days']}d)")
    if yoe < 4:
        concerns.append("below minimum experience range")
    if cats < 2:
        concerns.append("limited match on core JD technical requirements")

    # Build sentence 1: core facts
    s1 = f"{title} with {yoe:.1f} years of experience based in {location_str}; {skill_str}."

    # Build sentence 2: availability + concerns (honest, rank-calibrated)
    if rank <= 10:
        # Top 10: strong positive tone, still specific
        if concerns:
            s2 = f"Strong engagement signals ({avail_str}); note: {concerns[0]}."
        else:
            s2 = f"Strong engagement and availability ({avail_str}); {cats}/5 core JD requirement categories matched."
    elif rank <= 30:
        # Mid-top: balanced
        if concerns:
            s2 = f"Engagement: {avail_str}. Concern: {concerns[0]}."
        else:
            s2 = f"Engagement: {avail_str}; {cats}/5 JD categories covered."
    elif rank <= 60:
        # Lower: factual, note gaps
        if concerns:
            s2 = f"Ranked here due to: {'; '.join(concerns[:2])}. Availability: {avail_str}."
        else:
            s2 = f"Partial match; {cats}/5 JD categories covered. {avail_str}."
    else:
        # Bottom: honest about why they're low
        if concerns:
            s2 = f"Below cutoff primarily due to: {'; '.join(concerns[:2])}."
        else:
            s2 = f"Included as borderline fit; {cats}/5 JD categories covered with weak engagement."

    return f"{s1} {s2}"


def rerank_and_explain(
    top_200: list[dict],
    jd: dict,
    final_k: int = 100
) -> list[dict]:
    """
    Final reranking pass over top-200 candidates.

    Additional reranking signal: the initial scorer is good but doesn't
    account for 'JD hints' like:
    - Candidates who listed 'AI Engineer' or 'ML Engineer' as title get a nudge
    - Candidates with GitHub activity score > 50 get a nudge (JD: open source)
    - Candidates with very strong behavioral (open + active + high response) get a nudge
    """
    for row in top_200:
        rerank_bonus = 0.0

        # Title alignment bonus
        title_lower = row.get("current_title", "").lower()
        if any(t in title_lower for t in ["ai engineer", "ml engineer", "machine learning",
                                            "data scientist", "nlp", "search engineer",
                                            "applied scientist", "research engineer"]):
            rerank_bonus += 0.03

        # GitHub signal (JD says: open-source in AI/ML space)
        if row.get("github_score", 0) > 0.5:
            rerank_bonus += 0.02

        # Triple availability bonus (open + active + high response rate)
        if (row.get("open_to_work") and
                row.get("days_inactive", 999) <= 14 and
                row.get("response_rate", 0) >= 0.6):
            rerank_bonus += 0.025

        # Strong skill match bonus (hit 4 or 5 of 5 categories)
        cats = row.get("category_hits", 0)
        if cats >= 4:
            rerank_bonus += 0.02
        elif cats >= 3:
            rerank_bonus += 0.01

        row["composite_score"] = round(row["composite_score"] + rerank_bonus, 6)

    # Re-sort after bonus adjustments
    # Secondary sort by candidate_id ASCENDING for ties (validator requirement)
    top_200.sort(key=lambda x: (-x["composite_score"], x["candidate_id"])  )

    # Generate reasoning for final top-100 (not all 200 — only what we submit)
    final = top_200[:final_k]
    for rank_idx, row in enumerate(final, start=1):
        row["reasoning"] = _build_reasoning(row, rank_idx)

    return final
