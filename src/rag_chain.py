"""RAG prompt construction and answer generation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import (
    CHAT_MODEL,
    DEFAULT_PER_RISK_K,
    DEFAULT_PER_SOURCE_K,
    DEFAULT_TOP_K,
    MAX_COMPARISON_CHUNKS,
    MAX_CONTEXT_CHARS_PER_CHUNK,
)
from src.evidence_grader import grade_planner_results
from src.query_planner import plan_query
from src.vector_store import list_source_files, similarity_search_by_source_file


ANSWER_PROMPT = """You are a careful financial document analysis assistant.

Answer the question using only the retrieved context below.
If the context is insufficient, say what is missing. Do not invent facts.
When evidence relevance and scores are shown in the context, prioritize high-relevance and higher-scored evidence.
Use consulting-style, evidence-safe language. Prefer phrases such as:
- "Based on the retrieved evidence..."
- "The retrieved disclosures suggest..."
- "The evidence is stronger for..."
- "This should not be interpreted as a full risk ranking without additional quantitative metrics."
Avoid saying one bank is definitely safer or riskier unless the retrieved evidence strongly supports it.

When the question compares Deutsche Bank and Commerzbank:
- Compare Deutsche Bank and Commerzbank separately.
- Compare each requested risk type separately, using headings such as Operational Risk, Liquidity Risk, and Regulatory Risk when those risks are requested.
- Use evidence for each bank from that bank's retrieved sources.
- State clearly when one bank has stronger or weaker retrieved evidence than the other.
- Do not claim one bank is riskier unless the retrieved context provides enough evidence for both banks.
- If evidence for either bank or risk category is missing, say exactly: "Retrieved evidence was insufficient for this specific category" and lower confidence.
- Include sources for both banks when available.

Required output format:

Executive Summary:
...

Key Evidence:
- ...

Risk Flags:
- ...

Recommendation:
Further due diligence required:
- ...

Additional quantitative indicators to check:
- ...

Suggested consultant next steps:
- ...

Sources:
- source_file, page_number

Limitations:
...

Confidence:
Low / Medium / High

Question:
{question}

Retrieved context:
{context}
"""

KNOWN_ENTITY_PATTERNS = {
    "Deutsche Bank": ["deutsche bank", "deutsche"],
    "Commerzbank": ["commerzbank", "commerz"],
    "EBA": ["eba", "european banking authority"],
    "Basel": ["basel"],
}

SOURCE_LABEL_PATTERNS = {
    "Deutsche Bank": ["deutsche"],
    "Commerzbank": ["commerzbank", "commerz"],
    "EBA": ["eba"],
    "Basel": ["basel"],
}

REGULATORY_TERMS = [
    "regulation",
    "regulatory",
    "compliance",
    "eba",
    "supervision",
    "basel",
    "capital requirement",
]

RISK_TYPE_PATTERNS = {
    "operational risk": ["operational risk", "operations risk", "operational"],
    "liquidity risk": ["liquidity risk", "funding risk", "liquidity"],
    "regulatory risk": ["regulatory risk", "regulation risk", "supervisory risk", "regulatory"],
    "credit risk": ["credit risk", "credit"],
    "market risk": ["market risk", "market"],
    "cyber risk": ["cyber risk", "cybersecurity risk", "cybersecurity", "cyber"],
    "technology risk": ["technology risk", "it risk", "information technology risk"],
    "capital risk": ["capital risk", "capital requirement", "capital requirements", "capital"],
    "compliance risk": ["compliance risk", "compliance"],
}


@dataclass
class RetrievalInfo:
    """Small status object for CLI logging."""

    mode: str
    counts_by_source: dict[str, int]
    counts_by_entity_and_risk: dict[str, dict[str, int]] | None = None
    regulatory_context_count: int = 0
    planner_tasks: list[dict] | None = None
    counts_by_task: list[dict] | None = None
    evidence_grading_summary: list[dict] | None = None


def truncate_text(text: str, max_chars: int = MAX_CONTEXT_CHARS_PER_CHUNK) -> str:
    """Limit each retrieved chunk before it is sent to the chat model."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def format_retrieved_documents(documents: list[Document]) -> str:
    """Format retrieved chunks with compact source metadata."""
    formatted = []
    for index, doc in enumerate(documents, start=1):
        source_file = doc.metadata.get("source_file", "unknown")
        page_number = doc.metadata.get("page_number", "unknown")
        category = doc.metadata.get("document_category", "unknown")
        focuses = doc.metadata.get("retrieval_focuses") or doc.metadata.get("retrieval_focus")
        focus_line = f", retrieval focus {focuses}" if focuses else ""
        chunk = truncate_text(doc.page_content)
        formatted.append(
            f"[{index}] Source: {source_file}, page {page_number}, category {category}{focus_line}\n"
            f"{chunk}"
        )
    return "\n\n".join(formatted)


