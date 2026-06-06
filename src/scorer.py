"""
scorer.py — Deterministic multi-signal candidate scorer

Rules:
- No API calls, no GPU, no external models
- All scoring is deterministic and reproducible
- Implements hard filters + 5-dimension soft scoring
- Returns None for hard-disqualified candidates

Scoring dimensions:
  1. skill_match       — semantic skill matching against JD must-haves
  2. career_trajectory — growth, product vs consulting, domain fit
  3. behavioral        — platform engagement signals
  4. education         — institution tier + field relevance
  5. location_fit      — India + city preference
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from src.jd_config import JD_PROFILE


# ---------------------------------------------------------------------------
# Skill matching helpers
# ---------------------------------------------------------------------------

def _build_skill_index(skills: list[dict]) -> dict[str, dict]:
    """Build a lower-case name → skill dict for fast lookup."""
    return {s["name"].lower(): s for s in skills}


def _skill_text_match(skill_name: str, target_terms: list[str]) -> bool:
    """Check if a skill name semantically matches any target term."""
    skill_lower = skill_name.lower()
    for term in target_terms:
        term_lower = term.lower()
        if term_lower in skill_lower or skill_lower in term_lower:
            return True
    return False


def _proficiency_weight(proficiency: str) -> float:
    weights = {"expert": 1.0, "advanced": 0.85, "intermediate": 0.65, "beginner": 0.40}
    return weights.get(proficiency, 0.5)


def score_skills(candidate: dict, jd: dict) -> dict:
    """
    Score candidate skills against JD must-haves and strong signals.
    Returns raw scores and matched skill lists.
    """
    skills = candidate.get("skills", [])
    skill_idx = _build_skill_index(skills)

    # Also extract skill names from career descriptions (keyword presence in text)
    career_text = " ".join(
        r.get("description", "") for r in candidate.get("career_history", [])
    ).lower()
    profile_text = (
        candidate.get("profile", {}).get("summary", "") + " " +
        candidate.get("profile", {}).get("headline", "")
    ).lower()
    full_text = career_text + " " + profile_text

    # --- Must-have skill matching ---
    must_have_terms = jd["must_have_skills"]
    matched_must = []
    unmatched_must = []
    must_score_sum = 0.0

    for term in must_have_terms:
        # Check in skills list first (higher confidence)
        found_in_skills = False
        for skill_name, skill_data in skill_idx.items():
            if _skill_text_match(skill_name, [term]):
                weight = _proficiency_weight(skill_data.get("proficiency", "intermediate"))
                # Bonus for endorsements (capped)
                endorsement_bonus = min(skill_data.get("endorsements", 0) / 50, 0.15)
                must_score_sum += weight + endorsement_bonus
                matched_must.append(term)
                found_in_skills = True
                break

        if not found_in_skills:
            # Check in free text (career descriptions, summary) — lower weight
            if term.lower() in full_text:
                must_score_sum += 0.5  # Text mention is weaker than listed skill
                matched_must.append(f"{term}*")  # asterisk = text-only match
            else:
                unmatched_must.append(term)

    # Normalize by number of unique meaningful terms (deduplicate synonyms)
    # We use count of matched unique categories, not raw term count
    unique_must_categories = {
        "embeddings_retrieval": ["embeddings", "sentence-transformers", "openai embeddings", "bge", "e5",
                                  "semantic search", "dense retrieval", "vector search", "embedding"],
        "vector_db": ["pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
                       "elasticsearch", "vector database", "vector store", "hybrid search", "chroma", "annoy"],
        "ranking_systems": ["ranking", "retrieval", "recommendation system", "search", "bm25",
                             "information retrieval", "candidate ranking", "re-ranking", "reranking",
                             "learning to rank"],
        "evaluation": ["ndcg", "mrr", "map", "evaluation", "a/b testing", "offline eval",
                        "ranking evaluation", "benchmark"],
        "python": ["python"],
    }

    category_hits = 0
    for cat, terms in unique_must_categories.items():
        for term in terms:
            matched_in_cat = any(term in m.lower() for m in matched_must)
            found_in_text = term in full_text
            if matched_in_cat or found_in_text:
                category_hits += 1
                break

    must_score = category_hits / len(unique_must_categories)  # 0-1

    # Also check assessment scores for relevant skills
    assessment_scores = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {})
    assessment_bonus = 0.0
    for skill_name, score in assessment_scores.items():
        for rel_skill in jd["relevant_assessment_skills"]:
            if rel_skill.lower() in skill_name.lower():
                assessment_bonus += (score / 100) * 0.05
                break
    assessment_bonus = min(assessment_bonus, 0.10)

    # --- Strong signal skills ---
    strong_terms = jd["strong_signal_skills"]
    strong_hits = 0
    matched_strong = []
    for term in strong_terms:
        for skill_name in skill_idx:
            if _skill_text_match(skill_name, [term]):
                strong_hits += 1
                matched_strong.append(term)
                break
        else:
            if term.lower() in full_text:
                strong_hits += 0.5
                matched_strong.append(f"{term}*")

    strong_score = min(strong_hits / 8, 1.0)  # normalize: 8+ strong skills = perfect

    final_skill_score = (must_score * 0.70 + strong_score * 0.20 + assessment_bonus * 0.10)

    return {
        "skill_score": round(final_skill_score, 4),
        "category_hits": category_hits,
        "matched_must": matched_must[:5],   # For reasoning
        "matched_strong": matched_strong[:5],
        "must_score": round(must_score, 3),
        "strong_score": round(strong_score, 3),
    }


# ---------------------------------------------------------------------------
# Career trajectory scoring
# ---------------------------------------------------------------------------

def score_career(candidate: dict, jd: dict) -> dict:
    """
    Score career trajectory:
    - Product company vs consulting
    - Upward growth (title progression)
    - Domain relevance (AI/ML/NLP/Search)
    - Experience years in band
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    yoe = float(profile.get("years_of_experience", 0))

    # --- Experience years band score ---
    if yoe < 4:
        exp_score = 0.3
    elif yoe < 5:
        exp_score = 0.65
    elif yoe < 6:
        exp_score = 0.80
    elif yoe <= 8:
        exp_score = 1.0   # Ideal band
    elif yoe <= 10:
        exp_score = 0.85
    elif yoe <= 13:
        exp_score = 0.65
    else:
        exp_score = 0.45

    # --- Product company detection ---
    consulting_flags = jd["consulting_red_flag_companies"]
    total_months = sum(r.get("duration_months", 0) for r in career)
    consulting_months = 0
    product_months = 0

    for role in career:
        company_lower = role.get("company", "").lower()
        is_consulting = any(flag in company_lower for flag in consulting_flags)
        desc_lower = role.get("description", "").lower()
        has_product_signal = any(
            sig in desc_lower for sig in jd["product_company_signals"]
        )

        duration = role.get("duration_months", 0)
        if is_consulting:
            consulting_months += duration
        elif has_product_signal:
            product_months += duration

    consulting_ratio = consulting_months / max(total_months, 1)
    product_ratio = product_months / max(total_months, 1)

    # JD says: "only consulting career" is a hard disqualifier
    # But "prior product company experience" overrides this
    if consulting_ratio > 0.85 and product_ratio < 0.10:
        # Entire career consulting — hard penalty but not full disqualify
        product_score = 0.15
    elif consulting_ratio > 0.60:
        product_score = 0.4
    elif product_ratio > 0.50:
        product_score = 1.0
    elif product_ratio > 0.25:
        product_score = 0.75
    else:
        product_score = 0.55  # Neutral — no clear signal either way

    # --- Domain relevance in career descriptions ---
    ai_ml_terms = [
        "machine learning", "deep learning", "neural", "nlp", "embedding",
        "retrieval", "ranking", "recommendation", "search", "vector",
        "model", "inference", "training", "pytorch", "tensorflow", "sklearn",
        "data science", "ai", "llm", "transformer", "bert",
    ]
    domain_hits = 0
    for role in career:
        desc = role.get("description", "").lower()
        title = role.get("title", "").lower()
        for term in ai_ml_terms:
            if term in desc or term in title:
                domain_hits += 1
                break  # one per role

    domain_score = min(domain_hits / max(len(career), 1), 1.0)

    # --- Title progression (growth velocity) ---
    # Higher roles = more recent (career sorted newest first typically)
    seniority_map = {
        "principal": 6, "staff": 5, "lead": 5,
        "senior": 4, "sr.": 4,
        "mid": 3,
        "junior": 2, "jr.": 2, "associate": 2,
        "intern": 1, "trainee": 1,
    }

    def get_seniority(title: str) -> int:
        t = title.lower()
        for key, val in seniority_map.items():
            if key in t:
                return val
        return 3  # default: mid-level

    if len(career) >= 2:
        # Sort by start date
        sorted_career = sorted(
            career,
            key=lambda r: r.get("start_date", "2000-01-01")
        )
        oldest_level = get_seniority(sorted_career[0].get("title", ""))
        newest_level = get_seniority(sorted_career[-1].get("title", ""))
        growth = newest_level - oldest_level
        if growth >= 2:
            trajectory_score = 1.0    # Clear upward
        elif growth == 1:
            trajectory_score = 0.8
        elif growth == 0:
            trajectory_score = 0.6    # Lateral / stable
        else:
            trajectory_score = 0.3    # Downward
    else:
        trajectory_score = 0.6

    # Combine career signals
    career_score = (
        exp_score * 0.25 +
        product_score * 0.35 +
        domain_score * 0.25 +
        trajectory_score * 0.15
    )

    return {
        "career_score": round(career_score, 4),
        "exp_score": round(exp_score, 3),
        "product_score": round(product_score, 3),
        "domain_score": round(domain_score, 3),
        "trajectory_score": round(trajectory_score, 3),
        "yoe": yoe,
        "consulting_ratio": round(consulting_ratio, 2),
        "is_mainly_consulting": consulting_ratio > 0.85,
    }


