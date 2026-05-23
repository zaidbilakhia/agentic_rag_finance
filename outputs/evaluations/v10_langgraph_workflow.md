# V10 LangGraph Workflow Orchestration

## What V10 Adds

V10 wraps the existing Agentic Finance RAG pipeline in a LangGraph `StateGraph` workflow.

This is an orchestration refactor, not a rewrite. The graph reuses the existing project modules for planning, retrieval, evidence grading, retrieval repair, answer generation, answer criticism, report generation, report export, and evaluation.

## Why LangGraph Was Introduced After V9

V0 through V9.1 built and polished the functional pipeline:

- Retrieval and answer generation.
- Planner, grader, critic, repair, report, and evaluation agents.
- Benchmarking and benchmark analysis.
- HTML/PDF report export and PDF polish.

V10 adds a clearer workflow structure after those components are stable. LangGraph makes the pipeline easier to inspect, route, and extend without changing the underlying agent logic.

## Graph Nodes

The V10 workflow includes these nodes:

- `plan_query`
- `retrieve_documents`
- `grade_evidence`
- `repair_retrieval`
- `generate_answer`
- `critique_answer`
- `generate_report`
- `export_report`
- `evaluate_run`

Small pass-through routing nodes are used for optional report, export, and evaluation branches.

## Conditional Routing

The graph routes based on state flags:

- `repair_retrieval=true` routes from grading to retrieval repair.
- `use_critic=true` routes from answer generation to the critic.
- `generate_report=true` routes to Markdown report generation.
- `export_html=true` or `export_pdf=true` routes to report export.
- `evaluate=true` routes to deterministic evaluation.

If an optional step is disabled, the graph skips it and continues to the next routing point.

## Reused Existing Modules

V10 reuses:

- `src/query_planner.py`
- `src/evidence_grader.py`
- `src/retrieval_repair.py`
- `src/answer_critic.py`
- `src/report_generator.py`
- `src/report_exporter.py`
- `src/evaluation_agent.py`
- helper functions from `src/rag_chain.py`

The original `run_rag_pipeline` remains available and unchanged for CLI, benchmark, and Streamlit compatibility.

## Command Examples

Run the graph with a question:

```bash
python3 scripts/run_graph.py \
  --question "Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?" \
  --planner \
  --grade-evidence \
  --repair-retrieval \
  --critic \
  --report \
  --export-html \
  --evaluate
```

Export the Mermaid workflow diagram:

```bash
python3 scripts/run_graph.py --export-mermaid
```

## Limitations

- V10 does not change retrieval quality or model behavior by itself.
- It does not replace the existing CLI, benchmark runner, or Streamlit dashboard.
- The graph runner still requires `OPENAI_API_KEY` for answer generation.
- Mermaid rendering depends on LangGraph support; a static fallback diagram is written if needed.
- The graph currently focuses on orchestration clarity, not persistence, checkpointing, or background execution.