def format_planner_documents(documents: list[Document]) -> str:
    """Format retrieved chunks grouped by planner task."""
    grouped: dict[int, dict] = {}
    for doc in documents:
        task_index = int(doc.metadata.get("planner_task_index", 0))
        grouped.setdefault(
            task_index,
            {
                "entity": doc.metadata.get("retrieval_entity", "unknown"),
                "risk_type": doc.metadata.get("retrieval_focus", "unknown"),
                "search_query": doc.metadata.get("planner_search_query", "unknown"),
                "documents": [],
            },
        )
        grouped[task_index]["documents"].append(doc)

    sections = []
    for task_index in sorted(grouped):
        group = grouped[task_index]
        sections.append(
            "Retrieval task "
            f"{task_index}: {group['entity']} / {group['risk_type']} / {group['search_query']}"
        )
        for doc_index, doc in enumerate(group["documents"], start=1):
            source_file = doc.metadata.get("source_file", "unknown")
            page_number = doc.metadata.get("page_number", "unknown")
            category = doc.metadata.get("document_category", "unknown")
            relevance = doc.metadata.get("evidence_relevance")
            score = doc.metadata.get("evidence_score")
            header = (
                f"[{task_index}.{doc_index}] Source: {source_file}, "
                f"page {page_number}, category {category}"
            )
            if relevance is not None and score is not None:
                header = (
                    f"[{group['entity']} | {group['risk_type']} | "
                    f"relevance: {relevance} | score: {score} | "
                    f"source: {source_file} | page: {page_number}]"
                )
            chunk = truncate_text(doc.page_content)
            sections.append(f"{header}\n{chunk}")

    return "\n\n".join(sections)


def create_prompt() -> ChatPromptTemplate:
    """Create the finance RAG prompt."""
    return ChatPromptTemplate.from_template(ANSWER_PROMPT)


def detect_entities(question: str) -> set[str]:
    """Detect known document entities mentioned in the user question."""
    lowered = question.lower()
    entities = set()
    for entity, patterns in KNOWN_ENTITY_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            entities.add(entity)
    return entities


def needs_regulatory_context(question: str) -> bool:
    """Return True when the query asks about regulation, supervision, or risk."""
    lowered = question.lower()
    return any(term in lowered for term in REGULATORY_TERMS)


def is_bank_comparison(question: str) -> bool:
    """Detect the Deutsche Bank vs Commerzbank comparison case."""
    entities = detect_entities(question)
    return {"Deutsche Bank", "Commerzbank"}.issubset(entities)


def detect_risk_types(question: str) -> list[str]:
    """Detect requested risk types in the user question."""
    lowered = question.lower()
    risk_types = []
    for risk_type, patterns in RISK_TYPE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            risk_types.append(risk_type)
    return risk_types


def source_files_for_label(source_files: list[str], label: str) -> list[str]:
    """Find source files matching a known source label."""
    patterns = SOURCE_LABEL_PATTERNS.get(label, [])
    matches = []
    for source_file in source_files:
        lowered = source_file.lower()
        if any(pattern in lowered for pattern in patterns):
            matches.append(source_file)
    return matches


def copy_document_with_focus(doc: Document, entity: str, risk_type: str) -> Document:
    """Copy a retrieved document and attach its intended retrieval focus."""
    metadata = dict(doc.metadata)
    metadata["retrieval_entity"] = entity
    metadata["retrieval_focus"] = risk_type
    metadata["retrieval_focuses"] = f"{entity}: {risk_type}"
    return Document(page_content=doc.page_content, metadata=metadata)


def copy_document_with_planner_task(doc: Document, task: dict, task_index: int) -> Document:
    """Copy a document and attach the planner task that retrieved it."""
    metadata = dict(doc.metadata)
    metadata["retrieval_entity"] = task["entity"]
    metadata["retrieval_focus"] = task["risk_type"]
    metadata["retrieval_focuses"] = f"{task['entity']}: {task['risk_type']}"
    metadata["planner_task_index"] = task_index
    metadata["planner_search_query"] = task["search_query"]
    metadata["planner_purpose"] = task["purpose"]
    return Document(page_content=doc.page_content, metadata=metadata)