# ---------------------------------------------------------------------------
# Behavioral signals scoring
# ---------------------------------------------------------------------------

def score_behavioral(candidate: dict, jd: dict) -> dict:
    """
    Score platform behavioral signals.
    Key insight from JD: "A perfect-on-paper candidate who hasn't logged in
    for 6 months and has a 5% response rate is, for hiring purposes, not
    actually available."
    """
    sig = candidate.get("redrob_signals", {})
    ref_date = jd["reference_date"]

    # --- Recency: last active ---
    last_active_str = sig.get("last_active_date", "2020-01-01")
    try:
        last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
        days_inactive = (ref_date - last_active).days
    except (ValueError, TypeError):
        days_inactive = 365

    if days_inactive <= 7:
        recency_score = 1.0
    elif days_inactive <= 30:
        recency_score = 0.85
    elif days_inactive <= 60:
        recency_score = 0.65
    elif days_inactive <= 90:
        recency_score = 0.45
    elif days_inactive <= 180:
        recency_score = 0.25
    else:
        recency_score = 0.05  # Over 6 months: JD says down-weight heavily

    # --- Open to work ---
    open_to_work = 1.0 if sig.get("open_to_work_flag", False) else 0.3

    # --- Recruiter response rate ---
    rr = float(sig.get("recruiter_response_rate", 0.5))
    # JD explicitly: down-weight low response rates
    if rr >= 0.7:
        response_score = 1.0
    elif rr >= 0.5:
        response_score = 0.75
    elif rr >= 0.3:
        response_score = 0.50
    elif rr >= 0.1:
        response_score = 0.25
    else:
        response_score = 0.05  # 5% response rate → nearly useless

    # --- Interview completion rate ---
    icr = float(sig.get("interview_completion_rate", 0.5))
    interview_score = icr  # Direct: 0-1

    # --- Profile completeness ---
    pc = float(sig.get("profile_completeness_score", 50)) / 100
    profile_score = pc

    # --- GitHub activity (JD: "open-source contributions in AI/ML space") ---
    gh = float(sig.get("github_activity_score", -1))
    if gh == -1:
        github_score = 0.3  # No GitHub — neutral, not disqualifying
    else:
        github_score = gh / 100

    # --- Saved by recruiters (social proof) ---
    saved = int(sig.get("saved_by_recruiters_30d", 0))
    saved_score = min(saved / 10, 1.0)  # 10+ saves = perfect score

    # --- Notice period fit ---
    notice = int(sig.get("notice_period_days", 60))
    preferred = jd["notice_period_preferred_days"]
    if notice <= preferred:
        notice_score = 1.0
    elif notice <= 45:
        notice_score = 0.75
    elif notice <= 60:
        notice_score = 0.60
    elif notice <= 90:
        notice_score = 0.40
    else:
        notice_score = 0.20

    # Weighted combination per JD behavioral guidance
    bw = jd["behavioral_weights"]
    behavioral_score = (
        open_to_work          * bw["open_to_work"] +
        recency_score         * bw["recency"] +
        response_score        * bw["recruiter_response_rate"] +
        interview_score       * bw["interview_completion_rate"] +
        profile_score         * bw["profile_completeness"] +
        github_score          * bw["github_activity"] +
        saved_score           * bw["saved_by_recruiters_30d"] +
        notice_score          * bw["notice_period_fit"]
    )

    return {
        "behavioral_score": round(behavioral_score, 4),
        "recency_score": round(recency_score, 3),
        "open_to_work": sig.get("open_to_work_flag", False),
        "response_rate": rr,
        "response_score": round(response_score, 3),
        "notice_days": notice,
        "github_score": round(github_score, 3),
        "days_inactive": days_inactive,
    }


