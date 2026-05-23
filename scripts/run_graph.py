#!/usr/bin/env python3
"""Run the V10 LangGraph workflow for Agentic Finance RAG."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_EVIDENCE_TOP_N  # noqa: E402
from src.workflow_graph import export_graph_mermaid, run_graph_pipeline  # noqa: E402


DEFAULT_QUESTION = (
    "Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, "
    "and regulatory risk. Which bank appears riskier and what should a consultant recommend?"
)


def parse_args() -> argparse.Namespace:
    """Parse LangGraph workflow CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run the V10 LangGraph workflow for Agentic Finance RAG."
    )
    parser.add_argument(
        "--question",
        default=None,
        help="Optional non-interactive question. If omitted, the CLI prompts for one.",
    )
    parser.add_argument(
        "--planner",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Query Planner Agent. Default: true",
    )
    parser.add_argument(
        "--grade-evidence",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Evidence Grader Agent. Default: true",
    )
    parser.add_argument(
        "--repair-retrieval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Retrieval Repair Agent. Default: true",
    )
    parser.add_argument(
        "--critic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the Answer Critic Agent. Default: true",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate a Markdown report.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run deterministic evaluation.",
    )
    parser.add_argument(
        "--export-html",
        action="store_true",
        help="Export the generated report to styled HTML.",
    )
    parser.add_argument(
        "--export-pdf",
        action="store_true",
        help="Export the generated report to PDF when WeasyPrint is available.",
    )
    parser.add_argument(
        "--evidence-top-n",
        type=int,
        default=DEFAULT_EVIDENCE_TOP_N,
        help=f"Maximum kept chunks per planner task. Default: {DEFAULT_EVIDENCE_TOP_N}",
    )
    parser.add_argument(
        "--repair-top-k",
        type=int,
        default=3,
        help="Chunks to retrieve per repair query. Default: 3",
    )
    parser.add_argument(
        "--repair-max-queries",
        type=int,
        default=4,
        help="Maximum repair queries per weak task. Default: 4",
    )
    parser.add_argument(
        "--repair-min-kept",
        type=int,
        default=1,
        help="Minimum kept chunks per task before repair is skipped. Default: 1",
    )
    parser.add_argument(
        "--repair-min-score",
        type=float,
        default=0.40,
        help="Minimum best kept evidence score before repair is skipped. Default: 0.40",
    )
    parser.add_argument(
        "--report-name",
        default=None,
        help="Optional Markdown report filename.",
    )
    parser.add_argument(
        "--evaluation-name",
        default=None,
        help="Optional evaluation Markdown filename.",
    )
    parser.add_argument(
        "--export-name",
        default=None,
        help="Optional output filename stem for HTML/PDF exports.",
    )
    parser.add_argument(
        "--export-mermaid",
        action="store_true",
        help="Export the LangGraph workflow Mermaid diagram.",
    )
    parser.add_argument(
        "--mermaid-output",
        default="outputs/evaluations/v10_langgraph_workflow.mmd",
        help="Mermaid output path. Default: outputs/evaluations/v10_langgraph_workflow.mmd",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> str | None:
    """Return an error message for invalid numeric arguments."""
    if args.evidence_top_n <= 0:
        return "--evidence-top-n must be greater than 0."
    if args.repair_top_k <= 0:
        return "--repair-top-k must be greater than 0."
    if args.repair_max_queries <= 0:
        return "--repair-max-queries must be greater than 0."
    if args.repair_min_kept <= 0:
        return "--repair-min-kept must be greater than 0."
    if args.repair_min_score < 0:
        return "--repair-min-score must be non-negative."
    return None


def print_retrieval_plan(plan: list[dict] | None) -> None:
    """Print graph retrieval plan."""
    print("\nRetrieval plan:")
    if not plan:
        print("- none")
        return
    for index, task in enumerate(plan, start=1):
        print(f"{index}. {task.get('entity')} | {task.get('risk_type')} | {task.get('search_query')}")


def print_evidence_summary(summary: list[dict] | None) -> None:
    """Print graph evidence grading summary."""
    print("\nEvidence grading summary:")
    if not summary:
        print("- not used")
        return
    for item in summary:
        print(
            f"- {item.get('entity')} / {item.get('risk_type')}: "
            f"{item.get('kept', 0)} kept, {item.get('removed', 0)} removed"
        )


def print_repair_summary(summary: list[dict] | None) -> None:
    """Print graph retrieval repair summary."""
    print("\nRetrieval repair summary:")
    if not summary:
        print("- not used")
        return
    for item in summary:
        print(
            f"- {item.get('entity')} / {item.get('risk_type')}: "
            f"{item.get('status', 'unknown')} "
            f"({item.get('additional_chunks_kept', 0)} kept after repair)"
        )


def print_critic_summary(summary: dict | None) -> None:
    """Print graph critic summary."""
    print("\nAnswer critic summary:")
    if not summary:
        print("- not used")
        return
    issues = summary.get("issues", [])
    main_issue = issues[0].get("message", "None") if issues else "None"
    print(f"- passed: {str(summary.get('passed', False)).lower()}")
    print(f"- issues found: {len(issues)}")
    print(f"- main issue: {main_issue}")
    print(f"- summary: {summary.get('critic_summary', '')}")


def print_evaluation_summary(evaluation: dict | None) -> None:
    """Print graph evaluation summary."""
    print("\nEvaluation summary:")
    if not evaluation:
        print("- not used")
        return
    scores = evaluation.get("scores", {})
    for metric, score in scores.items():
        score_text = "not scored" if score is None else f"{score}/5"
        print(f"- {metric}: {score_text}")
    print(f"- overall_score: {evaluation.get('overall_score')}/5")


def print_result(result: dict) -> None:
    """Print a readable graph run summary."""
    print(f"\nRetrieval mode: {result.get('retrieval_mode', 'unknown')}")
    print_retrieval_plan(result.get("retrieval_plan"))
    print_evidence_summary(result.get("evidence_grading_summary"))
    print_repair_summary(result.get("retrieval_repair_summary"))
    print_critic_summary(result.get("critic_summary"))

    print("\nFinal answer:")
    print((result.get("final_answer") or "").strip())

    if result.get("report_path"):
        print("\nReport saved to:")
        print(result["report_path"])
    if result.get("html_report_path"):
        print("\nHTML report saved to:")
        print(result["html_report_path"])
    if result.get("pdf_report_path"):
        print("\nPDF report saved to:")
        print(result["pdf_report_path"])
    export_summary = result.get("export_summary") or {}
    if export_summary.get("pdf_error"):
        print("\nPDF export failed:")
        print(export_summary["pdf_error"])
    if result.get("evaluation_path"):
        print("\nEvaluation saved to:")
        print(result["evaluation_path"])
    print_evaluation_summary(result.get("evaluation"))

    if result.get("errors"):
        print("\nGraph warnings:")
        for error in result["errors"]:
            print(f"- {error}")


def run_once(question: str, args: argparse.Namespace) -> int:
    """Run one graph pipeline question."""
    try:
        result = run_graph_pipeline(
            question=question,
            use_planner=args.planner,
            grade_evidence=args.grade_evidence,
            repair_retrieval=args.repair_retrieval,
            use_critic=args.critic,
            generate_report=args.report,
            evaluate=args.evaluate,
            export_html=args.export_html,
            export_pdf=args.export_pdf,
            evidence_top_n=args.evidence_top_n,
            repair_top_k=args.repair_top_k,
            repair_max_queries=args.repair_max_queries,
            repair_min_kept=args.repair_min_kept,
            repair_min_score=args.repair_min_score,
            report_name=args.report_name,
            evaluation_name=args.evaluation_name,
            export_name=args.export_name,
        )
    except RuntimeError as exc:
        print(f"Graph pipeline failed: {exc}")
        return 1
    except Exception as exc:
        print(f"Graph pipeline failed: {exc}")
        return 1

    print_result(result)
    return 0


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    validation_error = validate_args(args)
    if validation_error:
        print(validation_error)
        return 1

    if args.export_mermaid:
        mermaid_path = export_graph_mermaid(args.mermaid_output)
        print("Mermaid workflow saved to:")
        print(mermaid_path)
        if not args.question:
            return 0

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Please export it before running the graph pipeline.")
        return 1

    if args.question:
        return run_once(args.question, args)

    print("Finance RAG LangGraph CLI. Ask a question, or type 'exit' to quit.")
    print(f"Default example: {DEFAULT_QUESTION}")
    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            return 0
        if not question:
            continue
        run_once(question, args)


if __name__ == "__main__":
    raise SystemExit(main())
