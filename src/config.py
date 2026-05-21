"""Central configuration for the finance RAG baseline."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is optional at import time; requirements.txt includes it.
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_PDF_DIR = PROJECT_ROOT / "data" / "raw_pdfs"
CHROMA_DIR = PROJECT_ROOT / "vector_db" / "chroma"

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 6
DEFAULT_PER_SOURCE_K = 4
DEFAULT_PER_RISK_K = 2
DEFAULT_EVIDENCE_TOP_N = 2
MAX_COMPARISON_CHUNKS = 16
DEFAULT_MAX_PAGES_PER_PDF = 250
MIN_PAGE_CHARS = 250
MAX_CONTEXT_CHARS_PER_CHUNK = 1800

USEFUL_KEYWORDS = [
    "risk",
    "operational risk",
    "liquidity risk",
    "credit risk",
    "market risk",
    "regulatory",
    "regulation",
    "capital",
    "compliance",
    "cyber",
    "cybersecurity",
    "technology risk",
    "internal controls",
    "financial performance",
    "revenue",
    "profit",
    "loss",
    "strategy",
    "outlook",
    "management report",
    "Basel",
    "EBA",
    "capital requirement",
    "stress test",
]


def require_openai_api_key() -> str:
    """Return OPENAI_API_KEY or raise a clear setup error."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it before running this command:\n"
            "export OPENAI_API_KEY='your-api-key'"
        )
    return api_key
