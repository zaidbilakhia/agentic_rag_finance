#!/usr/bin/env python3
"""Create a deterministic Markdown error analysis for V8 benchmark results."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK_DIR = PROJECT_ROOT / "outputs" / "benchmarks"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "evaluations" / (
    "v8_3_benchmark_error_analysis.md"
)
BENCHMARK_PATTERN = "v8_benchmark_results_*.json"

METRIC_LABELS = {
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


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a V8 benchmark JSON result and write a deterministic "
            "Markdown error analysis report."
        )
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "Path to a benchmark JSON file. Defaults to the latest "
            "outputs/benchmarks/v8_benchmark_results_*.json file."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH.relative_to(PROJECT_ROOT)),
        help=(
            "Path for the Markdown analysis report. Default: "
            "outputs/evaluations/v8_3_benchmark_error_analysis.md"
        ),
    )
    return parser.parse_args()


def resolve_path(path: str | Path) -> Path:
    """Resolve a path relative to the project root when needed."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def load_benchmark(path: str | Path) -> dict:
    """Load a benchmark JSON payload."""
    benchmark_path = resolve_path(path)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark JSON file not found: {benchmark_path}")
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Benchmark JSON must contain an object at the top level.")
    if not isinstance(data.get("results", []), list):
        raise ValueError("Benchmark JSON field 'results' must be a list.")
    return data


