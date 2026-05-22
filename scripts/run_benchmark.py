#!/usr/bin/env python3
"""Run a multi-question benchmark for the Agentic Finance RAG pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_EVIDENCE_TOP_N, require_openai_api_key  # noqa: E402
from src.evaluation_agent import METRIC_LABELS  # noqa: E402
from src.rag_chain import run_rag_pipeline  # noqa: E402


DEFAULT_QUESTIONS_PATH = PROJECT_ROOT / "data" / "evaluation_questions.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "benchmarks"
BENCHMARK_NAME = "V8 Multi-Question Benchmark"


def parse_args() -> argparse.Namespace:
    """Parse benchmark runner arguments."""
    parser = argparse.ArgumentParser(
        description="Run the V8 multi-question benchmark for Agentic Finance RAG."
    )
    parser.add_argument(
        "--questions",
        default=str(DEFAULT_QUESTIONS_PATH),
        help="Path to benchmark question JSON file. Default: data/evaluation_questions.json",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for benchmark JSON and Markdown outputs. Default: outputs/benchmarks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of questions to evaluate.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Do not generate individual per-question Markdown reports.",
    )
    parser.add_argument(
        "--skip-evaluation",
        action="store_true",
        help="Do not run the V5 evaluation agent.",
    )
    parser.add_argument(
        "--evidence-top-n",
        type=int,
        default=DEFAULT_EVIDENCE_TOP_N,
        help=f"Maximum kept chunks per planner task after grading. Default: {DEFAULT_EVIDENCE_TOP_N}",
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
    return parser.parse_args()


def load_questions(path: str | Path, limit: int | None = None) -> list[dict]:
    """Load benchmark questions from JSON."""
    questions_path = Path(path)
    if not questions_path.is_absolute():
        questions_path = PROJECT_ROOT / questions_path
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    if not isinstance(questions, list):
        raise ValueError("Benchmark question file must contain a JSON list.")
    if limit is not None:
        if limit <= 0:
            raise ValueError("--limit must be greater than 0 when provided.")
        return questions[:limit]
    return questions


def safe_name(value: str) -> str:
    """Create a filesystem-friendly stem for generated report/evaluation names."""
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return safe.strip("_") or "benchmark_question"


def main_critic_issue(critic_summary: dict | None) -> str:
    """Return the first critic issue message if available."""
    issues = (critic_summary or {}).get("issues", [])
    if not issues:
        return "None"
    return issues[0].get("message", "None")


def main_weakness(evaluation: dict | None, error: str | None = None) -> str:
    """Return a compact weakness label for benchmark tables."""
    if error:
        return error
    weaknesses = (evaluation or {}).get("weaknesses", [])
    if weaknesses:
        return weaknesses[0]
    return "No major weakness identified"


def compact_question_result(question_item: dict, pipeline_result: dict) -> dict:
    """Keep only benchmark-relevant fields from one successful pipeline run."""
    evaluation = pipeline_result.get("evaluation") or {}
    return {
        "id": question_item.get("id", "unknown"),
        "question": question_item.get("question", ""),
        "category": question_item.get("category", "unknown"),
        "expected_focus": question_item.get("expected_focus", []),
        "status": "completed",
        "overall_score": evaluation.get("overall_score"),
        "scores": evaluation.get("scores", {}),
        "report_path": pipeline_result.get("report_path"),
        "evaluation_path": pipeline_result.get("evaluation_path"),
        "main_critic_issue": main_critic_issue(pipeline_result.get("critic_summary")),
        "main_weakness": main_weakness(evaluation),
        "repair_summary": pipeline_result.get("retrieval_repair_summary") or [],
        "retrieval_mode": pipeline_result.get("retrieval_mode"),
    }


def failed_question_result(question_item: dict, error: Exception) -> dict:
    """Create a benchmark result for a failed question without stopping the run."""
    return {
        "id": question_item.get("id", "unknown"),
        "question": question_item.get("question", ""),
        "category": question_item.get("category", "unknown"),
        "status": "failed",
        "error": str(error),
        "overall_score": None,
        "scores": {},
        "report_path": None,
        "evaluation_path": None,
        "main_critic_issue": "n/a",
        "main_weakness": main_weakness(None, str(error)),
        "repair_summary": [],
    }


def average_numeric(values: list[Any]) -> float | None:
    """Average numeric values, returning None when none are available."""
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 1)


def calculate_average_scores(results: list[dict]) -> dict[str, float | None]:
    """Calculate average score for each V5 metric."""
    averages = {}
    for metric in METRIC_LABELS:
        averages[metric] = average_numeric(
            [result.get("scores", {}).get(metric) for result in results]
        )
    return averages


def build_benchmark_payload(results: list[dict], timestamp: str) -> dict:
    """Build the final benchmark JSON payload."""
    completed = [result for result in results if result.get("status") == "completed"]
    return {
        "benchmark_name": BENCHMARK_NAME,
        "timestamp": timestamp,
        "questions_evaluated": len(results),
        "questions_completed": len(completed),
        "questions_failed": len(results) - len(completed),
        "average_overall_score": average_numeric(
            [result.get("overall_score") for result in completed]
        ),
        "average_scores": calculate_average_scores(completed),
        "results": results,
    }


def score_text(score: Any) -> str:
    """Format a score for Markdown and terminal output."""
    if score is None:
        return "not scored"
    return f"{float(score):.1f}/5"


def markdown_link_or_text(path: str | None) -> str:
    """Render a relative path as a Markdown link when present."""
    if not path:
        return "n/a"
    return f"[{Path(path).name}](../../{path})"


def markdown_escape(value: Any) -> str:
    """Escape Markdown table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def save_benchmark_json(payload: dict, output_dir: str | Path, timestamp: str) -> str:
    """Save benchmark JSON and return relative path."""
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"v8_benchmark_results_{timestamp}.json"
    file_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return relative_path(file_path)


