"""Deterministic V2 evidence grader for planner-based retrieval."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from langchain_core.documents import Document


RISK_KEYWORDS = {
    "operational risk": [
        "operational risk",
        "non-financial risk",
        "internal processes",
        "systems",
        "external events",
        "fraud",
        "control",
        "controls",
        "framework",
        "loss event",
        "business continuity",
        "cyber",
        "compliance failure",
    ],
    "liquidity risk": [
        "liquidity risk",
        "liquidity",
        "funding",
        "cash flow",
        "stress scenario",
        "liquidity coverage ratio",
        "lcr",
        "net stable funding ratio",
        "nsfr",
        "deposits",
        "refinancing",
        "payment obligations",
    ],
    "regulatory risk": [
        "regulatory risk",
        "regulation",
        "regulatory",
        "compliance",
        "supervisor",
        "supervision",
        "ecb",
        "bafin",
        "eba",
        "capital requirement",
        "audit",
        "enforcement",
        "sanctions",
        "reporting",
        "data integrity",
    ],
    "regulatory context": [
        "eba",
        "european banking authority",
        "regulation",
        "supervision",
        "supervisory",
        "banking",
        "capital",
        "liquidity",
        "risk management",
        "governance",
    ],
}

CONCRETE_EVIDENCE_WORDS = [
    "framework",
    "policy",
    "governance",
    "exposure",
    "losses",
    "stress",
    "ratio",
    "requirement",
    "controls",
    "mitigation",
    "monitoring",
    "capital",
    "funding",
]

ENTITY_ALIASES = {
    "Deutsche Bank": ["deutsche bank", "deutsche"],
    "Commerzbank": ["commerzbank", "commerz"],
    "EBA": ["eba", "european banking authority"],
}


def normalize_text(text: str) -> str:
    """Lowercase and normalize whitespace for simple matching."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def get_keywords_for_risk_type(risk_type: str) -> list[str]:
    """Return task-specific keyword hints."""
    return RISK_KEYWORDS.get(normalize_text(risk_type), [])


def phrase_hits(text: str, phrases: list[str]) -> list[str]:
    """Return phrases present in normalized text."""
    return [phrase for phrase in phrases if normalize_text(phrase) in text]


def source_matches_entity(entity: str, metadata: dict[str, Any]) -> bool:
    """Use source filename as a backup signal when text omits the bank name."""
    source_file = normalize_text(str(metadata.get("source_file", "")))
    return any(alias in source_file for alias in ENTITY_ALIASES.get(entity, []))


