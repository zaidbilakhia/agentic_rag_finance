"""V5 deterministic evaluation agent for finance RAG runs."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT


DEFAULT_EVALUATION_DIR = PROJECT_ROOT / "outputs" / "evaluations"

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

EXPECTED_TASKS = {
    ("Deutsche Bank", "operational risk"),
    ("Deutsche Bank", "liquidity risk"),
    ("Deutsche Bank", "regulatory risk"),
    ("Commerzbank", "operational risk"),
    ("Commerzbank", "liquidity risk"),
    ("Commerzbank", "regulatory risk"),
    ("EBA", "regulatory context"),
}

REPORT_SECTIONS = [
    "Question",
    "Executive Summary",
    "Agentic RAG Pipeline Used",
    "Generated Retrieval Plan",
    "Retrieval Summary",
    "Evidence Grading Summary",
    "Risk Comparison",
    "Consultant Recommendation",
    "Answer Critic Review",
    "Sources",
    "Limitations",
    "Confidence",
]


def normalize_text(text: str) -> str:
    """Normalize text for simple deterministic scoring."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def sanitize_evaluation_name(evaluation_name: str | None) -> str:
    """Return a safe markdown filename under outputs/evaluations."""
    if not evaluation_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"evaluation_{timestamp}.md"

    name = Path(evaluation_name).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not name:
        name = "evaluation"
    if not name.lower().endswith(".md"):
        name += ".md"
    return name


def task_key(task: dict) -> tuple[str, str]:
    """Create a comparable key for a retrieval task."""
    return (task.get("entity", "unknown"), task.get("risk_type", "unknown"))


def retrieval_count_map(retrieval_summary: Any) -> dict[tuple[str, str], int]:
    """Normalize retrieval summary into task-level counts."""
    counts: dict[tuple[str, str], int] = {}
    if isinstance(retrieval_summary, list):
        for item in retrieval_summary:
            counts[(item.get("entity", "unknown"), item.get("risk_type", "unknown"))] = int(
                item.get("count", 0)
            )
    return counts


def score_retrieval_completeness(
    retrieval_plan: list[dict] | None,
    retrieval_summary: Any,
    repair_summary: list[dict] | None = None,
) -> tuple[int, str]:
    """Score whether retrieval covered the expected banks, risks, and EBA task."""
    planned = {task_key(task) for task in retrieval_plan or []}
    counts = retrieval_count_map(retrieval_summary)
    expected_planned = EXPECTED_TASKS.intersection(planned)
    expected_with_chunks = {key for key in EXPECTED_TASKS if counts.get(key, 0) > 0}

    unresolved_repairs = [
        item for item in repair_summary or []
        if item.get("status") in {"attempted_no_improvement", "failed"}
    ]

    if EXPECTED_TASKS.issubset(planned) and EXPECTED_TASKS.issubset(expected_with_chunks) and not unresolved_repairs:
        return 5, "All expected planner tasks were created and retrieved chunks."
    if unresolved_repairs:
        return 4, "Expected tasks were planned, but at least one evidence gap remained after repair."
    if EXPECTED_TASKS.issubset(planned) and len(expected_with_chunks) >= 6:
        return 4, "All expected tasks were planned with one weak or missing retrieval area."
    if len(expected_planned) >= 4:
        return 3, "Several expected tasks were planned, but important gaps remain."
    if planned:
        return 2, "Retrieval was structured but missed major expected entities or risks."
    return 1, "Retrieval was not structured or expected tasks were mostly missing."


