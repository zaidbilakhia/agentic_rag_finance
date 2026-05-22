#!/usr/bin/env python3
"""Interactive CLI for asking questions against the finance RAG database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    DEFAULT_EVIDENCE_TOP_N,
    DEFAULT_PER_RISK_K,
    DEFAULT_PER_SOURCE_K,
    DEFAULT_TOP_K,
    require_openai_api_key,
)
from src.evaluation_agent import evaluate_run, save_evaluation_markdown  # noqa: E402
from src.rag_chain import RetrievalInfo, run_rag_answer  # noqa: E402
from src.report_generator import collect_sources_from_documents, generate_report  # noqa: E402
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
    parser.add_argument(
        "--planner",
        action="store_true",
        help="Use the V1 query planner agent for structured retrieval.",
    )
    parser.add_argument(
        "--grade-evidence",
        action="store_true",
        help="Use the V2 evidence grader after planner retrieval.",
    )
    parser.add_argument(
        "--evidence-top-n",
        type=int,
        default=DEFAULT_EVIDENCE_TOP_N,
        help=(
            "Maximum kept chunks per planner task after evidence grading. "
            f"Default: {DEFAULT_EVIDENCE_TOP_N}"
        ),
    )
    parser.add_argument(
        "--critic",
        action="store_true",
        help="Use the V3 answer critic to self-check and improve the final answer.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Save a V4 professional Markdown report under outputs/reports.",
    )
    parser.add_argument(
        "--report-name",
        default=None,
        help="Optional report filename to save under outputs/reports.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run the V5 evaluation agent and save a benchmark report.",
    )
    parser.add_argument(
        "--evaluation-name",
        default=None,
        help="Optional evaluation filename to save under outputs/evaluations.",
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

    if retrieval_info.planner_tasks is not None:
        print("\nGenerated retrieval plan:")
        if not retrieval_info.planner_tasks:
            print("- No structured planner tasks generated; falling back to normal retrieval.")
        else:
            for index, task in enumerate(retrieval_info.planner_tasks, start=1):
                print(
                    f"{index}. {task['entity']} | {task['risk_type']} | "
                    f"{task['search_query']}"
                )

        print("\nChunks retrieved:")
        if not retrieval_info.counts_by_task:
            print("- none: 0")
        else:
            for item in retrieval_info.counts_by_task:
                print(
                    f"- {item['entity']} / {item['risk_type']}: "
                    f"{item['count']}"
                )

        if retrieval_info.evidence_grading_summary:
            print("\nEvidence grading summary:")
            for task_summary in retrieval_info.evidence_grading_summary:
                print(
                    f"- {task_summary['entity']} / {task_summary['risk_type']}: "
                    f"{task_summary['kept']} kept, {task_summary['removed']} removed"
                )
                for item in task_summary["items"]:
                    status = "kept" if item["keep"] else "removed"
                    print(
                        f"  - {item['relevance']} | {item['score']:.2f} | "
                        f"page {item['page']} | {status}"
                    )
        return

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


def print_critic_summary(retrieval_info: RetrievalInfo) -> None:
    """Print answer critic metadata after the critic has reviewed the draft."""
    if not retrieval_info.critic_result:
        return

    issues = retrieval_info.critic_result.get("issues", [])
    main_issue = issues[0].get("message", "None") if issues else "None"

    print("\nAnswer critic summary:")
    print(f"- passed: {str(retrieval_info.critic_result.get('passed', False)).lower()}")
    print(f"- issues found: {len(issues)}")
    print(f"- main issue: {main_issue}")
    print(f"- summary: {retrieval_info.critic_result.get('critic_summary', '')}")


def print_evaluation_summary(evaluation: dict) -> None:
    """Print V5 metric scores."""
    labels = {
        "retrieval_completeness": "Retrieval Completeness",
        "source_relevance": "Source Relevance",
        "evidence_grounding": "Evidence Grounding",
        "comparative_reasoning": "Comparative Reasoning",
        "risk_specific_reasoning": "Risk-Specific Reasoning",
        "overclaiming_control": "Overclaiming Control",
        "recommendation_quality": "Recommendation Quality",
        "limitations_quality": "Limitations Quality",
        "source_transparency": "Source Transparency",
        "report_quality": "Report Quality",
    }
    print("\nEvaluation summary:")
    for key, label in labels.items():
        score = evaluation["scores"].get(key)
        score_text = "not scored" if score is None else f"{score}/5"
        print(f"- {label}: {score_text}")
    print(f"- Overall Score: {evaluation['overall_score']}/5")


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
    if args.evidence_top_n <= 0:
        print("--evidence-top-n must be greater than 0.")
        return 1
    if args.grade_evidence and not args.planner:
        print("--grade-evidence requires --planner.")
        return 1
    if args.critic and not args.planner:
        print("Warning: Answer critic is most useful with --planner and --grade-evidence.")

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
                use_planner=args.planner,
                grade_evidence=args.grade_evidence,
                evidence_top_n=args.evidence_top_n,
                use_critic=args.critic,
                retrieval_log_callback=print_retrieval_log,
            )
        except Exception as exc:
            print(f"Question failed: {exc}")
            continue

        if args.critic:
            print_critic_summary(_retrieval_info)
            print("\nFinal answer:")
            print(answer.strip())
        else:
            print("\n" + answer.strip())
        print_sources(documents)

        sources = collect_sources_from_documents(documents)
        report_path = None
        report_content = None

        if args.report:
            report_path = generate_report(
                question=question,
                final_answer=answer,
                retrieval_plan=_retrieval_info.planner_tasks,
                retrieval_summary=_retrieval_info.counts_by_task
                or _retrieval_info.counts_by_source,
                evidence_summary=_retrieval_info.evidence_grading_summary,
                critic_summary=_retrieval_info.critic_result,
                sources=sources,
                report_name=args.report_name,
            )
            report_content = (PROJECT_ROOT / report_path).read_text(encoding="utf-8")
            print("\nReport saved to:")
            print(report_path)

        if args.evaluate:
            evaluation = evaluate_run(
                question=question,
                final_answer=answer,
                retrieval_plan=_retrieval_info.planner_tasks,
                retrieval_summary=_retrieval_info.counts_by_task
                or _retrieval_info.counts_by_source,
                evidence_summary=_retrieval_info.evidence_grading_summary,
                critic_summary=_retrieval_info.critic_result,
                sources=sources,
                report_path=report_path,
                report_content=report_content,
            )
            evaluation_path = save_evaluation_markdown(
                evaluation,
                evaluation_name=args.evaluation_name,
            )
            print_evaluation_summary(evaluation)
            print("\nEvaluation saved to:")
            print(evaluation_path)


if __name__ == "__main__":
    raise SystemExit(main())
