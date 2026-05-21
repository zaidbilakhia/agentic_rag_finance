#!/usr/bin/env python3
"""Safely delete the local Chroma vector database."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CHROMA_DIR  # noqa: E402
from src.vector_store import reset_vector_db, vector_db_exists  # noqa: E402


def main() -> int:
    if not vector_db_exists(CHROMA_DIR):
        print(f"No vector database found at {CHROMA_DIR}")
        return 0

    answer = input(f"Delete vector database at {CHROMA_DIR}? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Reset cancelled.")
        return 0

    reset_vector_db(CHROMA_DIR)
    print(f"Deleted vector database at {CHROMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