def score_source_relevance(
    evidence_summary: list[dict] | None,
    repair_summary: list[dict] | None = None,
) -> tuple[int, str]:
    """Score relevance using evidence-grading output."""
    if not evidence_summary:
        return 3, "Evidence grading was not available, so source relevance is only acceptable by default."

    kept_items = []
    removed_low = 0
    for task in evidence_summary:
        for item in task.get("items", []):
            if item.get("keep"):
                kept_items.append(item)
            elif item.get("relevance") == "low":
                removed_low += 1

    if not kept_items:
        return 2, "No kept graded evidence was found."

    unresolved_repairs = [
        item for item in repair_summary or []
        if item.get("status") in {"attempted_no_improvement", "failed"}
    ]
    high_count = sum(1 for item in kept_items if item.get("relevance") == "high")
    high_ratio = high_count / len(kept_items)
    if unresolved_repairs:
        return 3, "Some low-relevance or missing evidence remained unresolved after repair."
    if high_ratio >= 0.75:
        return 5, "Most kept chunks are high relevance."
    if high_ratio >= 0.40 and removed_low > 0:
        return 4, "Kept evidence mixes high and medium relevance, and low evidence was removed."
    if high_ratio >= 0.20:
        return 3, "Kept evidence contains many medium chunks."
    return 2, "Kept evidence has limited high-relevance support."


def score_evidence_grounding(final_answer: str, sources: dict | None) -> tuple[int, str]:
    """Score whether the answer is source-grounded and avoids unsupported certainty."""
    text = normalize_text(final_answer)
    has_sources = bool(sources)
    mentions_missing = "insufficient" in text or "missing" in text
    cautious = "retrieved evidence" in text or "based on" in text
    definitive = "definitely riskier" in text or "clearly safer" in text

    if has_sources and cautious and mentions_missing and not definitive:
        return 5, "Answer is cautious, source-backed, and mentions missing evidence."
    if has_sources and cautious and not definitive:
        return 4, "Answer is grounded in sources and uses careful language."
    if has_sources:
        return 3, "Answer has sources but grounding language is limited."
    if definitive:
        return 2, "Answer appears to overclaim without visible source grounding."
    return 2, "Source grounding is weak or not visible."


def score_comparative_reasoning(final_answer: str) -> tuple[int, str]:
    """Score direct comparison between Deutsche Bank and Commerzbank."""
    text = normalize_text(final_answer)
    has_both = "deutsche bank" in text and "commerzbank" in text
    risk_mentions = sum(
        1 for risk in ["operational risk", "liquidity risk", "regulatory risk"] if risk in text
    )
    uncertainty = "uncertainty" in text or "not a definitive" in text
    compare_terms = "compared" in text or "comparison" in text or "appears" in text

    if has_both and risk_mentions == 3 and uncertainty and compare_terms:
        return 5, "Answer directly compares both banks across all requested risks with uncertainty."
    if has_both and risk_mentions >= 2 and compare_terms:
        return 4, "Answer compares both banks but some risk comparison detail could be stronger."
    if has_both:
        return 3, "Answer discusses both banks but comparison is somewhat shallow."
    return 1, "Answer does not clearly compare both banks."


def score_risk_specific_reasoning(final_answer: str) -> tuple[int, str]:
    """Score separation of operational, liquidity, and regulatory risk."""
    text = normalize_text(final_answer)
    risks = ["operational risk", "liquidity risk", "regulatory risk"]
    count = sum(1 for risk in risks if risk in text)
    if count == 3 and all(risk.title() in final_answer for risk in risks):
        return 5, "All three requested risk categories are clearly separated and discussed."
    if count == 3:
        return 4, "All three risk categories are addressed."
    if count == 2:
        return 3, "Two requested risk categories are addressed."
    if count == 1:
        return 2, "Only one requested risk category is addressed."
    return 1, "Risk discussion is generic."


def score_overclaiming_control(final_answer: str) -> tuple[int, str]:
    """Score cautious treatment of risk ranking and evidence limits."""
    text = normalize_text(final_answer)
    positive_markers = [
        "based on the retrieved evidence",
        "retrieved and graded evidence",
        "higher uncertainty",
        "not a definitive risk ranking",
        "disclosure",
        "retrieval limitations",
    ]
    negative_markers = ["definitely riskier", "clearly safer", "is safer", "is riskier"]
    positives = sum(1 for marker in positive_markers if marker in text)
    negatives = sum(1 for marker in negative_markers if marker in text)
    if negatives == 0 and positives >= 4:
        return 5, "Answer strongly controls overclaiming and separates evidence limits."
    if negatives == 0 and positives >= 2:
        return 4, "Answer uses careful comparative language."
    if negatives == 0:
        return 3, "Answer avoids strong overclaims but could state limitations more clearly."
    if positives:
        return 2, "Answer contains some caution but also potentially overclaims."
    return 1, "Answer appears to overclaim without adequate caveats."