def score_chunk(
    question: str,
    task: dict,
    chunk_text: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Score a chunk against the user question and a planner retrieval task."""
    del question  # Reserved for future grader improvements.

    metadata = metadata or {}
    text = normalize_text(chunk_text)
    entity = task.get("entity", "")
    risk_type = task.get("risk_type", "")
    score = 0.0
    reasons: list[str] = []

    entity_hits = phrase_hits(text, ENTITY_ALIASES.get(entity, []))
    if entity_hits:
        score += 0.20
        reasons.append(f"mentions target entity: {entity}")
    elif source_matches_entity(entity, metadata):
        score += 0.10
        reasons.append(f"source file matches target entity: {entity}")

    risk_text = normalize_text(risk_type)
    if risk_text and risk_text in text:
        score += 0.30
        reasons.append(f"mentions target risk type: {risk_type}")

    risk_hits = phrase_hits(text, get_keywords_for_risk_type(risk_type))
    if risk_hits:
        score += min(0.25, 0.05 * len(risk_hits))
        reasons.append("contains related risk keywords: " + ", ".join(risk_hits[:5]))

    evidence_hits = phrase_hits(text, CONCRETE_EVIDENCE_WORDS)
    if evidence_hits:
        score += min(0.20, 0.04 * len(evidence_hits))
        reasons.append("contains concrete evidence terms: " + ", ".join(evidence_hits[:5]))

    if len(text) < 150:
        score -= 0.20
        reasons.append("penalized for very short chunk")
    elif len(text) < 300:
        score -= 0.10
        reasons.append("penalized for short chunk")

    if entity not in {"General", "EBA"} and not entity_hits and not source_matches_entity(entity, metadata):
        score -= 0.15
        reasons.append("does not mention or source-match the target entity")

    if risk_text and risk_text not in text and not risk_hits:
        score -= 0.20
        reasons.append("does not match the task risk type")

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("limited task-specific evidence signals found")
    return score, reasons


def relevance_label(score: float) -> str:
    """Map numeric score to a simple relevance label."""
    if score >= 0.70:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def grade_chunk(question: str, task: dict, chunk: dict) -> dict:
    """Grade one retrieved chunk represented as a dictionary."""
    score, reasons = score_chunk(
        question,
        task,
        chunk.get("text", ""),
        metadata=chunk.get("metadata", {}),
    )
    metadata = chunk.get("metadata", {})
    return {
        "entity": task.get("entity"),
        "risk_type": task.get("risk_type"),
        "source": metadata.get("source_file", "unknown"),
        "page": metadata.get("page_number", "unknown"),
        "relevance": relevance_label(score),
        "score": round(score, 2),
        "keep": False,
        "reason": "; ".join(reasons),
        "text": chunk.get("text", ""),
        "metadata": metadata,
        "task": task,
        "document": chunk.get("document"),
    }


def grade_task_evidence(
    question: str,
    task: dict,
    chunks: list[dict],
    top_n: int = 2,
) -> list[dict]:
    """Grade and mark kept chunks for one retrieval task."""
    graded = [grade_chunk(question, task, chunk) for chunk in chunks]
    graded.sort(key=lambda item: item["score"], reverse=True)

    high = [item for item in graded if item["relevance"] == "high"]
    medium = [item for item in graded if item["relevance"] == "medium"]
    keep_ids = {id(item) for item in high[:top_n]}

    if len(keep_ids) < top_n:
        for item in medium:
            if len(keep_ids) >= top_n:
                break
            keep_ids.add(id(item))

    for item in graded:
        item["keep"] = id(item) in keep_ids

    return graded


def document_to_chunk(doc: Document) -> dict:
    """Convert a LangChain Document into the grader's chunk dictionary."""
    return {
        "text": doc.page_content,
        "metadata": dict(doc.metadata),
        "document": doc,
    }


def grade_planner_results(
    question: str,
    planner_tasks: list[dict],
    documents: list[Document],
    top_n: int = 2,
) -> tuple[list[Document], list[dict]]:
    """Grade planner-retrieved documents and return kept docs plus summary."""
    docs_by_task: dict[int, list[Document]] = defaultdict(list)
    for doc in documents:
        task_index = int(doc.metadata.get("planner_task_index", 0))
        docs_by_task[task_index].append(doc)

    kept_documents: list[Document] = []
    grading_summary: list[dict] = []

    for task_index, task in enumerate(planner_tasks, start=1):
        chunks = [document_to_chunk(doc) for doc in docs_by_task.get(task_index, [])]
        graded_items = grade_task_evidence(question, task, chunks, top_n=top_n)

        task_summary = {
            "entity": task["entity"],
            "risk_type": task["risk_type"],
            "kept": sum(1 for item in graded_items if item["keep"]),
            "removed": sum(1 for item in graded_items if not item["keep"]),
            "items": [],
        }

        for item in graded_items:
            doc = item["document"]
            if item["keep"] and doc is not None:
                metadata = dict(doc.metadata)
                metadata["evidence_relevance"] = item["relevance"]
                metadata["evidence_score"] = item["score"]
                metadata["evidence_reason"] = item["reason"]
                kept_documents.append(
                    Document(page_content=doc.page_content, metadata=metadata)
                )

            task_summary["items"].append(
                {
                    "relevance": item["relevance"],
                    "score": item["score"],
                    "page": item["page"],
                    "keep": item["keep"],
                    "source": item["source"],
                    "reason": item["reason"],
                }
            )

        grading_summary.append(task_summary)

    return kept_documents, grading_summary
