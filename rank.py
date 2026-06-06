#!/usr/bin/env python3
"""
Redrob Hackathon — Intelligent Candidate Ranking Pipeline
==========================================================
CPU-only. No API calls. Runs in <5 min on 16GB RAM for 100K candidates.

Usage:
    python rank.py --candidates ./data/candidates.jsonl --out ./output/submission.csv

Architecture:
    Stage 1: Deterministic feature extraction (all 100K candidates, fast)
    Stage 2: Rule-based hard filter + soft semantic match (no GPU needed)
    Stage 3: Weighted multi-signal fusion with dynamic JD weights
    Stage 4: Rerank top-200, generate reasoning, write CSV
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from src.loader import load_candidates_streaming
from src.jd_config import JD_PROFILE
from src.scorer import score_candidate
from src.reranker import rerank_and_explain
from src.utils.validate import validate_output


def main():
    parser = argparse.ArgumentParser(description="Redrob candidate ranker")
    parser.add_argument("--candidates", default="./data/candidates.jsonl",
                        help="Path to candidates.jsonl")
    parser.add_argument("--out", default="./output/submission.csv",
                        help="Output CSV path")
    parser.add_argument("--top-k", type=int, default=100,
                        help="Number of candidates to output (default: 100)")
    args = parser.parse_args()

    t0 = time.time()
    print(f"[rank.py] Starting pipeline...")
    print(f"[rank.py] Candidates: {args.candidates}")
    print(f"[rank.py] Output: {args.out}")

    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        print(f"ERROR: Candidates file not found: {candidates_path}", file=sys.stderr)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Stage 1+2+3: Stream all candidates, score each deterministically
    # -----------------------------------------------------------------------
    print(f"\n[Stage 1-3] Scoring all candidates (streaming)...")
    scored = []
    total = 0
    skipped_hard = 0

    for candidate in load_candidates_streaming(candidates_path):
        total += 1
        result = score_candidate(candidate, JD_PROFILE)

        if result is None:
            skipped_hard += 1
            continue

        scored.append(result)

        if total % 10000 == 0:
            elapsed = time.time() - t0
            print(f"  Processed {total:,} candidates | {len(scored):,} passed filter | {elapsed:.1f}s elapsed")

    print(f"\n[Stage 1-3] Done. Total: {total:,} | Passed: {len(scored):,} | Hard-filtered: {skipped_hard:,}")
    print(f"  Elapsed: {time.time() - t0:.1f}s")

    # -----------------------------------------------------------------------
    # Stage 4: Sort, rerank top-200, generate reasoning
    # -----------------------------------------------------------------------
    print(f"\n[Stage 4] Reranking and generating reasoning...")
    scored.sort(key=lambda x: -x["composite_score"])

    # Take top 200 for reranking (gives buffer above the required 100)
    top_200 = scored[:200]
    final_100 = rerank_and_explain(top_200, JD_PROFILE)

    # -----------------------------------------------------------------------
    # Write output CSV
    # -----------------------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Round scores first, THEN sort — so tie-breaking is applied at the rounded precision
    for row in final_100[:100]:
        row["output_score"] = round(row["composite_score"], 4)

    final_100 = sorted(
        final_100[:100],
        key=lambda x: (-x["output_score"], x["candidate_id"])
    )

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, row in enumerate(final_100, start=1):
            writer.writerow([
                row["candidate_id"],
                i,
                row["output_score"],
                row["reasoning"]
            ])

    elapsed = time.time() - t0
    print(f"\n[rank.py] Done in {elapsed:.1f}s")
    print(f"[rank.py] Output written to: {out_path}")

    # Validate
    errors = validate_output(out_path)
    if errors:
        print(f"\n⚠ Validation issues:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"✓ Submission validated successfully.")


if __name__ == "__main__":
    main()
