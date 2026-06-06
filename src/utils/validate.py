"""
utils/validate.py — Output validation matching the official validator logic.
Run this before submitting to catch issues early.
"""

import csv
import re
from pathlib import Path

REQUIRED_HEADER = ["candidate_id", "rank", "score", "reasoning"]
CANDIDATE_ID_PATTERN = re.compile(r"^CAND_[0-9]{7}$")


def validate_output(csv_path: Path) -> list[str]:
    """
    Validate submission CSV. Returns list of error strings.
    Empty list = valid submission.
    Mirrors the logic in validate_submission.py from the challenge kit.
    """
    errors = []
    path = Path(csv_path)

    if path.suffix.lower() != ".csv":
        errors.append("Filename must use a .csv extension.")

    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                errors.append("File is empty.")
                return errors

            if header != REQUIRED_HEADER:
                errors.append(
                    f"Header must be exactly: {','.join(REQUIRED_HEADER)}\n"
                    f"Found: {','.join(header)}"
                )

            data_rows = [row for row in reader if any(cell.strip() for cell in row)]

    except UnicodeDecodeError:
        errors.append("File must be UTF-8 encoded.")
        return errors

    if len(data_rows) != 100:
        errors.append(f"Must have exactly 100 data rows, found {len(data_rows)}.")

    seen_ids = set()
    seen_ranks = set()
    by_rank = []

    for i, cells in enumerate(data_rows):
        row_num = i + 2
        if len(cells) != 4:
            errors.append(f"Row {row_num}: expected 4 columns, got {len(cells)}.")
            continue

        row = dict(zip(REQUIRED_HEADER, cells))
        cid = row["candidate_id"].strip()
        rank_s = row["rank"].strip()
        score_s = row["score"].strip()

        if not CANDIDATE_ID_PATTERN.match(cid):
            errors.append(f"Row {row_num}: invalid candidate_id '{cid}'.")
        elif cid in seen_ids:
            errors.append(f"Row {row_num}: duplicate candidate_id '{cid}'.")
        else:
            seen_ids.add(cid)

        try:
            rank = int(rank_s)
            if not 1 <= rank <= 100:
                errors.append(f"Row {row_num}: rank {rank} out of range 1-100.")
            elif rank in seen_ranks:
                errors.append(f"Row {row_num}: duplicate rank {rank}.")
            else:
                seen_ranks.add(rank)
        except ValueError:
            errors.append(f"Row {row_num}: rank must be integer.")
            rank = None

        try:
            score = float(score_s)
        except ValueError:
            errors.append(f"Row {row_num}: score must be float.")
            score = None

        if rank is not None and score is not None and cid:
            by_rank.append((rank, score, cid))

    missing = set(range(1, 101)) - seen_ranks
    if missing:
        errors.append(f"Missing ranks: {sorted(missing)}")

    by_rank.sort(key=lambda x: x[0])
    for i in range(len(by_rank) - 1):
        r1, s1, _ = by_rank[i]
        r2, s2, _ = by_rank[i + 1]
        if s1 < s2:
            errors.append(f"Score not non-increasing: rank {r1} ({s1}) < rank {r2} ({s2}).")

    return errors
