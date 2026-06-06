"""
loader.py — Memory-efficient streaming loader for candidates.jsonl

Reads 100K candidates one line at a time without loading into memory.
"""

import json
from pathlib import Path
from typing import Iterator


def load_candidates_streaming(path: Path) -> Iterator[dict]:
    """
    Stream candidates from a .jsonl file one by one.
    Never loads the full file into memory.
    """
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                # Skip malformed lines without crashing the pipeline
                import sys
                print(f"  [loader] Skipping malformed line {line_num}: {e}", file=sys.stderr)
                continue


def load_candidates_batch(path: Path, batch_size: int = 1000) -> Iterator[list]:
    """
    Stream candidates in batches (useful for parallel processing if needed).
    """
    batch = []
    for candidate in load_candidates_streaming(path):
        batch.append(candidate)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