# ---------------------------------------------------------------------------
# Education scoring
# ---------------------------------------------------------------------------

def score_education(candidate: dict, jd: dict) -> float:
    """Score education: tier and field relevance."""
    education = candidate.get("education", [])
    if not education:
        return 0.40  # No education listed — neutral

    tier_scores = {"tier_1": 1.0, "tier_2": 0.75, "tier_3": 0.55, "tier_4": 0.35, "unknown": 0.45}
    relevant_fields = [
        "computer science", "information technology", "engineering", "mathematics",
        "statistics", "data science", "machine learning", "artificial intelligence",
        "electronics", "electrical", "physics",
    ]

    best_score = 0.0
    for edu in education:
        tier = edu.get("tier", "unknown")
        field = edu.get("field_of_study", "").lower()
        degree = edu.get("degree", "").lower()

        t_score = tier_scores.get(tier, 0.45)
        f_score = 0.5  # default
        for rf in relevant_fields:
            if rf in field:
                f_score = 1.0
                break

        # Postgrad bonus
        if any(pg in degree for pg in ["m.tech", "m.e.", "mtech", "ms", "m.s.", "phd", "ph.d", "mba"]):
            deg_bonus = 0.1
        else:
            deg_bonus = 0.0

        score = t_score * 0.6 + f_score * 0.4 + deg_bonus
        best_score = max(best_score, score)

    return round(min(best_score, 1.0), 4)


