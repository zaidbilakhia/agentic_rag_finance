"""V6 deterministic retrieval repair for weak planner evidence tasks."""

from __future__ import annotations

import re
from typing import Callable

from langchain_core.documents import Document

from src.evidence_grader import document_to_chunk, grade_task_evidence


REPAIR_QUERY_TEMPLATES = {
    "liquidity risk": [
        "{entity} liquidity risk management",
        "{entity} funding risk",
        "{entity} liquidity coverage ratio",
        "{entity} LCR NSFR",
        "{entity} liquidity stress test",
        "{entity} refinancing risk",
        "{entity} cash flow liquidity",
        "{entity} liquidity reserve",
        "{entity} funding plan",
    ],
    "operational risk": [
        "{entity} operational risk management",
        "{entity} non-financial risk",
        "{entity} internal controls",
        "{entity} operational loss",
        "{entity} cyber risk",
        "{entity} fraud risk",
        "{entity} business continuity",
        "{entity} risk control framework",
    ],
    "regulatory risk": [
        "{entity} regulatory compliance",
        "{entity} supervision",
        "{entity} ECB supervision",
        "{entity} BaFin",
        "{entity} EBA",
        "{entity} capital requirements",
        "{entity} regulatory findings",
        "{entity} regulatory reporting",
        "{entity} compliance risk",
    ],
    "regulatory context": [
        "EBA banking supervision risk management",
        "EBA liquidity risk supervision",
        "EBA operational risk supervision",
        "EBA regulatory framework banks",
        "EBA capital requirements liquidity risk",
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for duplicate detection."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def document_key(doc: Document) -> tuple[object, object, str]:
    """Create a lightweight duplicate key for a retrieved chunk."""
    return (
        doc.metadata.get("source_file", "unknown"),
        doc.metadata.get("page_number", "unknown"),
        normalize_text(doc.page_content[:200]),
    )


def source_page_key(doc: Document) -> tuple[object, object]:
    """Return source/page duplicate key."""
    return (
        doc.metadata.get("source_file", "unknown"),
        doc.metadata.get("page_number", "unknown"),
    )


def text_key(doc: Document) -> str:
    """Return normalized text-prefix duplicate key."""
    return normalize_text(doc.page_content[:200])


def needs_repair(
    task: dict,
    graded_chunks: list[dict],
    min_kept: int = 1,
    min_best_score: float = 0.40,
) -> bool:
    """Return True when a task has weak or missing graded evidence."""
    del task
    kept = [item for item in graded_chunks if item.get("keep")]
    if len(kept) < min_kept:
        return True
    best_score = max(float(item.get("score", 0.0)) for item in kept)
    if best_score < min_best_score:
        return True
    if kept and all(item.get("relevance") == "low" for item in kept):
        return True
    if graded_chunks and not kept:
        return True
    return False


def generate_repair_queries(
    task: dict,
    question: str,
    max_queries: int = 4,
) -> list[str]:
    """Generate bounded fallback queries for a weak retrieval task."""
    del question
    entity = task.get("entity", "")
    risk_type = task.get("risk_type", "")
    templates = REPAIR_QUERY_TEMPLATES.get(risk_type, [f"{entity} {risk_type} management"])

    queries = []
    for template in templates:
        query = template.format(entity=entity).strip()
        if query and query not in queries:
            queries.append(query)
        if len(queries) >= max_queries:
            break
    return queries


def annotate_repaired_document(doc: Document, task: dict, task_index: int, query: str) -> Document:
    """Attach planner and repair metadata to a retrieved repair chunk."""
    metadata = dict(doc.metadata)
    metadata["retrieval_entity"] = task["entity"]
    metadata["retrieval_focus"] = task["risk_type"]
    metadata["retrieval_focuses"] = f"{task['entity']}: {task['risk_type']}"
    metadata["planner_task_index"] = task_index
    metadata["planner_search_query"] = task["search_query"]
    metadata["planner_purpose"] = task["purpose"]
    metadata["repair_query"] = query
    metadata["retrieval_repaired"] = True
    return Document(page_content=doc.page_content, metadata=metadata)


def grade_repaired_documents(
    question: str,
    task: dict,
    documents: list[Document],
    evidence_top_n: int,
) -> tuple[list[Document], list[dict]]:
    """Grade repaired documents and return kept repaired docs plus grading items."""
    chunks = [document_to_chunk(doc) for doc in documents]
    graded_items = grade_task_evidence(question, task, chunks, top_n=evidence_top_n)
    kept_documents = []

    for item in graded_items:
        doc = item.get("document")
        if not item.get("keep") or doc is None:
            continue
        metadata = dict(doc.metadata)
        metadata["evidence_relevance"] = item["relevance"]
        metadata["evidence_score"] = item["score"]
        metadata["evidence_reason"] = item["reason"]
        metadata["retrieval_repaired"] = True
        kept_documents.append(Document(page_content=doc.page_content, metadata=metadata))

    return kept_documents, graded_items


def repair_task_retrieval(
    question: str,
    task: dict,
    task_index: int,
    existing_documents: list[Document],
    retriever_fn: Callable[[dict, str, int], list[Document]],
    top_k: int = 3,
    evidence_top_n: int = 2,
    max_queries: int = 4,
) -> dict:
    """Attempt repair retrieval for one weak planner task."""
    repair_queries = generate_repair_queries(task, question, max_queries=max_queries)
    seen = {document_key(doc) for doc in existing_documents}
    seen_source_pages = {source_page_key(doc) for doc in existing_documents}
    seen_texts = {text_key(doc) for doc in existing_documents}
    repaired_candidates: list[Document] = []
    additional_retrieved = 0

    for query in repair_queries:
        try:
            docs = retriever_fn(task, query, top_k)
        except Exception as exc:
            return {
                "entity": task["entity"],
                "risk_type": task["risk_type"],
                "repair_needed": True,
                "repair_queries": repair_queries,
                "additional_chunks_retrieved": additional_retrieved,
                "additional_chunks_kept": 0,
                "best_repaired_score": 0.0,
                "status": "failed",
                "message": f"Repair retrieval failed: {exc}",
                "kept_documents": [],
                "graded_items": [],
            }

        for doc in docs:
            annotated_doc = annotate_repaired_document(doc, task, task_index, query)
            key = document_key(annotated_doc)
            source_page = source_page_key(annotated_doc)
            text_prefix = text_key(annotated_doc)
            if key in seen or source_page in seen_source_pages or text_prefix in seen_texts:
                continue
            seen.add(key)
            seen_source_pages.add(source_page)
            seen_texts.add(text_prefix)
            repaired_candidates.append(annotated_doc)
            additional_retrieved += 1

    kept_documents, graded_items = grade_repaired_documents(
        question,
        task,
        repaired_candidates,
        evidence_top_n=evidence_top_n,
    )
    best_score = max((float(item.get("score", 0.0)) for item in graded_items), default=0.0)
    kept_count = len(kept_documents)
    status = "improved" if kept_count else "attempted_no_improvement"
    message = (
        f"Repair found additional relevant evidence for {task['entity']} {task['risk_type']}."
        if kept_count
        else "Repair attempted, but no strong evidence was found."
    )

    return {
        "entity": task["entity"],
        "risk_type": task["risk_type"],
        "repair_needed": True,
        "repair_queries": repair_queries,
        "additional_chunks_retrieved": additional_retrieved,
        "additional_chunks_kept": kept_count,
        "best_repaired_score": round(best_score, 2),
        "status": status,
        "message": message,
        "kept_documents": kept_documents,
        "graded_items": graded_items,
    }


def repair_retrieval_results(
    question: str,
    planner_tasks: list[dict],
    initial_documents: list[Document],
    kept_documents: list[Document],
    evidence_summary: list[dict],
    retriever_fn: Callable[[dict, str, int], list[Document]],
    top_k: int = 3,
    evidence_top_n: int = 2,
    max_queries: int = 4,
    min_kept: int = 1,
    min_best_score: float = 0.40,
) -> dict:
    """Repair weak tasks and merge kept repaired evidence with original kept evidence."""
    summary_by_task = {
        (item.get("entity"), item.get("risk_type")): item for item in evidence_summary
    }
    final_documents = list(kept_documents)
    repair_summary = []

    for task_index, task in enumerate(planner_tasks, start=1):
        key = (task["entity"], task["risk_type"])
        task_summary = summary_by_task.get(key, {})
        graded_items = task_summary.get("items", [])

        if not needs_repair(task, graded_items, min_kept=min_kept, min_best_score=min_best_score):
            repair_summary.append(
                {
                    "entity": task["entity"],
                    "risk_type": task["risk_type"],
                    "repair_needed": False,
                    "repair_queries": [],
                    "additional_chunks_retrieved": 0,
                    "additional_chunks_kept": 0,
                    "best_repaired_score": 0.0,
                    "status": "not_needed",
                    "message": "Existing graded evidence met repair thresholds.",
                    "kept_documents": [],
                    "graded_items": [],
                }
            )
            continue

        repair_result = repair_task_retrieval(
            question=question,
            task=task,
            task_index=task_index,
            existing_documents=initial_documents + final_documents,
            retriever_fn=retriever_fn,
            top_k=top_k,
            evidence_top_n=evidence_top_n,
            max_queries=max_queries,
        )
        final_documents.extend(repair_result["kept_documents"])
        repair_summary.append(repair_result)

    return {
        "documents": final_documents,
        "repair_summary": repair_summary,
    }