def score_recommendation_quality(final_answer: str) -> tuple[int, str]:
    """Score practical consulting recommendation quality."""
    text = normalize_text(final_answer)
    markers = [
        "further due diligence",
        "lcr",
        "nsfr",
        "stress test",
        "capital ratio",
        "capital ratios",
        "operational loss",
        "regulatory findings",
        "interview",
        "risk team",
    ]
    hits = sum(1 for marker in markers if marker in text)
    if hits >= 6:
        return 5, "Recommendation includes strong due diligence and quantitative checks."
    if hits >= 4:
        return 4, "Recommendation is practical and includes quantitative indicators."
    if hits >= 2:
        return 3, "Recommendation is acceptable but could be more specific."
    if hits == 1:
        return 2, "Recommendation is thin."
    return 1, "Recommendation lacks practical consulting next steps."


def score_limitations_quality(final_answer: str, report_content: str | None = None) -> tuple[int, str]:
    """Score clarity of limitations."""
    text = normalize_text((final_answer or "") + "\n" + (report_content or ""))
    markers = [
        "based only on retrieved evidence",
        "missing commerzbank liquidity evidence",
        "disclosure detail is not the same as actual risk",
        "not a definitive",
        "not a credit",
        "not investment advice",
        "not a supervisory rating",
    ]
    hits = sum(1 for marker in markers if marker in text)
    if hits >= 4:
        return 5, "Limitations are explicit and cover evidence, disclosure, and rating limits."
    if hits >= 3:
        return 4, "Limitations are clear."
    if hits >= 2:
        return 3, "Limitations are present but could be stronger."
    if hits == 1:
        return 2, "Limitations are minimal."
    return 1, "Limitations are missing or unclear."


def score_source_transparency(sources: dict | None, final_answer: str) -> tuple[int, str]:
    """Score source filename and page transparency."""
    has_source_pages = bool(sources) and any(pages for pages in sources.values())
    text = normalize_text(final_answer)
    answer_mentions_sources = ".pdf" in text and "page" in text
    if has_source_pages and answer_mentions_sources:
        return 5, "Source filenames and pages are visible in answer/output metadata."
    if has_source_pages:
        return 4, "Source filenames and pages are available in retrieved source metadata."
    if ".pdf" in text:
        return 3, "Source filenames are visible but pages may be incomplete."
    return 1, "Sources are vague or missing."


def score_report_quality(report_content: str | None) -> tuple[int | None, str]:
    """Score report completeness if a report exists."""
    if not report_content:
        return None, "Report quality was not scored because no report was generated."

    text = normalize_text(report_content)
    present = sum(1 for section in REPORT_SECTIONS if normalize_text(section) in text)
    if present >= 11:
        return 5, "Report includes nearly all expected professional sections."
    if present >= 9:
        return 4, "Report includes most expected sections."
    if present >= 7:
        return 3, "Report is usable but missing several expected sections."
    if present >= 4:
        return 2, "Report is incomplete."
    return 1, "Report is mostly missing required structure."


def calculate_overall_score(scores: dict[str, int | None]) -> float:
    """Average numeric scores, excluding None."""
    numeric_scores = [score for score in scores.values() if isinstance(score, int)]
    if not numeric_scores:
        return 0.0
    return round(sum(numeric_scores) / len(numeric_scores), 1)