def find_latest_benchmark_json(output_dir: str | Path) -> Path:
    """Find the latest V8 benchmark JSON file by timestamped filename."""
    benchmark_dir = resolve_path(output_dir)
    matches = sorted(
        benchmark_dir.glob(BENCHMARK_PATTERN),
        key=lambda path: path.name,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(
            f"No benchmark JSON files found under {benchmark_dir} matching {BENCHMARK_PATTERN}"
        )
    return matches[0]


def numeric_score(value: Any) -> float | None:
    """Convert a score to float when possible."""
    if isinstance(value, (int, float)):
        return float(value)
    return None


def score_interpretation(score: float | int | None) -> str:
    """Return a short interpretation label for a 1-5 score."""
    if score is None:
        return "not scored"
    value = float(score)
    if value >= 4.5:
        return "strong"
    if value >= 4.0:
        return "good"
    if value >= 3.0:
        return "needs improvement"
    return "weak"


def score_text(score: Any) -> str:
    """Format a numeric score for Markdown."""
    value = numeric_score(score)
    if value is None:
        return "not scored"
    return f"{value:.1f}/5"


def markdown_escape(value: Any) -> str:
    """Escape Markdown table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def completed_results(results: list[dict]) -> list[dict]:
    """Return completed results with numeric overall scores."""
    return [
        result
        for result in results
        if result.get("status") == "completed" and numeric_score(result.get("overall_score")) is not None
    ]


def get_top_questions(results: list[dict], n: int = 3) -> list[dict]:
    """Return top questions by overall score."""
    return sorted(
        completed_results(results),
        key=lambda result: (float(result.get("overall_score", 0.0)), result.get("id", "")),
        reverse=True,
    )[:n]


def get_bottom_questions(results: list[dict], n: int = 3) -> list[dict]:
    """Return bottom questions by overall score."""
    return sorted(
        completed_results(results),
        key=lambda result: (float(result.get("overall_score", 0.0)), result.get("id", "")),
    )[:n]


def calculate_category_scores(results: list[dict]) -> list[dict]:
    """Calculate average score and question count by category."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for result in completed_results(results):
        category = result.get("category") or result.get("category_used") or "unknown"
        grouped[str(category)].append(float(result.get("overall_score")))

    rows = []
    for category in sorted(grouped):
        scores = grouped[category]
        average = round(sum(scores) / len(scores), 1)
        rows.append(
            {
                "category": category,
                "questions": len(scores),
                "average_score": average,
                "interpretation": score_interpretation(average),
            }
        )
    return sorted(rows, key=lambda row: (row["average_score"], row["category"]))


def analyze_metric_strengths(average_scores: dict) -> dict[str, list[tuple[str, float]]]:
    """Sort average metric scores into strongest and weakest lists."""
    metric_scores = [
        (metric, float(score))
        for metric, score in (average_scores or {}).items()
        if numeric_score(score) is not None
    ]
    strongest = sorted(metric_scores, key=lambda item: (item[1], item[0]), reverse=True)
    weakest = sorted(metric_scores, key=lambda item: (item[1], item[0]))
    return {"strongest": strongest, "weakest": weakest}


def extract_repair_issues(results: list[dict]) -> dict:
    """Extract retrieval repair attempts and unresolved evidence gaps."""
    rows = []
    attempted = 0
    improved = 0
    no_improvement = 0
    unresolved = []

    for result in results:
        question_id = result.get("id", "unknown")
        for item in result.get("repair_summary") or []:
            status = item.get("status", "unknown")
            if status == "not_needed":
                continue

            additional_retrieved = int(item.get("additional_chunks_retrieved") or 0)
            additional_kept = int(item.get("additional_chunks_kept") or 0)
            best_score = float(item.get("best_repaired_score") or 0.0)
            row = {
                "question_id": question_id,
                "entity": item.get("entity", "unknown"),
                "risk_type": item.get("risk_type", "unknown"),
                "status": status,
                "additional_chunks_retrieved": additional_retrieved,
                "additional_chunks_kept": additional_kept,
                "best_repaired_score": best_score,
            }
            rows.append(row)

            attempted += 1
            if status == "improved":
                improved += 1
            if status == "attempted_no_improvement":
                no_improvement += 1
            if status == "attempted_no_improvement" or additional_kept == 0 or best_score < 0.40:
                unresolved.append(row)

    return {
        "attempted": attempted,
        "improved": improved,
        "attempted_no_improvement": no_improvement,
        "rows": rows,
        "unresolved": unresolved,
    }


def infer_strength(result: dict) -> str:
    """Infer the main strength from the highest metric scores."""
    scores = result.get("scores") or {}
    ranked = sorted(
        [
            (metric, float(score))
            for metric, score in scores.items()
            if numeric_score(score) is not None
        ],
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    if not ranked:
        return "No scored strength available"

    top_metric = ranked[0][0]
    strength_map = {
        "evidence_grounding": "high evidence grounding",
        "source_transparency": "high source transparency",
        "report_quality": "high report quality",
        "comparative_reasoning": "strong comparative reasoning",
        "retrieval_completeness": "strong retrieval completeness",
        "recommendation_quality": "strong recommendation quality",
        "limitations_quality": "clear limitations handling",
        "risk_specific_reasoning": "strong risk-specific reasoning",
        "overclaiming_control": "good overclaiming control",
        "source_relevance": "strong source relevance",
    }
    return strength_map.get(top_metric, top_metric.replace("_", " "))


def common_error_patterns(results: list[dict], metric_analysis: dict, repair_issues: dict) -> list[str]:
    """Generate deterministic common error pattern bullets."""
    bullets = []
    weakness_counts = Counter(
        result.get("main_weakness")
        for result in results
        if result.get("main_weakness") and result.get("main_weakness") != "No major weakness identified"
    )
    if weakness_counts:
        weakness, count = weakness_counts.most_common(1)[0]
        bullets.append(f"{weakness} appears in {count} question(s), making it the most common weakness.")

    weakest_metrics = metric_analysis.get("weakest", [])[:3]
    if weakest_metrics:
        labels = ", ".join(METRIC_LABELS.get(metric, metric) for metric, _ in weakest_metrics)
        bullets.append(f"The weakest average metrics are {labels}.")

    critic_issues = [
        str(result.get("main_critic_issue", ""))
        for result in results
        if result.get("main_critic_issue") and result.get("main_critic_issue") != "None"
    ]
    critic_text = " ".join(critic_issues).lower()
    if "liquidity" in critic_text:
        bullets.append("Several critic notes point to unresolved liquidity-evidence gaps.")
    if "regulatory" in critic_text:
        bullets.append("Some regulatory-context answers need deeper use of regulatory evidence.")

    category_scores = calculate_category_scores(results)
    lower_categories = [row["category"] for row in category_scores if row["average_score"] < 4.0]
    if lower_categories:
        bullets.append(
            "Lower-scoring categories include "
            + ", ".join(lower_categories)
            + ", suggesting those question types need targeted improvement."
        )

    unresolved = repair_issues.get("unresolved", [])
    if unresolved:
        entities = Counter(row["entity"] for row in unresolved)
        entity_summary = ", ".join(
            f"{entity} ({count})" for entity, count in entities.most_common(3)
        )
        bullets.append(
            "Retrieval repair often detects gaps but does not always find stronger evidence; "
            f"the most frequent unresolved entities are {entity_summary}."
        )

    strongest_metrics = metric_analysis.get("strongest", [])[:2]
    if strongest_metrics:
        labels = ", ".join(METRIC_LABELS.get(metric, metric) for metric, _ in strongest_metrics)
        bullets.append(f"{labels} are consistently strong relative to the other metrics.")

    return bullets


def build_analysis(data: dict, source_path: Path) -> dict:
    """Build all derived analysis values used by the Markdown writer."""
    results = data.get("results", [])
    metric_analysis = analyze_metric_strengths(data.get("average_scores", {}))
    repair_issues = extract_repair_issues(results)
    return {
        "source_path": source_path,
        "benchmark_name": data.get("benchmark_name", "unknown"),
        "timestamp": data.get("timestamp", "unknown"),
        "questions_evaluated": data.get("questions_evaluated", len(results)),
        "questions_completed": data.get("questions_completed", len(completed_results(results))),
        "questions_failed": data.get("questions_failed", 0),
        "average_overall_score": data.get("average_overall_score"),
        "average_scores": data.get("average_scores", {}),
        "results": results,
        "top_questions": get_top_questions(results),
        "bottom_questions": get_bottom_questions(results),
        "category_scores": calculate_category_scores(results),
        "metric_analysis": metric_analysis,
        "repair_issues": repair_issues,
        "common_patterns": common_error_patterns(results, metric_analysis, repair_issues),
    }


def relative_display_path(path: Path) -> str:
    """Display a project-relative path when possible."""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def table_rows_for_questions(rows: list[dict], strength: bool) -> list[str]:
    """Render strongest or weakest question table rows."""
    rendered = []
    for index, result in enumerate(rows, start=1):
        category = result.get("category") or result.get("category_used") or "unknown"
        reason = infer_strength(result) if strength else result.get("main_weakness", "n/a")
        rendered.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    markdown_escape(result.get("id", "unknown")),
                    markdown_escape(category),
                    score_text(result.get("overall_score")),
                    markdown_escape(reason),
                ]
            )
            + " |"
        )
    return rendered


