"""Streamlit dashboard for the Agentic Finance RAG pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_EVIDENCE_TOP_N  # noqa: E402
from src.rag_chain import run_rag_pipeline  # noqa: E402


DEFAULT_QUESTION = (
    "Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, "
    "and regulatory risk. Which bank appears riskier and what should a consultant recommend?"
)


def to_dataframe_retrieval_plan(plan: list[dict] | None) -> list[dict]:
    """Convert planner tasks into display rows."""
    return [
        {
            "Step": index,
            "Entity": task.get("entity", "unknown"),
            "Risk Type": task.get("risk_type", "unknown"),
            "Search Query": task.get("search_query", "unknown"),
            "Purpose": task.get("purpose", ""),
        }
        for index, task in enumerate(plan or [], start=1)
    ]


def to_dataframe_retrieval_summary(summary: Any) -> list[dict]:
    """Convert retrieval summary metadata into display rows."""
    if isinstance(summary, list):
        return [
            {
                "Entity": item.get("entity", "unknown"),
                "Risk Type": item.get("risk_type", "unknown"),
                "Chunks Retrieved": item.get("count", 0),
            }
            for item in summary
        ]
    if isinstance(summary, dict):
        return [
            {"Entity": source, "Risk Type": "all", "Chunks Retrieved": count}
            for source, count in summary.items()
        ]
    return []


def best_evidence_values(task_summary: dict) -> tuple[str, float]:
    """Return best relevance and score from a task evidence summary."""
    items = task_summary.get("items", [])
    if not items:
        return "n/a", 0.0
    best = max(items, key=lambda item: float(item.get("score", 0.0)))
    return best.get("relevance", "n/a"), float(best.get("score", 0.0))


def to_dataframe_evidence_summary(summary: list[dict] | None) -> list[dict]:
    """Convert evidence grading summary into task-level rows."""
    rows = []
    for item in summary or []:
        best_relevance, best_score = best_evidence_values(item)
        rows.append(
            {
                "Entity": item.get("entity", "unknown"),
                "Risk Type": item.get("risk_type", "unknown"),
                "Kept": item.get("kept", 0),
                "Removed": item.get("removed", 0),
                "Best Relevance": best_relevance,
                "Best Score": round(best_score, 2),
            }
        )
    return rows


def to_dataframe_evidence_details(summary: list[dict] | None) -> list[dict]:
    """Convert chunk-level grading details into display rows."""
    rows = []
    for task in summary or []:
        for item in task.get("items", []):
            rows.append(
                {
                    "Entity": task.get("entity", "unknown"),
                    "Risk Type": task.get("risk_type", "unknown"),
                    "Relevance": item.get("relevance", "unknown"),
                    "Score": round(float(item.get("score", 0.0)), 2),
                    "Page": item.get("page", "unknown"),
                    "Status": "kept" if item.get("keep") else "removed",
                }
            )
    return rows


def to_dataframe_repair_summary(summary: list[dict] | None) -> list[dict]:
    """Convert retrieval repair summary into display rows."""
    return [
        {
            "Entity": item.get("entity", "unknown"),
            "Risk Type": item.get("risk_type", "unknown"),
            "Status": item.get("status", "unknown"),
            "Additional Retrieved": item.get("additional_chunks_retrieved", 0),
            "Additional Kept": item.get("additional_chunks_kept", 0),
            "Best Repaired Score": round(float(item.get("best_repaired_score", 0.0)), 2),
        }
        for item in summary or []
    ]


def to_dataframe_evaluation_scores(evaluation: dict | None) -> list[dict]:
    """Convert evaluation metric scores into display rows."""
    if not evaluation:
        return []
    labels = {
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
    scores = evaluation.get("scores", {})
    notes = evaluation.get("notes", {})
    return [
        {
            "Metric": label,
            "Score": "not scored" if scores.get(key) is None else f"{scores.get(key)}/5",
            "Notes": notes.get(key, ""),
        }
        for key, label in labels.items()
    ]


def load_file_text(path: str | None) -> str | None:
    """Read a generated report/evaluation file if it exists."""
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = PROJECT_ROOT / file_path
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def safe_download_button(label: str, path: str | None, mime_type: str = "text/markdown") -> None:
    """Render a download button for a generated file."""
    content = load_file_text(path)
    if not content or not path:
        return
    st.download_button(
        label,
        data=content,
        file_name=Path(path).name,
        mime=mime_type,
    )


def show_sources(sources: dict | None) -> None:
    """Display retrieved source file/page metadata."""
    rows = [
        {"Source File": source_file, "Pages": ", ".join(str(page) for page in pages)}
        for source_file, pages in (sources or {}).items()
    ]
    if rows:
        st.table(rows)
    else:
        st.info("No source metadata was available.")


st.set_page_config(page_title="Agentic Finance RAG Dashboard", layout="wide")

st.title("Agentic Finance RAG Dashboard")
st.caption(
    "Query planning, evidence grading, retrieval repair, answer criticism, "
    "report generation, and evaluation for financial documents."
)

with st.sidebar:
    st.header("Pipeline Options")
    use_planner = st.checkbox("Use Query Planner Agent", value=True)
    grade_evidence = st.checkbox("Use Evidence Grader Agent", value=True)
    repair_retrieval = st.checkbox("Use Retrieval Repair Agent", value=True)
    use_critic = st.checkbox("Use Answer Critic Agent", value=True)
    generate_report = st.checkbox("Generate Report", value=True)
    run_evaluation = st.checkbox("Run Evaluation Agent", value=True)

    with st.expander("Advanced settings"):
        evidence_top_n = st.number_input(
            "evidence_top_n",
            min_value=1,
            max_value=5,
            value=DEFAULT_EVIDENCE_TOP_N,
            step=1,
        )
        repair_top_k = st.number_input("repair_top_k", min_value=1, max_value=10, value=3, step=1)
        repair_max_queries = st.number_input(
            "repair_max_queries",
            min_value=1,
            max_value=10,
            value=4,
            step=1,
        )
        repair_min_kept = st.number_input(
            "repair_min_kept",
            min_value=0,
            max_value=5,
            value=1,
            step=1,
        )
        repair_min_score = st.number_input(
            "repair_min_score",
            min_value=0.0,
            max_value=1.0,
            value=0.40,
            step=0.05,
        )

question = st.text_area("Question", value=DEFAULT_QUESTION, height=130)
run_button = st.button("Run Agentic RAG", type="primary")

if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY is not set. Please export it before running the app.")

if run_button:
    if not question.strip():
        st.warning("Please enter a question.")
    elif not os.getenv("OPENAI_API_KEY"):
        st.stop()
    else:
        try:
            with st.spinner("Running Agentic Finance RAG pipeline..."):
                st.session_state["rag_result"] = run_rag_pipeline(
                    question=question.strip(),
                    use_planner=use_planner,
                    grade_evidence=grade_evidence,
                    repair_retrieval=repair_retrieval,
                    use_critic=use_critic,
                    generate_report=generate_report,
                    evaluate=run_evaluation,
                    evidence_top_n=int(evidence_top_n),
                    repair_top_k=int(repair_top_k),
                    repair_max_queries=int(repair_max_queries),
                    repair_min_kept=int(repair_min_kept),
                    repair_min_score=float(repair_min_score),
                )
            st.success("Pipeline completed successfully.")
        except Exception as exc:
            st.error(f"Pipeline failed: {exc}")
            with st.expander("Debug details"):
                st.exception(exc)

result = st.session_state.get("rag_result")
if not result:
    st.info("Configure the pipeline and click Run Agentic RAG to start.")
    st.stop()

tabs = st.tabs(
    [
        "Final Answer",
        "Retrieval Plan",
        "Evidence Grading",
        "Retrieval Repair",
        "Answer Critic",
        "Report",
        "Evaluation",
    ]
)

with tabs[0]:
    st.subheader("Final Answer")
    st.caption(f"Retrieval mode: {result.get('retrieval_mode', 'unknown')}")
    st.markdown(result.get("final_answer", "No answer was generated."))
    st.subheader("Sources")
    show_sources(result.get("retrieved_sources"))

with tabs[1]:
    st.subheader("Generated Retrieval Plan")
    plan_rows = to_dataframe_retrieval_plan(result.get("retrieval_plan"))
    if plan_rows:
        st.dataframe(plan_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Query Planner Agent was not used for this run.")

    st.subheader("Chunks Retrieved")
    retrieval_rows = to_dataframe_retrieval_summary(result.get("retrieval_summary"))
    if retrieval_rows:
        st.dataframe(retrieval_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No retrieval summary was available.")

with tabs[2]:
    st.subheader("Evidence Grading Summary")
    evidence_rows = to_dataframe_evidence_summary(result.get("evidence_grading_summary"))
    if evidence_rows:
        st.dataframe(evidence_rows, use_container_width=True, hide_index=True)
        with st.expander("Chunk-level grading details"):
            detail_rows = to_dataframe_evidence_details(result.get("evidence_grading_summary"))
            if detail_rows:
                st.dataframe(detail_rows, use_container_width=True, hide_index=True)
            else:
                st.info("No chunk-level grading details were available.")
    else:
        st.info("Evidence Grader Agent was not used for this run.")

with tabs[3]:
    st.subheader("Retrieval Repair Summary")
    repair_rows = to_dataframe_repair_summary(result.get("retrieval_repair_summary"))
    if repair_rows:
        st.dataframe(repair_rows, use_container_width=True, hide_index=True)
        for item in result.get("retrieval_repair_summary") or []:
            if item.get("status") == "attempted_no_improvement":
                st.warning(
                    f"Repair was attempted for {item.get('entity')} / "
                    f"{item.get('risk_type')}, but no stronger evidence was found."
                )
    else:
        st.info("Retrieval Repair Agent was not used for this run.")

with tabs[4]:
    st.subheader("Answer Critic")
    critic = result.get("critic_summary")
    if critic:
        passed = bool(critic.get("passed"))
        issues = critic.get("issues", [])
        main_issue = issues[0].get("message", "None") if issues else "None"
        if passed:
            st.success("Answer critic passed the final answer.")
        else:
            st.warning("Answer critic found issues and rewrote the final answer.")
        st.write(f"**passed:** {str(passed).lower()}")
        st.write(f"**issues found:** {len(issues)}")
        st.write(f"**main issue:** {main_issue}")
        st.write(f"**critic summary:** {critic.get('critic_summary', '')}")
    else:
        st.info("Answer Critic Agent was not used for this run.")

with tabs[5]:
    st.subheader("Report")
    report_path = result.get("report_path")
    report_content = result.get("report_content") or load_file_text(report_path)
    if report_path and report_content:
        st.write(f"**Report path:** `{report_path}`")
        safe_download_button("Download Markdown Report", report_path)
        with st.expander("Report preview", expanded=True):
            st.markdown(report_content)
    else:
        st.info("Report generation was disabled.")

with tabs[6]:
    st.subheader("Evaluation")
    evaluation = result.get("evaluation")
    if evaluation:
        st.metric("Overall Score", f"{evaluation.get('overall_score', 0.0)}/5")
        score_rows = to_dataframe_evaluation_scores(evaluation)
        if score_rows:
            st.dataframe(score_rows, use_container_width=True, hide_index=True)
        st.write("**Strengths**")
        st.markdown("\n".join(f"- {item}" for item in evaluation.get("strengths", [])))
        st.write("**Weaknesses**")
        weaknesses = evaluation.get("weaknesses", [])
        st.markdown(
            "\n".join(f"- {item}" for item in weaknesses)
            if weaknesses
            else "- No major weaknesses identified by deterministic heuristics."
        )
        st.write("**Recommendations**")
        st.markdown("\n".join(f"- {item}" for item in evaluation.get("recommendations", [])))
        evaluation_path = result.get("evaluation_path")
        if evaluation_path:
            st.write(f"**Evaluation path:** `{evaluation_path}`")
            safe_download_button("Download Evaluation Markdown", evaluation_path)
    else:
        st.info("Evaluation was disabled.")