def build_pipeline_metadata(
    retrieval_plan: list[dict] | None,
    evidence_summary: list[dict] | None,
    repair_summary: list[dict] | None,
    critic_summary: dict | None,
    report_path: str | None,
) -> dict:
    """Return booleans for active pipeline components."""
    return {
        "planner_used": bool(retrieval_plan),
        "evidence_grader_used": bool(evidence_summary),
        "retrieval_repair_used": bool(repair_summary),
        "critic_used": bool(critic_summary),
        "report_generated": bool(report_path),
        "report_path": report_path,
    }


def evaluate_run(
    question: str,
    final_answer: str,
    retrieval_plan: list[dict] | None = None,
    retrieval_summary: Any | None = None,
    evidence_summary: list[dict] | None = None,
    graded_evidence: list[dict] | None = None,
    critic_summary: dict | None = None,
    sources: dict | None = None,
    report_path: str | None = None,
    report_content: str | None = None,
    repair_summary: list[dict] | None = None,
) -> dict:
    """Evaluate one completed finance RAG run using deterministic heuristics."""
    del graded_evidence  # Reserved for future finer-grained evaluation.

    metric_functions = {
        "retrieval_completeness": score_retrieval_completeness(
            retrieval_plan, retrieval_summary, repair_summary
        ),
        "source_relevance": score_source_relevance(evidence_summary, repair_summary),
        "evidence_grounding": score_evidence_grounding(final_answer, sources),
        "comparative_reasoning": score_comparative_reasoning(final_answer),
        "risk_specific_reasoning": score_risk_specific_reasoning(final_answer),
        "overclaiming_control": score_overclaiming_control(final_answer),
        "recommendation_quality": score_recommendation_quality(final_answer),
        "limitations_quality": score_limitations_quality(final_answer, report_content),
        "source_transparency": score_source_transparency(sources, final_answer),
        "report_quality": score_report_quality(report_content),
    }

    scores = {metric: value[0] for metric, value in metric_functions.items()}
    notes = {metric: value[1] for metric, value in metric_functions.items()}
    overall_score = calculate_overall_score(scores)

    strengths = []
    weaknesses = []
    recommendations = []

    if scores["retrieval_completeness"] and scores["retrieval_completeness"] >= 4:
        strengths.append("Balanced retrieval plan across both banks and requested risk types.")
    else:
        weaknesses.append("Retrieval coverage has important gaps.")
        recommendations.append("Add fallback retrieval when a planner task has zero retrieved chunks.")

    if scores["source_relevance"] and scores["source_relevance"] >= 4:
        strengths.append("Evidence grading removed low-relevance chunks or retained stronger evidence.")
    else:
        weaknesses.append("Evidence relevance could be improved.")

    unresolved_repairs = [
        item for item in repair_summary or []
        if item.get("status") in {"attempted_no_improvement", "failed"}
    ]
    improved_repairs = [item for item in repair_summary or [] if item.get("status") == "improved"]
    if improved_repairs:
        strengths.append("Retrieval repair improved at least one weak evidence task.")
    if unresolved_repairs:
        weaknesses.append("Some evidence gaps remained after retrieval repair.")
        recommendations.append("Add additional fallback queries or ingest more relevant pages for unresolved tasks.")

    if scores["overclaiming_control"] and scores["overclaiming_control"] >= 4:
        strengths.append("Final answer uses cautious language and avoids definitive unsupported ranking.")
    else:
        weaknesses.append("Final answer may need stronger overclaiming controls.")
        recommendations.append("Strengthen answer critic instructions for risk-ranking language.")

    if scores["report_quality"] is None:
        recommendations.append("Generate a report with --report to evaluate report quality.")
    elif scores["report_quality"] < 4:
        weaknesses.append("Report structure or risk comparison sections could be more complete.")
        recommendations.append("Improve report generator risk comparison subsections.")

    if not recommendations:
        recommendations.append("Continue testing across more finance questions and documents.")

    return {
        "question": question,
        "scores": scores,
        "notes": notes,
        "overall_score": overall_score,
        "summary": (
            "The system shows structured retrieval, evidence filtering, cautious reasoning, "
            "and reusable reporting. Remaining gaps should be reviewed per metric notes."
        ),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "pipeline_metadata": build_pipeline_metadata(
            retrieval_plan, evidence_summary, repair_summary, critic_summary, report_path
        ),
        "retrieval_plan": retrieval_plan or [],
        "retrieval_summary": retrieval_summary or [],
        "evidence_summary": evidence_summary or [],
        "repair_summary": repair_summary or [],
        "report_path": report_path,
    }