def write_markdown_report(analysis: dict, output_path: str | Path) -> Path:
    """Write the V8.3 Markdown benchmark error analysis report."""
    output = resolve_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    average_scores = analysis["average_scores"]
    metric_analysis = analysis["metric_analysis"]
    repair_issues = analysis["repair_issues"]

    strongest_metric_names = [
        METRIC_LABELS.get(metric, metric) for metric, _ in metric_analysis.get("strongest", [])[:2]
    ]
    weakest_metric_names = [
        METRIC_LABELS.get(metric, metric) for metric, _ in metric_analysis.get("weakest", [])[:2]
    ]
    top_categories = sorted(
        analysis["category_scores"], key=lambda row: (row["average_score"], row["category"]), reverse=True
    )[:3]
    lower_categories = [
        row["category"] for row in analysis["category_scores"] if row["average_score"] < 4.0
    ]
    top_category_text = (
        ", ".join(row["category"] for row in top_categories) or "the highest-scoring categories"
    )
    lower_category_text = ", ".join(lower_categories) or "the lower-scoring question categories"
    executive_summary = (
        "The benchmark shows that the system performs strongest on "
        f"{top_category_text} and on metrics such as "
        f"{', '.join(strongest_metric_names) or 'the strongest metrics'}. "
        f"It performs weaker on {lower_category_text} and on metrics such as "
        f"{', '.join(weakest_metric_names) or 'the weakest metrics'}, especially when relevant "
        "evidence remains sparse after retrieval repair."
    )

    lines = [
        "# V8.3 Benchmark Error Analysis Report",
        "",
        "## 1. Benchmark Overview",
        "",
        f"- Source benchmark file: `{relative_display_path(analysis['source_path'])}`",
        f"- Benchmark name: {markdown_escape(analysis['benchmark_name'])}",
        f"- Timestamp: {markdown_escape(analysis['timestamp'])}",
        f"- Questions evaluated: {analysis['questions_evaluated']}",
        f"- Questions completed: {analysis['questions_completed']}",
        f"- Questions failed: {analysis['questions_failed']}",
        f"- Average overall score: {score_text(analysis['average_overall_score'])}",
        "",
        "## 2. Executive Summary",
        "",
        executive_summary,
        "",
        "## 3. Strongest Questions",
        "",
        "| Rank | Question ID | Category | Score | Main Strength |",
        "|------|-------------|----------|-------|---------------|",
        *table_rows_for_questions(analysis["top_questions"], strength=True),
        "",
        "## 4. Weakest Questions",
        "",
        "| Rank | Question ID | Category | Score | Main Weakness |",
        "|------|-------------|----------|-------|---------------|",
        *table_rows_for_questions(analysis["bottom_questions"], strength=False),
        "",
        "## 5. Average Metric Performance",
        "",
        f"- Strongest metrics: {', '.join(strongest_metric_names) or 'n/a'}",
        f"- Weakest metrics: {', '.join(weakest_metric_names) or 'n/a'}",
        "",
        "| Metric | Average Score | Interpretation |",
        "|--------|---------------|----------------|",
    ]

    metric_rows = [
        (metric, score)
        for metric, score in average_scores.items()
        if numeric_score(score) is not None
    ]
    metric_rows = sorted(metric_rows, key=lambda item: (float(item[1]), item[0]), reverse=True)
    for metric, score in metric_rows:
        value = numeric_score(score)
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(METRIC_LABELS.get(metric, metric)),
                    score_text(value),
                    score_interpretation(value),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 6. Category-Level Performance",
            "",
            "| Category | Questions | Average Score | Interpretation |",
            "|----------|-----------|---------------|----------------|",
        ]
    )
    for row in analysis["category_scores"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(row["category"]),
                    str(row["questions"]),
                    score_text(row["average_score"]),
                    row["interpretation"],
                ]
            )
            + " |"
        )

    lines.extend(["", "## 7. Common Error Patterns", ""])
    for pattern in analysis["common_patterns"]:
        lines.append(f"- {pattern}")

    lines.extend(
        [
            "",
            "## 8. Retrieval Repair Analysis",
            "",
            f"- Repair attempted tasks: {repair_issues['attempted']}",
            f"- Improved tasks: {repair_issues['improved']}",
            f"- Attempted with no improvement: {repair_issues['attempted_no_improvement']}",
            f"- Unresolved evidence gap examples: {len(repair_issues['unresolved'])}",
            "",
            "| Question ID | Entity | Risk Type | Status | Additional Retrieved | Additional Kept | Best Repaired Score |",
            "|-------------|--------|-----------|--------|----------------------|------------------|---------------------|",
        ]
    )
    repair_rows = repair_issues["rows"] or []
    for row in repair_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(row["question_id"]),
                    markdown_escape(row["entity"]),
                    markdown_escape(row["risk_type"]),
                    markdown_escape(row["status"]),
                    str(row["additional_chunks_retrieved"]),
                    str(row["additional_chunks_kept"]),
                    f"{row['best_repaired_score']:.2f}",
                ]
            )
            + " |"
        )
    if not repair_rows:
        lines.append("| n/a | n/a | n/a | n/a | 0 | 0 | 0.00 |")

    lines.extend(
        [
            "",
            "## 9. Recommended Next Improvements",
            "",
            "1. Improve retrieval quality for single-bank questions.",
            "2. Improve EBA/regulatory-context evidence usage.",
            "3. Improve report risk-comparison sections.",
            "4. Add more domain-specific fallback queries.",
            "5. Consider PDF/HTML report export as V9 after benchmark analysis.",
            "",
            "## 10. Roadmap Decision",
            "",
            "Based on the benchmark, the next engineering step can be either V8.4 Retrieval "
            "Quality Improvement or V9 PDF/HTML Report Export. If the goal is model "
            "quality, prioritize V8.4. If the goal is demo and portfolio polish, prioritize V9.",
            "",
            "## 11. Limitations",
            "",
            "- This analysis depends on deterministic benchmark scores.",
            "- This is not a human finance expert review.",
            "- It does not verify financial truth outside retrieved documents.",
            "- The benchmark size is small.",
            "- Scores may vary slightly due to LLM outputs in the original benchmark runs.",
            "",
        ]
    )

    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    input_path = resolve_path(args.input) if args.input else find_latest_benchmark_json(DEFAULT_BENCHMARK_DIR)
    benchmark = load_benchmark(input_path)
    analysis = build_analysis(benchmark, input_path)
    output_path = write_markdown_report(analysis, args.output)
    print(f"Wrote benchmark error analysis: {relative_display_path(output_path)}")


if __name__ == "__main__":
    main()