def dedupe_documents(documents: list[Document]) -> list[Document]:
    """Remove duplicate chunks while preserving retrieval order and focus labels."""
    seen: dict[tuple[object, object, str], Document] = {}
    unique_documents = []
    for doc in documents:
        key = (
            doc.metadata.get("source_file", "unknown"),
            doc.metadata.get("page_number", "unknown"),
            doc.page_content[:200],
        )
        existing_doc = seen.get(key)
        if existing_doc:
            existing_focuses = existing_doc.metadata.get("retrieval_focuses", "")
            new_focus = doc.metadata.get("retrieval_focuses", "")
            if new_focus and new_focus not in existing_focuses:
                merged_focuses = [focus for focus in [existing_focuses, new_focus] if focus]
                existing_doc.metadata["retrieval_focuses"] = "; ".join(merged_focuses)
            continue
        seen[key] = doc
        unique_documents.append(doc)
    return unique_documents


def count_documents_by_source(documents: list[Document]) -> dict[str, int]:
    """Count retrieved chunks by source_file."""
    counts = Counter(
        doc.metadata.get("source_file", "unknown")
        for doc in documents
    )
    return dict(counts)


def normal_retrieval(vector_store, question: str, k: int) -> tuple[list[Document], RetrievalInfo]:
    """Run the original simple similarity retrieval path."""
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    documents = retriever.invoke(question)
    return documents, RetrievalInfo(
        mode="normal",
        counts_by_source=count_documents_by_source(documents),
    )


def planner_source_files(source_files: list[str], task: dict) -> list[str]:
    """Map a planner task to source files. Return [] for global fallback."""
    entity = task["entity"]
    if entity == "General":
        return []
    return source_files_for_label(source_files, entity)


def planner_retrieval(
    vector_store,
    question: str,
    per_risk_k: int = DEFAULT_PER_RISK_K,
    grade_evidence: bool = False,
    evidence_top_n: int = 2,
) -> tuple[list[Document], RetrievalInfo]:
    """Execute V1 query planner tasks against Chroma."""
    tasks = plan_query(question)
    source_files = list_source_files(vector_store)
    documents: list[Document] = []
    counts_by_task: list[dict] = []

    if not tasks:
        documents, info = normal_retrieval(vector_store, question, DEFAULT_TOP_K)
        info.mode = "query planner agent"
        info.planner_tasks = []
        info.counts_by_task = []
        return documents, info

    for task_index, task in enumerate(tasks, start=1):
        task_k = 2 if task["entity"] == "EBA" else per_risk_k
        matching_files = planner_source_files(source_files, task)

        if matching_files:
            task_documents = similarity_search_by_source_file(
                vector_store,
                query=task["search_query"],
                source_files=matching_files,
                k=task_k,
            )
        else:
            task_documents = vector_store.similarity_search(task["search_query"], k=task_k)

        task_documents = dedupe_documents(
            [
                copy_document_with_planner_task(doc, task, task_index)
                for doc in task_documents
            ]
        )
        counts_by_task.append(
            {
                "entity": task["entity"],
                "risk_type": task["risk_type"],
                "count": len(task_documents),
            }
        )
        documents.extend(task_documents)

    if grade_evidence:
        kept_documents, grading_summary = grade_planner_results(
            question,
            planner_tasks=tasks,
            documents=documents,
            top_n=evidence_top_n,
        )
        kept_documents = kept_documents[:MAX_COMPARISON_CHUNKS]
        return kept_documents, RetrievalInfo(
            mode="query planner agent + evidence grader",
            counts_by_source=count_documents_by_source(kept_documents),
            planner_tasks=tasks,
            counts_by_task=counts_by_task,
            evidence_grading_summary=grading_summary,
        )

    documents = dedupe_documents(documents)[:MAX_COMPARISON_CHUNKS]
    return documents, RetrievalInfo(
        mode="query planner agent",
        counts_by_source=count_documents_by_source(documents),
        planner_tasks=tasks,
        counts_by_task=counts_by_task,
    )