def metric_score_text(score: int | None) -> str:
    """Format a metric score."""
    return "not scored" if score is None else f"{score}/5"


def save_evaluation_markdown(
    evaluation: dict,
    output_dir: str | Path = DEFAULT_EVALUATION_DIR,
    evaluation_name: str | None = None,
) -> str:
    """Save a V5 evaluation report and return its path."""
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    evaluation_file = output_path / sanitize_evaluation_name(evaluation_name)

    metric_rows = []
    for metric, label in METRIC_LABELS.items():
        metric_rows.append(
            f"| {label} | {metric_score_text(evaluation['scores'].get(metric))} | "
            f"{evaluation['notes'].get(metric, '')} |"
        )

    metadata = evaluation["pipeline_metadata"]
    tasks = evaluation.get("retrieval_plan", [])
    retrieval_summary = evaluation.get("retrieval_summary", [])
    evidence_summary = evaluation.get("evidence_summary", [])
    repair_summary = evaluation.get("repair_summary", [])

    content = f"""# V5 Evaluation Agent Report

## 1. Question

{evaluation['question']}

## 2. Overall Score

{evaluation['overall_score']}/5

{evaluation['summary']}

## 3. Metric Scores

| Metric | Score | Notes |
|---|---|---|
{chr(10).join(metric_rows)}

## 4. Strengths

{chr(10).join(f"- {item}" for item in evaluation['strengths'])}

## 5. Weaknesses

{chr(10).join(f"- {item}" for item in evaluation['weaknesses']) or "- No major weaknesses identified by deterministic heuristics."}

## 6. Recommendations

{chr(10).join(f"- {item}" for item in evaluation['recommendations'])}

## 7. Pipeline Metadata

- planner used: {str(metadata['planner_used']).lower()}
- evidence grader used: {str(metadata['evidence_grader_used']).lower()}
- retrieval repair used: {str(metadata['retrieval_repair_used']).lower()}
- critic used: {str(metadata['critic_used']).lower()}
- report generated: {str(metadata['report_generated']).lower()}
- report path: {metadata.get('report_path') or 'n/a'}

## 8. Retrieval Completeness Details

Tasks planned:

{chr(10).join(f"- {task.get('entity')} / {task.get('risk_type')} / {task.get('search_query')}" for task in tasks) or "- No structured tasks were available."}

Chunks retrieved:

{chr(10).join(f"- {item.get('entity')} / {item.get('risk_type')}: {item.get('count')}" for item in retrieval_summary) if isinstance(retrieval_summary, list) else str(retrieval_summary)}

Evidence kept/removed:

{chr(10).join(f"- {item.get('entity')} / {item.get('risk_type')}: {item.get('kept', 0)} kept, {item.get('removed', 0)} removed" for item in evidence_summary) or "- Evidence grading summary was not available."}

Retrieval repair:

{chr(10).join(f"- {item.get('entity')} / {item.get('risk_type')}: {item.get('status')} ({item.get('additional_chunks_kept', 0)} kept from repair)" for item in repair_summary) or "- Retrieval repair was not used."}

## 9. Evaluation Limitations

- This is a deterministic heuristic evaluation, not a human expert review.
- It does not verify external truth beyond retrieved sources.
- It does not prove the financial conclusions are correct.
- Financial conclusions are not investment advice.
"""

    evaluation_file.write_text(content.strip() + "\n", encoding="utf-8")
    try:
        return str(evaluation_file.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(evaluation_file)
