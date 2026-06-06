# Redrob Hackathon — Intelligent Candidate Ranking

**Challenge:** Intelligent Candidate Discovery & Ranking  
**Approach:** Multi-signal deterministic ranker with semantic skill matching and behavioral multipliers

---

## Quick Start

```bash
pip install -r requirements.txt   # Nothing to install — pure Python stdlib only

python rank.py \
  --candidates ./data/candidates.jsonl \
  --out ./output/submission.csv
```

Runs in **~34 seconds** on a standard CPU with 16GB RAM. No GPU. No API calls. No network.

---

## What this system does

Most ranking systems fail at this problem in one of two ways:

1. **Keyword matchers** rank candidates who listed "RAG" and "Pinecone" as skills above candidates who actually built retrieval systems but never used those exact terms.
2. **Pure semantic embedders** rank on profile similarity without accounting for whether the candidate is actually reachable or available.

This system solves both problems with a **five-dimension deterministic scorer** that reads the JD the way an experienced recruiter would — looking for what it *means*, not just what it *says*.

---

## Architecture

```
candidates.jsonl (100K)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1-3: Deterministic Scorer (all 100K, ~34s)   │
│                                                     │
│  ① Hard Filter   — removes clearly wrong-domain     │
│                    candidates (consulting-only,      │
│                    wrong specialty) before scoring   │
│                                                     │
│  ② 5-Dimension   — parallel scoring per candidate:  │
│     Scoring         skill_match  (35%)               │
│                     career_traj  (25%)               │
│                     behavioral   (25%)               │
│                     location     (10%)               │
│                     education     (5%)               │
│                                                     │
│  ③ Composite     — weighted fusion → single 0-1     │
│     Fusion          score per candidate              │
└─────────────────────────────────────────────────────┘
        │
        ▼ top 200 candidates
┌─────────────────────────────────────────────────────┐
│  Stage 4: Reranker + Reasoning Generator            │
│                                                     │
│  ① Rerank bonus  — title alignment, GitHub signal,  │
│                    triple availability boost         │
│                                                     │
│  ② Reasoning     — specific, non-hallucinated,      │
│     Generator      rank-calibrated 1-2 sentences    │
│                    from structured candidate data    │
└─────────────────────────────────────────────────────┘
        │
        ▼
  submission.csv (top 100)
```

---

## Scoring Dimensions

### 1. Skill Match (35%)

Matches candidate skills against **5 categories** derived from the JD must-haves — not keyword lists:

| Category | What we look for |
|---|---|
| Embeddings / Retrieval | sentence-transformers, BGE, E5, dense retrieval, semantic search |
| Vector DB | FAISS, Pinecone, Weaviate, Qdrant, Milvus, OpenSearch |
| Ranking Systems | BM25, re-ranking, LTR, recommendation, hybrid search |
| Evaluation Frameworks | NDCG, MRR, MAP, A/B testing, offline eval |
| Python | Confirmed production Python |

Matching accounts for: listed skill proficiency level, endorsements, duration of use, career description text (lower weight), and Redrob platform assessment scores.

### 2. Career Trajectory (25%)

Four sub-signals:

- **Experience band fit** — 6–8 years is ideal per JD; curve penalizes far outside
- **Product vs consulting ratio** — time at product companies vs consulting firms; JD explicitly disqualifies "entire consulting career"
- **Domain relevance** — AI/ML/NLP/Search keywords in actual job descriptions (not just skills)
- **Title progression** — upward seniority movement signals growth velocity

### 3. Behavioral Signals (25%)

Directly implements the JD's advice: *"A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% response rate is, for hiring purposes, not actually available."*

| Signal | Weight | Logic |
|---|---|---|
| Recency (last active) | 20% | Active this week = 1.0; inactive 6+ months = 0.05 |
| Recruiter response rate | 20% | ≥70% = 1.0; <10% = 0.05 |
| Open to work flag | 15% | Boolean availability signal |
| Interview completion rate | 10% | Reliability proxy |
| Profile completeness | 10% | Seriousness of job search |
| GitHub activity | 10% | JD: "open-source in AI/ML space" |
| Saved by recruiters 30d | 8% | Social proof from platform |
| Notice period fit | 7% | JD: "sub-30 day notice preferred" |

**Ghost candidate penalty:** Candidates inactive >180 days AND response rate <10% receive a 0.5× multiplier on their composite score — they are deprioritized regardless of skill strength.

### 4. Location Fit (10%)

Pune and Noida score 1.0 (stated preference). Delhi NCR, Hyderabad, Mumbai, Bangalore score 0.85–0.9. Other India locations score lower. Willing-to-relocate adds a bonus.

### 5. Education (5%)

Institution tier (tier_1 → tier_4) × field relevance (CS/Engineering/Mathematics/Statistics). Low weight intentionally — JD does not emphasize this.

---

## Hard Filters

Three categories are removed before scoring (not penalised — removed):

1. **Entire consulting career** — all roles at TCS/Infosys/Wipro/Accenture/Cognizant/Capgemini etc. with no product company experience
2. **Wrong primary domain** — current title is Mechanical Engineer, HR Manager, Graphic Designer, Sales, Marketing, Customer Support, Civil Engineer etc. *without* any NLP/IR signal in their skills
3. **No career history** — profile shell with no work history

These are implemented exactly as stated in the JD's "What we explicitly do NOT want" section.

---

## The Anti-Keyword-Stuffing Design

The JD explicitly warns: *"The right answer to this JD is not 'find candidates whose skills section contains the most AI keywords.' That's a trap we've explicitly built into the dataset."*

This system defends against that trap in three ways:

1. **Category matching, not keyword counting** — we check if a candidate covers 5 semantic *categories* of requirements, not if they have N keywords. A candidate with 30 AI buzzwords but who covers only 1 category scores low.

2. **Career text validation** — skill mentions in job description text are given *half* the weight of listed skills. This means candidates who *did* the work in practice but didn't keyword-stuff their skills list still surface.

3. **Domain reality check** — a "Marketing Manager" with "RAG" in their skills list gets hard-filtered if they have no NLP/IR career signal. The title and career history must be consistent with the claimed skills.

---

## Reasoning Quality

The `reasoning` column is generated purely from structured candidate data — no templates, no hallucination. Each entry:

- References the candidate's actual current title and years of experience
- Lists specific skills that matched JD requirements (only skills actually in their profile)
- States exact behavioral signal values (response rate, notice period, days inactive)
- Acknowledges specific concerns where they exist (long notice, low response rate, consulting background)
- Tones are calibrated to rank position (rank 1–10 = confident; rank 90–100 = honest about gaps)

---

## Compute Profile

| Metric | Value |
|---|---|
| Total runtime | ~34 seconds |
| Peak memory | ~800 MB |
| API calls during ranking | 0 |
| GPU usage | None |
| External network | None |
| Python version | 3.9+ |
| Dependencies | stdlib only |

---

## File Structure

```
redrob-ranker/
├── rank.py                    # Entry point — run this
├── requirements.txt           # Empty — stdlib only
├── README.md                  # This file
├── src/
│   ├── jd_config.py           # JD analysis: weights, signals, disqualifiers
│   ├── loader.py              # Streaming JSONL reader
│   ├── scorer.py              # 5-dimension deterministic scorer
│   ├── reranker.py            # Top-200 reranker + reasoning generator
│   └── utils/
│       └── validate.py        # Output validation (mirrors official validator)
├── data/                      # Put candidates.jsonl here
└── output/                    # submission.csv written here
```

---

## Reproduce Command

```bash
python rank.py --candidates ./data/candidates.jsonl --out ./output/submission.csv
```
