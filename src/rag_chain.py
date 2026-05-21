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
from src.vector_store import list_source_files, similarity_search_by_source_file


ANSWER_PROMPT = """You are a careful financial document analysis assistant.

Answer the question using only the retrieved context below.
If the context is insufficient, say what is missing. Do not invent facts.
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


def comparison_retrieval(
    vector_store,
    question: str,
    per_source_k: int = DEFAULT_PER_SOURCE_K,
    per_risk_k: int = DEFAULT_PER_RISK_K,
    include_regulatory_context: bool = True,
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
) -> tuple[list[Document], RetrievalInfo]:
    """Choose normal or balanced source-aware retrieval for the question."""
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
    )
    if retrieval_log_callback:
        retrieval_log_callback(retrieval_info)

    context = format_retrieved_documents(documents)

    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.2)
    chain = create_prompt() | llm
    response = chain.invoke({"question": question, "context": context})
    return response.content, documents, retrieval_info
