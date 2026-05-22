"""V4 deterministic Markdown report generator for finance RAG outputs."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.config import PROJECT_ROOT


DEFAULT_REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"
DEFAULT_REPORT_TITLE = "Banking Risk Comparison Report"


def sanitize_report_name(report_name: str | None) -> str:
    """Return a safe markdown filename that cannot escape the report directory."""
    if not report_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"risk_report_{timestamp}.md"

    name = Path(report_name).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not name:
        name = "risk_report"
    if not name.lower().endswith(".md"):
        name += ".md"
    return name


def markdown_escape(value: Any) -> str:
    """Escape table-sensitive characters."""
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def extract_answer_section(answer: str, heading: str) -> str:
    """Extract a section from plain or bold markdown answer headings."""
    headings = [
        "Executive Summary",
        "Key Evidence",
        "Risk Flags",
        "Recommendation",
        "Sources",
        "Limitations",
        "Confidence",
    ]
    heading_pattern = re.escape(heading)
    next_headings = [re.escape(item) for item in headings if item != heading]
    pattern = re.compile(
        rf"(?:^|\n)(?:\*\*)?{heading_pattern}:\s*(?:\*\*)?\s*\n?"
        rf"(.*?)(?=\n(?:\*\*)?(?:{'|'.join(next_headings)}):\s*(?:\*\*)?|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(answer)
    if not match:
        return ""
    return match.group(1).strip()


def collect_sources_from_documents(documents: list[Document]) -> dict[str, list[Any]]:
    """Collect source files and page numbers from retrieved/kept documents."""
    pages_by_source: dict[str, set[Any]] = defaultdict(set)
    for doc in documents:
        source_file = doc.metadata.get("source_file", "unknown")
        page_number = doc.metadata.get("page_number", "unknown")
        pages_by_source[source_file].add(page_number)

    result: dict[str, list[Any]] = {}
    for source_file, pages in pages_by_source.items():
        result[source_file] = sorted(pages, key=lambda value: str(value))
    return dict(sorted(result.items()))


def build_retrieval_summary_rows(retrieval_summary: Any) -> list[dict]:
    """Normalize retrieval summary metadata into report rows."""
    if not retrieval_summary:
        return []
    if isinstance(retrieval_summary, list):
        return retrieval_summary
    if isinstance(retrieval_summary, dict):
        return [
            {
                "entity": key,
                "risk_type": "all",
                "count": value,
            }
            for key, value in retrieval_summary.items()
        ]
    return []


def best_evidence_values(task_summary: dict) -> tuple[str, str]:
    """Return best relevance and score for one evidence-grading task."""
    items = task_summary.get("items", [])
    if not items:
        return "n/a", "n/a"
    best = max(items, key=lambda item: float(item.get("score", 0.0)))
    return str(best.get("relevance", "n/a")), f"{float(best.get('score', 0.0)):.2f}"


def critic_review_values(critic_summary: dict | None) -> tuple[str, int, str, str]:
    """Normalize critic metadata for the report."""
    if not critic_summary:
        return (
            "not used",
            0,
            "Answer Critic Agent was not used for this run.",
            "Answer Critic Agent was not used for this run.",
        )

    issues = critic_summary.get("issues", [])
    main_issue = issues[0].get("message", "None") if issues else "None"
    return (
        str(critic_summary.get("passed", False)).lower(),
        len(issues),
        main_issue,
        critic_summary.get("critic_summary", ""),
    )


def confidence_from_answer(final_answer: str) -> str:
    """Extract confidence from the final answer or default to Medium."""
    confidence = extract_answer_section(final_answer, "Confidence")
    if not confidence:
        return "Medium"
    first_line = confidence.splitlines()[0].strip()
    return first_line or "Medium"


def build_risk_section(final_answer: str, risk_heading: str, missing_note: str | None = None) -> str:
    """Create a deterministic risk section from the final answer text."""
    escaped = re.escape(risk_heading)
    pattern = re.compile(
        rf"(?:^|\n)(?:#+\s*)?(?:\*\*)?{escaped}(?:\*\*)?:?\s*\n?(.*?)(?=\n(?:#+\s*)?(?:\*\*)?(?:Operational Risk|Liquidity Risk|Regulatory Risk)(?:\*\*)?:|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(final_answer)
    text = match.group(1).strip() if match else ""
    if not text:
        text = "See the Executive Summary and Key Evidence sections above for the available retrieved evidence."
    if missing_note and missing_note.lower() not in text.lower():
        text += f"\n\n{missing_note}"
    return text


def table_or_note(headers: list[str], rows: list[list[Any]], empty_note: str) -> str:
    """Render a markdown table or a fallback note."""
    if not rows:
        return empty_note
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    row_lines = [
        "| " + " | ".join(markdown_escape(value) for value in row) + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator, *row_lines])


def pipeline_lines(
    retrieval_plan: list[dict] | None,
    evidence_summary: list[dict] | None,
    critic_summary: dict | None,
) -> str:
    """Describe the pipeline components active for this report."""
    lines = []
    if retrieval_plan:
        lines.append("- Query Planner Agent: decomposed the user question into structured retrieval tasks.")
    else:
        lines.append("- Query Planner Agent: was not used for this run.")

    if evidence_summary:
        lines.append("- Evidence Grader Agent: scored retrieved chunks and filtered weak evidence before answer generation.")
    else:
        lines.append("- Evidence Grader Agent: was not used for this run.")

    if critic_summary:
        lines.append("- Answer Critic Agent: reviewed the draft answer for grounding, overclaiming, uncertainty, and consulting-style recommendations.")
    else:
        lines.append("- Answer Critic Agent: was not used for this run.")

    lines.append("- Report Generator Agent: formatted the completed pipeline outputs into this Markdown report.")
    return "\n".join(lines)


def generate_report(
    question: str,
    final_answer: str,
    retrieval_plan: list[dict] | None = None,
    retrieval_summary: Any | None = None,
    evidence_summary: list[dict] | None = None,
    critic_summary: dict | None = None,
    sources: dict | None = None,
    output_dir: str | Path = DEFAULT_REPORT_DIR,
    report_name: str | None = None,
) -> str:
    """Generate a deterministic professional Markdown report and return its path."""
    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    report_file = output_path / sanitize_report_name(report_name)

    executive_summary = extract_answer_section(final_answer, "Executive Summary") or final_answer
    recommendation = extract_answer_section(final_answer, "Recommendation") or final_answer
    limitations = extract_answer_section(final_answer, "Limitations")
    confidence = confidence_from_answer(final_answer)

    retrieval_rows = [
        [
            index,
            task.get("entity", "unknown"),
            task.get("risk_type", "unknown"),
            task.get("search_query", "unknown"),
            task.get("purpose", "unknown"),
        ]
        for index, task in enumerate(retrieval_plan or [], start=1)
    ]

    retrieval_summary_rows = [
        [item.get("entity", "unknown"), item.get("risk_type", "unknown"), item.get("count", 0)]
        for item in build_retrieval_summary_rows(retrieval_summary)
    ]

    evidence_rows = []
    for item in evidence_summary or []:
        best_relevance, best_score = best_evidence_values(item)
        evidence_rows.append(
            [
                item.get("entity", "unknown"),
                item.get("risk_type", "unknown"),
                item.get("kept", 0),
                item.get("removed", 0),
                best_relevance,
                best_score,
            ]
        )

    source_rows = [
        [source_file, ", ".join(str(page) for page in pages)]
        for source_file, pages in sorted((sources or {}).items())
    ]

    critic_passed, issue_count, main_issue, critic_text = critic_review_values(critic_summary)

    report = f"""# {DEFAULT_REPORT_TITLE}

