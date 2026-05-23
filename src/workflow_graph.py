"""V10 LangGraph orchestration for the Agentic Finance RAG pipeline."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from src.answer_critic import critique_answer
from src.config import (
    CHAT_MODEL,
    DEFAULT_EVIDENCE_TOP_N,
    DEFAULT_PER_RISK_K,
    DEFAULT_TOP_K,
    MAX_COMPARISON_CHUNKS,
    PROJECT_ROOT,
    require_openai_api_key,
)
from src.evaluation_agent import evaluate_run, save_evaluation_markdown
from src.evidence_grader import grade_planner_results
from src.query_planner import plan_query
from src.rag_chain import (
    copy_document_with_planner_task,
    count_documents_by_source,
    create_prompt,
    dedupe_documents,
    format_planner_documents,
    format_retrieved_documents,
    merge_repair_grading_summary,
    planner_source_files,
    retrieve_documents,
)
from src.report_exporter import export_report
from src.report_generator import collect_sources_from_documents
from src.report_generator import generate_report as write_report
from src.retrieval_repair import repair_retrieval_results
from src.vector_store import (
    list_source_files,
    load_vector_store,
    similarity_search_by_source_file,
)


class FinanceRAGState(TypedDict, total=False):
    """Shared LangGraph state for the finance RAG workflow."""

    question: str

    use_planner: bool
    grade_evidence: bool
    repair_retrieval: bool
    use_critic: bool
    generate_report: bool
    evaluate: bool
    export_html: bool
    export_pdf: bool

    evidence_top_n: int
    repair_top_k: int
    repair_max_queries: int
    repair_min_kept: int
    repair_min_score: float

    report_name: str | None
    evaluation_name: str | None
    export_name: str | None

    retrieval_mode: str

    retrieval_plan: list[dict]
    retrieval_summary: Any
    retrieved_documents: list[dict]

    evidence_grading_summary: list[dict]
    initial_evidence_grading_summary: list[dict]
    graded_evidence: list[dict]

    retrieval_repair_summary: list[dict]

    final_answer: str
    draft_answer: str

    critic_summary: dict

    report_path: str | None
    report_content: str | None

    html_report_path: str | None
    pdf_report_path: str | None
    export_summary: dict

    evaluation: dict
    evaluation_path: str | None

    retrieved_sources: dict

    errors: list[str]

    vector_store: Any
    documents: list[Document]
    initial_documents: list[Document]
    evidence_context: str


def document_to_summary(doc: Document) -> dict:
    """Create lightweight document metadata for graph output inspection."""
    return {
        "source_file": doc.metadata.get("source_file", "unknown"),
        "page_number": doc.metadata.get("page_number", "unknown"),
        "retrieval_entity": doc.metadata.get("retrieval_entity"),
        "retrieval_focus": doc.metadata.get("retrieval_focus"),
        "evidence_relevance": doc.metadata.get("evidence_relevance"),
        "evidence_score": doc.metadata.get("evidence_score"),
        "text_preview": doc.page_content[:240],
    }


def retrieve_with_plan(
    vector_store: Any,
    tasks: list[dict],
    per_risk_k: int = DEFAULT_PER_RISK_K,
) -> tuple[list[Document], list[dict]]:
    """Run planner-task retrieval using the same helpers as rag_chain."""
    source_files = list_source_files(vector_store)
    documents: list[Document] = []
    counts_by_task: list[dict] = []

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

    return dedupe_documents(documents)[:MAX_COMPARISON_CHUNKS], counts_by_task


def append_error(state: FinanceRAGState, message: str) -> list[str]:
    """Append an error message to existing state errors."""
    return [*(state.get("errors") or []), message]


def node_plan_query(state: FinanceRAGState) -> dict:
    """Plan retrieval tasks when planner mode is enabled."""
    if not state.get("use_planner", True):
        return {"retrieval_plan": []}
    return {"retrieval_plan": plan_query(state["question"])}


def node_retrieve_documents(state: FinanceRAGState) -> dict:
    """Retrieve initial evidence documents."""
    vector_store = state.get("vector_store") or load_vector_store()
    question = state["question"]
    tasks = state.get("retrieval_plan") or []

    if state.get("use_planner", True) and tasks:
        documents, counts_by_task = retrieve_with_plan(vector_store, tasks)
        retrieval_mode = "query planner agent"
        retrieval_summary: Any = counts_by_task
    elif state.get("use_planner", True):
        documents, retrieval_info = retrieve_documents(
            vector_store,
            question=question,
            k=DEFAULT_TOP_K,
            use_planner=False,
        )
        retrieval_mode = "query planner agent"
        retrieval_summary = []
    else:
        documents, retrieval_info = retrieve_documents(
            vector_store,
            question=question,
            k=DEFAULT_TOP_K,
            use_planner=False,
        )
        retrieval_mode = retrieval_info.mode
        retrieval_summary = retrieval_info.counts_by_task or retrieval_info.counts_by_source

    return {
        "vector_store": vector_store,
        "documents": documents,
        "initial_documents": list(documents),
        "retrieval_mode": retrieval_mode,
        "retrieval_summary": retrieval_summary,
        "retrieved_documents": [document_to_summary(doc) for doc in documents],
    }


def node_grade_evidence(state: FinanceRAGState) -> dict:
    """Grade planner evidence when enabled."""
    if not state.get("grade_evidence", True) or not state.get("retrieval_plan"):
        return {}

    documents, grading_summary = grade_planner_results(
        state["question"],
        planner_tasks=state.get("retrieval_plan") or [],
        documents=state.get("documents") or [],
        top_n=int(state.get("evidence_top_n", DEFAULT_EVIDENCE_TOP_N)),
    )
    documents = documents[:MAX_COMPARISON_CHUNKS]
    return {
        "documents": documents,
        "retrieval_mode": "query planner agent + evidence grader",
        "retrieval_summary": state.get("retrieval_summary"),
        "initial_evidence_grading_summary": grading_summary,
        "evidence_grading_summary": grading_summary,
        "graded_evidence": grading_summary,
        "retrieved_documents": [document_to_summary(doc) for doc in documents],
    }


def node_repair_retrieval(state: FinanceRAGState) -> dict:
    """Repair weak planner evidence tasks when enabled."""
    if not state.get("repair_retrieval", True):
        return {}
    if not state.get("retrieval_plan") or not state.get("evidence_grading_summary"):
        return {}

    vector_store = state.get("vector_store") or load_vector_store()
    source_files = list_source_files(vector_store)

    def repair_retriever(task: dict, query: str, k: int) -> list[Document]:
        matching_files = planner_source_files(source_files, task)
        if matching_files:
            return similarity_search_by_source_file(
                vector_store,
                query=query,
                source_files=matching_files,
                k=k,
            )
        return vector_store.similarity_search(query, k=k)

    repair_result = repair_retrieval_results(
        question=state["question"],
        planner_tasks=state.get("retrieval_plan") or [],
        initial_documents=state.get("initial_documents") or [],
        kept_documents=state.get("documents") or [],
        evidence_summary=state.get("evidence_grading_summary") or [],
        retriever_fn=repair_retriever,
        top_k=int(state.get("repair_top_k", 3)),
        evidence_top_n=int(state.get("evidence_top_n", DEFAULT_EVIDENCE_TOP_N)),
        max_queries=int(state.get("repair_max_queries", 4)),
        min_kept=int(state.get("repair_min_kept", 1)),
        min_best_score=float(state.get("repair_min_score", 0.40)),
    )
    documents = repair_result["documents"][:MAX_COMPARISON_CHUNKS]
    merged_summary = merge_repair_grading_summary(
        state.get("evidence_grading_summary") or [],
        repair_result["repair_summary"],
    )
    return {
        "documents": documents,
        "retrieval_mode": "query planner agent + evidence grader + retrieval repair",
        "retrieval_repair_summary": repair_result["repair_summary"],
        "evidence_grading_summary": merged_summary,
        "retrieved_documents": [document_to_summary(doc) for doc in documents],
    }


def node_generate_answer(state: FinanceRAGState) -> dict:
    """Generate the draft/final answer from retrieved evidence."""
    documents = state.get("documents") or []
    if state.get("retrieval_plan"):
        context = format_planner_documents(documents)
    else:
        context = format_retrieved_documents(documents)

    llm = ChatOpenAI(model=CHAT_MODEL, temperature=0.2)
    chain = create_prompt() | llm
    response = chain.invoke({"question": state["question"], "context": context})
    answer = response.content
    return {
        "draft_answer": answer,
        "final_answer": answer,
        "evidence_context": context,
    }


def node_critique_answer(state: FinanceRAGState) -> dict:
    """Run the existing answer critic node."""
    critic_result = critique_answer(
        question=state["question"],
        draft_answer=state.get("draft_answer", state.get("final_answer", "")),
        evidence_context=state.get("evidence_context", ""),
        retrieval_plan=state.get("retrieval_plan"),
    )
    mode = state.get("retrieval_mode", "unknown")
    if "answer critic" not in mode:
        mode = f"{mode} + answer critic"
    return {
        "critic_summary": critic_result,
        "final_answer": critic_result["improved_answer"],
        "retrieval_mode": mode,
    }


def node_generate_report(state: FinanceRAGState) -> dict:
    """Generate the Markdown report."""
    documents = state.get("documents") or []
    sources = collect_sources_from_documents(documents)
    report_path = write_report(
        question=state["question"],
        final_answer=state.get("final_answer", ""),
        retrieval_plan=state.get("retrieval_plan"),
        retrieval_summary=state.get("retrieval_summary"),
        evidence_summary=state.get("evidence_grading_summary"),
        repair_summary=state.get("retrieval_repair_summary"),
        critic_summary=state.get("critic_summary"),
        sources=sources,
        report_name=state.get("report_name"),
    )
    report_file = PROJECT_ROOT / report_path
    report_content = report_file.read_text(encoding="utf-8") if report_file.exists() else None
    return {
        "report_path": report_path,
        "report_content": report_content,
        "retrieved_sources": sources,
    }


def node_export_report(state: FinanceRAGState) -> dict:
    """Export generated Markdown report to HTML/PDF when requested."""
    report_path = state.get("report_path")
    if not report_path:
        return {
            "errors": append_error(
                state,
                "Report export was requested, but no Markdown report was generated.",
            )
        }
    export_summary = export_report(
        markdown_path=report_path,
        export_html=bool(state.get("export_html") or state.get("export_pdf")),
        export_pdf=bool(state.get("export_pdf")),
        output_name=state.get("export_name"),
    )
    return {
        "export_summary": export_summary,
        "html_report_path": export_summary.get("html_path"),
        "pdf_report_path": export_summary.get("pdf_path"),
    }


def node_evaluate_run(state: FinanceRAGState) -> dict:
    """Evaluate the graph run with the existing deterministic evaluator."""
    documents = state.get("documents") or []
    sources = state.get("retrieved_sources") or collect_sources_from_documents(documents)
    evaluation = evaluate_run(
        question=state["question"],
        final_answer=state.get("final_answer", ""),
        retrieval_plan=state.get("retrieval_plan"),
        retrieval_summary=state.get("retrieval_summary"),
        evidence_summary=state.get("evidence_grading_summary"),
        critic_summary=state.get("critic_summary"),
        sources=sources,
        report_path=state.get("report_path"),
        report_content=state.get("report_content"),
        repair_summary=state.get("retrieval_repair_summary"),
    )
    evaluation_path = save_evaluation_markdown(
        evaluation,
        evaluation_name=state.get("evaluation_name"),
    )
    return {
        "evaluation": evaluation,
        "evaluation_path": evaluation_path,
        "retrieved_sources": sources,
    }


def node_passthrough(state: FinanceRAGState) -> dict:
    """No-op node used as a clear conditional routing point."""
    del state
    return {}


def route_after_grading(state: FinanceRAGState) -> str:
    """Route to repair only when repair is enabled and graded evidence exists."""
    if state.get("repair_retrieval") and state.get("evidence_grading_summary"):
        return "repair_retrieval"
    return "generate_answer"


def route_after_answer(state: FinanceRAGState) -> str:
    """Route to critic when enabled."""
    if state.get("use_critic"):
        return "critique_answer"
    return "maybe_report"


def route_after_critic(state: FinanceRAGState) -> str:
    """Continue after critic."""
    del state
    return "maybe_report"


def route_after_maybe_report(state: FinanceRAGState) -> str:
    """Route to report generation when enabled."""
    if state.get("generate_report"):
        return "generate_report"
    return "maybe_export"


def route_after_report(state: FinanceRAGState) -> str:
    """Continue after report generation."""
    del state
    return "maybe_export"


def route_after_maybe_export(state: FinanceRAGState) -> str:
    """Route to export when enabled."""
    if state.get("export_html") or state.get("export_pdf"):
        return "export_report"
    return "maybe_evaluate"


def route_after_export(state: FinanceRAGState) -> str:
    """Continue after export."""
    del state
    return "maybe_evaluate"


def route_after_maybe_evaluate(state: FinanceRAGState) -> str:
    """Route to evaluation when enabled."""
    if state.get("evaluate"):
        return "evaluate_run"
    return END


def build_finance_rag_graph():
    """Build and compile the V10 LangGraph StateGraph."""
    graph = StateGraph(FinanceRAGState)
    graph.add_node("plan_query", node_plan_query)
    graph.add_node("retrieve_documents", node_retrieve_documents)
    graph.add_node("grade_evidence", node_grade_evidence)
    graph.add_node("repair_retrieval", node_repair_retrieval)
    graph.add_node("generate_answer", node_generate_answer)
    graph.add_node("critique_answer", node_critique_answer)
    graph.add_node("maybe_report", node_passthrough)
    graph.add_node("generate_report", node_generate_report)
    graph.add_node("maybe_export", node_passthrough)
    graph.add_node("export_report", node_export_report)
    graph.add_node("maybe_evaluate", node_passthrough)
    graph.add_node("evaluate_run", node_evaluate_run)

    graph.add_edge(START, "plan_query")
    graph.add_edge("plan_query", "retrieve_documents")
    graph.add_edge("retrieve_documents", "grade_evidence")
    graph.add_conditional_edges(
        "grade_evidence",
        route_after_grading,
        {
            "repair_retrieval": "repair_retrieval",
            "generate_answer": "generate_answer",
        },
    )
    graph.add_edge("repair_retrieval", "generate_answer")
    graph.add_conditional_edges(
        "generate_answer",
        route_after_answer,
        {
            "critique_answer": "critique_answer",
            "maybe_report": "maybe_report",
        },
    )
    graph.add_conditional_edges(
        "critique_answer",
        route_after_critic,
        {"maybe_report": "maybe_report"},
    )
    graph.add_conditional_edges(
        "maybe_report",
        route_after_maybe_report,
        {
            "generate_report": "generate_report",
            "maybe_export": "maybe_export",
        },
    )
    graph.add_conditional_edges(
        "generate_report",
        route_after_report,
        {"maybe_export": "maybe_export"},
    )
    graph.add_conditional_edges(
        "maybe_export",
        route_after_maybe_export,
        {
            "export_report": "export_report",
            "maybe_evaluate": "maybe_evaluate",
        },
    )
    graph.add_conditional_edges(
        "export_report",
        route_after_export,
        {"maybe_evaluate": "maybe_evaluate"},
    )
    graph.add_conditional_edges(
        "maybe_evaluate",
        route_after_maybe_evaluate,
        {
            "evaluate_run": "evaluate_run",
            END: END,
        },
    )
    graph.add_edge("evaluate_run", END)
    return graph.compile()


@lru_cache(maxsize=1)
def compiled_finance_rag_graph():
    """Return a cached compiled graph."""
    return build_finance_rag_graph()


def run_graph_pipeline(
    question: str,
    use_planner: bool = True,
    grade_evidence: bool = True,
    repair_retrieval: bool = True,
    use_critic: bool = True,
    generate_report: bool = False,
    evaluate: bool = False,
    export_html: bool = False,
    export_pdf: bool = False,
    evidence_top_n: int = DEFAULT_EVIDENCE_TOP_N,
    repair_top_k: int = 3,
    repair_max_queries: int = 4,
    repair_min_kept: int = 1,
    repair_min_score: float = 0.40,
    report_name: str | None = None,
    evaluation_name: str | None = None,
    export_name: str | None = None,
) -> dict:
    """Run the V10 LangGraph workflow and return final state as a dict."""
    if repair_retrieval:
        use_planner = True
        grade_evidence = True
    if grade_evidence:
        use_planner = True
    if export_html or export_pdf:
        generate_report = True

    require_openai_api_key()
    initial_state: FinanceRAGState = {
        "question": question,
        "use_planner": use_planner,
        "grade_evidence": grade_evidence,
        "repair_retrieval": repair_retrieval,
        "use_critic": use_critic,
        "generate_report": generate_report,
        "evaluate": evaluate,
        "export_html": export_html,
        "export_pdf": export_pdf,
        "evidence_top_n": evidence_top_n,
        "repair_top_k": repair_top_k,
        "repair_max_queries": repair_max_queries,
        "repair_min_kept": repair_min_kept,
        "repair_min_score": repair_min_score,
        "report_name": report_name,
        "evaluation_name": evaluation_name,
        "export_name": export_name,
        "errors": [],
    }
    final_state = compiled_finance_rag_graph().invoke(initial_state)
    return dict(final_state)


STATIC_MERMAID = """flowchart TD
    START([START]) --> plan_query
    plan_query --> retrieve_documents
    retrieve_documents --> grade_evidence
    grade_evidence -->|repair_retrieval=true| repair_retrieval
    grade_evidence -->|repair_retrieval=false| generate_answer
    repair_retrieval --> generate_answer
    generate_answer -->|critic=true| critique_answer
    generate_answer -->|critic=false| maybe_report
    critique_answer --> maybe_report
    maybe_report -->|report=true| generate_report
    maybe_report -->|report=false| maybe_export
    generate_report --> maybe_export
    maybe_export -->|export=true| export_report
    maybe_export -->|export=false| maybe_evaluate
    export_report --> maybe_evaluate
    maybe_evaluate -->|evaluate=true| evaluate_run
    maybe_evaluate -->|evaluate=false| END([END])
    evaluate_run --> END
"""


def export_graph_mermaid(
    output_path: str = "outputs/evaluations/v10_langgraph_workflow.mmd",
) -> str:
    """Export the V10 workflow graph as Mermaid text."""
    path = Path(output_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)

    mermaid = STATIC_MERMAID
    try:
        graph = compiled_finance_rag_graph()
        drawable = graph.get_graph()
        if hasattr(drawable, "draw_mermaid"):
            mermaid = drawable.draw_mermaid()
    except Exception:
        mermaid = STATIC_MERMAID

    path.write_text(mermaid.strip() + "\n", encoding="utf-8")
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