def comparison_retrieval(
    vector_store,
    question: str,
    per_source_k: int = DEFAULT_PER_SOURCE_K,
    per_risk_k: int = DEFAULT_PER_RISK_K,
    include_regulatory_context: bool = True,
    use_planner: bool = False,
    grade_evidence: bool = False,
    evidence_top_n: int = 2,
) -> tuple[list[Document], RetrievalInfo]:
    """Retrieve balanced evidence for Deutsche Bank and Commerzbank comparisons."""
    source_files = list_source_files(vector_store)
    documents: list[Document] = []
    risk_types = detect_risk_types(question)
    counts_by_entity_and_risk: dict[str, dict[str, int]] = {}

    if risk_types:
        for entity in ["Deutsche Bank", "Commerzbank"]:
            matching_files = source_files_for_label(source_files, entity)
            counts_by_entity_and_risk[entity] = {}

            for risk_type in risk_types:
                focused_query = f"{entity} {risk_type}"
                focused_documents = similarity_search_by_source_file(
                    vector_store,
                    query=focused_query,
                    source_files=matching_files,
                    k=per_risk_k,
                )
                focused_documents = dedupe_documents(
                    [
                        copy_document_with_focus(doc, entity, risk_type)
                        for doc in focused_documents
                    ]
                )
                counts_by_entity_and_risk[entity][risk_type] = len(focused_documents)
                documents.extend(focused_documents)

        regulatory_context_count = 0
        if include_regulatory_context and needs_regulatory_context(question):
            regulatory_files = []
            for label in ["EBA", "Basel"]:
                regulatory_files.extend(source_files_for_label(source_files, label))

            regulatory_documents = similarity_search_by_source_file(
                vector_store,
                query=f"regulatory context {' '.join(risk_types)}",
                source_files=regulatory_files,
                k=2,
            )
            regulatory_documents = dedupe_documents(
                [
                    copy_document_with_focus(doc, "EBA", "regulatory context")
                    for doc in regulatory_documents
                ]
            )
            regulatory_context_count = len(regulatory_documents)
            documents.extend(regulatory_documents)

        documents = dedupe_documents(documents)[:MAX_COMPARISON_CHUNKS]
        return documents, RetrievalInfo(
            mode="risk-type comparison",
            counts_by_source=count_documents_by_source(documents),
            counts_by_entity_and_risk=counts_by_entity_and_risk,
            regulatory_context_count=regulatory_context_count,
        )

    for label in ["Deutsche Bank", "Commerzbank"]:
        matching_files = source_files_for_label(source_files, label)
        documents.extend(
            similarity_search_by_source_file(
                vector_store,
                query=question,
                source_files=matching_files,
                k=per_source_k,
            )
        )

    if include_regulatory_context and needs_regulatory_context(question):
        regulatory_files = []
        for label in ["EBA", "Basel"]:
            regulatory_files.extend(source_files_for_label(source_files, label))

        regulatory_k = max(1, min(2, per_source_k))
        documents.extend(
            similarity_search_by_source_file(
                vector_store,
                query=question,
                source_files=regulatory_files,
                k=regulatory_k,
            )
        )

    documents = dedupe_documents(documents)[:MAX_COMPARISON_CHUNKS]
    return documents, RetrievalInfo(
        mode="comparison",
        counts_by_source=count_documents_by_source(documents),
    )


def retrieve_documents(
    vector_store,
    question: str,
    k: int = DEFAULT_TOP_K,
    per_source_k: int = DEFAULT_PER_SOURCE_K,
    per_risk_k: int = DEFAULT_PER_RISK_K,
    include_regulatory_context: bool = True,
    use_planner: bool = False,
) -> tuple[list[Document], RetrievalInfo]:
    """Choose normal or balanced source-aware retrieval for the question."""
    if use_planner:
        return planner_retrieval(
            vector_store,
            question=question,
            per_risk_k=per_risk_k,
            grade_evidence=grade_evidence,
            evidence_top_n=evidence_top_n,
        )

    if is_bank_comparison(question):
        return comparison_retrieval(
            vector_store,
            question=question,
            per_source_k=per_source_k,
            per_risk_k=per_risk_k,
            include_regulatory_context=include_regulatory_context,
        )
    return normal_retrieval(vector_store, question, k)


def run_rag_answer(
    vector_store,
    question: str,
    k: int = DEFAULT_TOP_K,
    per_source_k: int = DEFAULT_PER_SOURCE_K,
    per_risk_k: int = DEFAULT_PER_RISK_K,
    include_regulatory_context: bool = True,
    use_planner: bool = False,
    grade_evidence: bool = False,
    evidence_top_n: int = 2,
    retrieval_log_callback: Callable[[RetrievalInfo], None] | None = None,
) -> tuple[str, list[Document], RetrievalInfo]:
    """Retrieve relevant chunks and answer with the configured chat model."""
    documents, retrieval_info = retrieve_documents(
        vector_store,
        question=question,
        k=k,
        per_source_k=per_source_k,
        per_risk_k=per_risk_k,
        include_regulatory_context=include_regulatory_context,
        use_planner=use_planner,
        grade_evidence=grade_evidence,
        evidence_top_n=evidence_top_n,
    )
    if retrieval_log_callback:
        retrieval_log_callback(retrieval_info)

    if retrieval_info.planner_tasks:
        context = format_planner_documents(documents)
    else:
        context = format_retrieved_documents(documents)

    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.2)
    chain = create_prompt() | llm
    response = chain.invoke({"question": question, "context": context})
    return response.content, documents, retrieval_info