def save_benchmark_markdown(payload: dict, output_dir: str | Path, timestamp: str) -> str:
    """Save benchmark Markdown summary and return relative path."""
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"v8_benchmark_results_{timestamp}.md"

    average_rows = [
        f"| {label} | {score_text(payload['average_scores'].get(metric))} |"
        for metric, label in METRIC_LABELS.items()
    ]
    result_rows = []
    for result in payload["results"]:
        result_rows.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(result.get("id", "unknown")),
                    markdown_escape(result.get("category", "unknown")),
                    score_text(result.get("overall_score")),
                    markdown_escape(result.get("main_weakness", "")),
                    markdown_link_or_text(result.get("report_path")),
                    markdown_link_or_text(result.get("evaluation_path")),
                ]
            )
            + " |"
        )

    content = f"""# V8 Multi-Question Benchmark Report

## 1. Benchmark Summary

- Questions evaluated: {payload['questions_evaluated']}
- Questions completed: {payload['questions_completed']}
- Questions failed: {payload['questions_failed']}
- Average overall score: {score_text(payload['average_overall_score'])}
- Pipeline used:
  - Query Planner Agent
  - Evidence Grader Agent
  - Retrieval Repair Agent
  - Answer Critic Agent
  - Report Generator Agent
  - Evaluation Agent

## 2. Average Metric Scores

| Metric | Average Score |
|---|---|
{chr(10).join(average_rows)}

## 3. Per-Question Results

| ID | Category | Overall Score | Main Weakness | Report | Evaluation |
|---|---|---|---|---|---|
{chr(10).join(result_rows)}

## 4. Observed Strengths

- The benchmark runner exercises the full Agentic RAG pipeline across multiple question categories.
- Successful runs preserve report and evaluation artifacts for inspection.
- The V5 evaluator provides consistent metric scores for comparing question-level behavior.
- Missing or weak evidence can be surfaced through repair summaries and evaluation weaknesses.

## 5. Observed Weaknesses

- Some tasks may still have weak or missing evidence after retrieval repair.
- Retrieval repair may not always find stronger evidence if the vector database lacks relevant chunks.
- Report risk comparison sections may remain generic for some question shapes.
- The current deterministic evaluator is useful for consistency but not a substitute for expert review.

## 6. Recommendations for Next Iteration

- Improve question-specific query planning for single-bank and single-risk questions.
- Add more domain-specific fallback queries for liquidity, capital, and regulatory evidence.
- Add stricter benchmark scoring once more labeled expectations are available.
- Expand the benchmark dataset with more banks, more reports, and more regulation-focused questions.

## 7. Benchmark Limitations

- The benchmark dataset is intentionally small.
- Evaluation is deterministic and heuristic.
- This is not a human expert review.
- The benchmark does not verify financial truth outside retrieved sources.
- The benchmark output is not investment advice.
"""
    file_path.write_text(content.strip() + "\n", encoding="utf-8")
    return relative_path(file_path)


def relative_path(path: Path) -> str:
    """Return path relative to the project root when possible."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_benchmark(args: argparse.Namespace) -> tuple[dict, str, str]:
    """Run the configured benchmark and save JSON/Markdown outputs."""
    questions = load_questions(args.questions, args.limit)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    for index, question_item in enumerate(questions, start=1):
        question_id = question_item.get("id", f"question_{index}")
        print(f"\n[{index}/{len(questions)}] Running {question_id}...")
        try:
            pipeline_result = run_rag_pipeline(
                question=question_item["question"],
                use_planner=True,
                grade_evidence=True,
                repair_retrieval=True,
                use_critic=True,
                generate_report=not args.skip_report,
                evaluate=not args.skip_evaluation,
                evidence_top_n=args.evidence_top_n,
                repair_top_k=args.repair_top_k,
                repair_max_queries=args.repair_max_queries,
                repair_min_kept=args.repair_min_kept,
                repair_min_score=args.repair_min_score,
                report_name=f"v8_{safe_name(question_id)}_report.md",
                evaluation_name=f"v8_{safe_name(question_id)}_evaluation.md",
            )
            result = compact_question_result(question_item, pipeline_result)
            results.append(result)
            print(f"Completed {question_id}: {score_text(result.get('overall_score'))}")
        except Exception as exc:  # Keep the benchmark moving across failures.
            result = failed_question_result(question_item, exc)
            results.append(result)
            print(f"Failed {question_id}: {exc}")

    payload = build_benchmark_payload(results, timestamp)
    json_path = save_benchmark_json(payload, args.output_dir, timestamp)
    markdown_path = save_benchmark_markdown(payload, args.output_dir, timestamp)
    return payload, json_path, markdown_path


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    try:
        require_openai_api_key()
    except RuntimeError:
        print("OPENAI_API_KEY is not set. Please export it before running the benchmark.")
        return 1

    try:
        payload, json_path, markdown_path = run_benchmark(args)
    except Exception as exc:
        print(f"Benchmark startup failed: {exc}")
        return 1

    print("\nBenchmark completed.")
    print(f"Questions evaluated: {payload['questions_evaluated']}")
    print(f"Average overall score: {score_text(payload['average_overall_score'])}")
    print("\nResults saved to:")
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