## 1. Question

{question}

## 2. Executive Summary

{executive_summary}

This report interprets the final answer as a retrieved-evidence assessment, not as a definitive risk ranking. Missing or weaker retrieved evidence may reflect retrieval coverage or disclosure detail rather than higher actual risk.

## 3. Agentic RAG Pipeline Used

{pipeline_lines(retrieval_plan, evidence_summary, critic_summary)}

## 4. Generated Retrieval Plan

{table_or_note(
        ["Step", "Entity", "Risk Type", "Search Query", "Purpose"],
        retrieval_rows,
        "No structured retrieval plan was available for this run.",
    )}

## 5. Retrieval Summary

{table_or_note(
        ["Entity", "Risk Type", "Chunks Retrieved"],
        retrieval_summary_rows,
        "No retrieval summary was available for this run.",
    )}

## 6. Evidence Grading Summary

{table_or_note(
        ["Entity", "Risk Type", "Kept", "Removed", "Best Relevance", "Best Score"],
        evidence_rows,
        "Evidence grading was not used for this run.",
    )}

Low-relevance evidence was excluded from final answer generation when evidence grading was enabled.

## 7. Risk Comparison

### 7.1 Operational Risk

{build_risk_section(final_answer, "Operational Risk")}

### 7.2 Liquidity Risk

{build_risk_section(
        final_answer,
        "Liquidity Risk",
        "Retrieved and graded evidence was insufficient for Commerzbank liquidity risk.",
    )}

### 7.3 Regulatory Risk

{build_risk_section(final_answer, "Regulatory Risk")}

## 8. Consultant Recommendation

{recommendation}

Additional quantitative indicators to check:

- LCR
- NSFR
- stress test results
- capital ratios
- regulatory findings
- historical operational loss data

## 9. Answer Critic Review

- passed: {critic_passed}
- issues found: {issue_count}
- main issue: {main_issue}
- critic summary: {critic_text}

## 10. Sources

{table_or_note(["Source File", "Pages"], source_rows, "No source metadata was available.")}

## 11. Limitations

{limitations or "- Analysis is based only on retrieved evidence."}
- Missing Commerzbank liquidity evidence limits comparison when applicable.
- Disclosure detail is not the same as actual risk.
- The final risk conclusion is not a definitive credit, investment, or supervisory rating.

## 12. Confidence

{confidence}
"""

    report_file.write_text(report.strip() + "\n", encoding="utf-8")
    try:
        return str(report_file.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(report_file)