# ---------------------------------------------------------------------------
# Location scoring
# ---------------------------------------------------------------------------

def score_location(candidate: dict, jd: dict) -> float:
    """Score location fit against JD preferences."""
    profile = candidate.get("profile", {})
    location = profile.get("location", "").lower()
    country = profile.get("country", "").lower()
    willing_to_relocate = candidate.get("redrob_signals", {}).get("willing_to_relocate", False)

    location_scores = {k.lower(): v for k, v in jd["location_score"].items()}

    # Direct match
    for loc, score in location_scores.items():
        if loc in location:
            return score

    # Country match
    if "india" in country:
        base = 0.55  # In India but not preferred city
        if willing_to_relocate:
            return 0.70  # India + willing to relocate = good
        return base

    # Outside India
    if willing_to_relocate:
        return 0.30
    return 0.15


# ---------------------------------------------------------------------------
# Hard disqualification logic
# ---------------------------------------------------------------------------

def check_hard_disqualifiers(candidate: dict, jd: dict) -> Optional[str]:
    """
    Returns a disqualification reason string if candidate should be
    hard-filtered, else None.

    From JD:
    - Pure research (academic labs, research-only) without production → disqualify
    - ONLY consulting career → disqualify
    - Primary expertise CV/speech/robotics without NLP/IR → disqualify
    """
    career = candidate.get("career_history", [])
    skills = [s["name"].lower() for s in candidate.get("skills", [])]
    profile = candidate.get("profile", {})

    if not career:
        return "No career history"

    # --- Check: only consulting career ---
    consulting_flags = jd["consulting_red_flag_companies"]
    all_companies = [r.get("company", "").lower() for r in career]
    all_consulting = all(
        any(flag in co for flag in consulting_flags) for co in all_companies if co
    )
    if all_consulting and len(career) >= 2:
        return "Entire career at consulting firms"

    # --- Check: wrong domain primary (CV/speech/robotics) without NLP/IR ---
    wrong_domain_terms = ["computer vision", "object detection", "robotics", "speech recognition",
                           "image classification", "autonomous", "mechanical", "civil", "accounting",
                           "sales", "marketing", "hr manager", "content writer", "graphic design",
                           "customer support"]
    nlp_ir_terms = ["nlp", "natural language", "retrieval", "ranking", "search",
                     "recommendation", "embedding", "information retrieval", "text"]

    current_title = profile.get("current_title", "").lower()
    headline = profile.get("headline", "").lower()
    has_wrong_domain = any(t in current_title or t in headline for t in wrong_domain_terms)
    has_nlp_ir = any(t in " ".join(skills) for t in nlp_ir_terms)

    if has_wrong_domain and not has_nlp_ir:
        return f"Primary domain mismatch: {current_title}"

    return None  # No disqualifier


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_candidate(candidate: dict, jd: dict) -> Optional[dict]:
    """
    Full candidate scoring pipeline.
    Returns None if candidate is hard-disqualified.
    Returns scored dict otherwise.
    """
    # Hard filter first (cheap, fast)
    disqualifier = check_hard_disqualifiers(candidate, jd)
    if disqualifier:
        return None

    # Score all dimensions
    skill_result    = score_skills(candidate, jd)
    career_result   = score_career(candidate, jd)
    behavioral_result = score_behavioral(candidate, jd)
    edu_score       = score_education(candidate, jd)
    loc_score       = score_location(candidate, jd)

    # Weighted composite
    dw = jd["dimension_weights"]
    composite = (
        skill_result["skill_score"]          * dw["skill_match"] +
        career_result["career_score"]        * dw["career_trajectory"] +
        behavioral_result["behavioral_score"] * dw["behavioral"] +
        edu_score                            * dw["education"] +
        loc_score                            * dw["location_fit"]
    )

    # Behavioral multiplier: JD says unavailable candidates should be down-weighted
    # Don't just subtract — multiply to penalize severely unavailable candidates
    if behavioral_result["days_inactive"] > 180 and behavioral_result["response_rate"] < 0.1:
        composite *= 0.5  # Severely down-weight ghost candidates

    return {
        "candidate_id": candidate["candidate_id"],
        "composite_score": round(composite, 6),
        # Dimension breakdown (for reasoning generation)
        "skill_score": skill_result["skill_score"],
        "career_score": career_result["career_score"],
        "behavioral_score": behavioral_result["behavioral_score"],
        "edu_score": edu_score,
        "loc_score": loc_score,
        # Sub-signals (for reasoning)
        "yoe": career_result["yoe"],
        "current_title": candidate.get("profile", {}).get("current_title", ""),
        "location": candidate.get("profile", {}).get("location", ""),
        "country": candidate.get("profile", {}).get("country", ""),
        "matched_must_skills": skill_result["matched_must"],
        "matched_strong_skills": skill_result["matched_strong"],
        "category_hits": skill_result["category_hits"],
        "open_to_work": behavioral_result["open_to_work"],
        "response_rate": behavioral_result["response_rate"],
        "notice_days": behavioral_result["notice_days"],
        "days_inactive": behavioral_result["days_inactive"],
        "github_score": behavioral_result["github_score"],
        "is_mainly_consulting": career_result["is_mainly_consulting"],
        "domain_score": career_result["domain_score"],
        "trajectory_score": career_result["trajectory_score"],
        "product_score": career_result["product_score"],
    }
