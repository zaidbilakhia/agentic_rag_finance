#!/usr/bin/env python3
"""Interactive CLI for asking questions against the finance RAG database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    DEFAULT_PER_RISK_K,
    DEFAULT_PER_SOURCE_K,
    DEFAULT_TOP_K,
    require_openai_api_key,
)
from src.rag_chain import RetrievalInfo, run_rag_answer  # noqa: E402
from src.vector_store import load_vector_store  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask questions using the finance RAG DB.")
    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of chunks to retrieve for normal retrieval. Default: {DEFAULT_TOP_K}",
    )
    parser.add_argument(
        "--per-source-k",
        type=int,
        default=DEFAULT_PER_SOURCE_K,
        help=(
            "Number of chunks to retrieve per source for comparison retrieval. "
            f"Default: {DEFAULT_PER_SOURCE_K}"
        ),
    )
    parser.add_argument(
        "--per-risk-k",
        type=int,
        default=DEFAULT_PER_RISK_K,
        help=(
            "Number of chunks to retrieve per bank/risk pair for risk-type "
            f"comparison retrieval. Default: {DEFAULT_PER_RISK_K}"
        ),
    )
    parser.add_argument(
        "--include-regulatory-context",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include EBA/Basel context for comparison questions when relevant. Default: true",
    )
    return parser.parse_args()


def source_group_label(source_file: str) -> str:
    """Create a readable source group from the source file name."""
    lowered = source_file.lower()
    if "deutsche" in lowered:
        return "Deutsche Bank"
    if "commerzbank" in lowered or "commerz" in lowered:
        return "Commerzbank"
    if "eba" in lowered:
        return "EBA"
    if "basel" in lowered:
        return "Basel"
    return source_file


def print_sources(documents) -> None:
    grouped_pages: dict[str, list[int | str]] = {}
    seen_pages = set()

    for doc in documents:
        source_file = doc.metadata.get("source_file", "unknown")
        page_number = doc.metadata.get("page_number", "unknown")
        group = source_group_label(source_file)
        key = (group, page_number)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        grouped_pages.setdefault(group, []).append(page_number)

    print("\nRetrieved Sources:")
    for group, pages in grouped_pages.items():
        print(f"{group}:")
        for page_number in pages:
            print(f"- page {page_number}")


def print_retrieval_log(retrieval_info: RetrievalInfo) -> None:
    """Print the retrieval mode and chunk counts before the LLM call."""
    print(f"\nRetrieval mode: {retrieval_info.mode}")
    if retrieval_info.counts_by_entity_and_risk:
        print("Chunks retrieved:")
        for entity, risk_counts in retrieval_info.counts_by_entity_and_risk.items():
            print(f"{entity}:")
            for risk_type, count in risk_counts.items():
                print(f"- {risk_type}: {count}")
        if retrieval_info.regulatory_context_count:
            print("EBA:")
            print(f"- regulatory context: {retrieval_info.regulatory_context_count}")
        return

    print("Chunks retrieved per source:")
    if not retrieval_info.counts_by_source:
        print("- none: 0")
        return

    grouped_counts: dict[str, int] = {}
    for source_file, count in retrieval_info.counts_by_source.items():
        group = source_group_label(source_file)
        grouped_counts[group] = grouped_counts.get(group, 0) + count

    for group, count in grouped_counts.items():
        print(f"- {group}: {count}")


def main() -> int:
    args = parse_args()
    if args.k <= 0:
        print("--k must be greater than 0.")
        return 1
    if args.per_source_k <= 0:
        print("--per-source-k must be greater than 0.")
        return 1
    if args.per_risk_k <= 0:
        print("--per-risk-k must be greater than 0.")
        return 1

    try:
        require_openai_api_key()
        vector_store = load_vector_store()
    except Exception as exc:
        print(f"Startup failed: {exc}")
        return 1

    print("Finance RAG CLI. Ask a question, or type 'exit' to quit.")

    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            return 0
        if not question:
            continue

        try:
            answer, documents, _retrieval_info = run_rag_answer(
                vector_store,
                question,
                k=args.k,
                per_source_k=args.per_source_k,
                per_risk_k=args.per_risk_k,
                include_regulatory_context=args.include_regulatory_context,
                retrieval_log_callback=print_retrieval_log,
            )
        except Exception as exc:
            print(f"Question failed: {exc}")
            continue

        print("\n" + answer.strip())
        print_sources(documents)


if __name__ == "__main__":
    raise SystemExit(main())
