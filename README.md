# Agentic RAG Finance Advisor - Simple RAG Baseline

A cost-optimized, CLI-first RAG baseline for financial document analysis. It ingests only finance/risk-relevant PDF pages, stores local embeddings in ChromaDB, and answers questions with retrieved evidence only.

This is the first working version before adding agentic components such as query planning, reasoning, risk analysis, and advisory agents.

## Folder Structure

```text
agentic_rag_finance/
├── data/
│   └── raw_pdfs/
├── vector_db/
│   └── chroma/
├── scripts/
│   ├── ingest.py
│   ├── ask.py
│   └── reset_vector_db.py
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── pdf_loader.py
│   ├── text_filter.py
│   ├── vector_store.py
│   └── rag_chain.py
├── outputs/
│   └── logs/
├── requirements.txt
├── .gitignore
└── README.md
```

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

On Ubuntu, use `python3` instead of `python` if `python` is not installed.

Export your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key"
```

The key is read from the environment only. Do not hardcode it in the project.

## Ingestion

Run a dry-run first. This parses PDFs, filters useful pages, estimates volume, and creates no embeddings:

```bash
python scripts/ingest.py --dry-run
```

Run real ingestion with a page cap per PDF:

```bash
python scripts/ingest.py --max-pages-per-pdf 200
```

If a vector DB already exists, the script asks before deleting it. To reset automatically before ingestion:

```bash
python scripts/ingest.py --max-pages-per-pdf 200 --force
```

## Ask Questions

Start the CLI:

```bash
python scripts/ask.py
```

Retrieve a different number of chunks:

```bash
python scripts/ask.py --k 8
```

Use the V1 query planner agent for structured retrieval:

```bash
python scripts/ask.py --planner
```

Use the V2 evidence grader agent to filter weak retrieved chunks before answering:

```bash
python scripts/ask.py --planner --grade-evidence
```

V1 plans retrieval into structured tasks. V2 grades the retrieved evidence for each task using deterministic relevance heuristics, then passes only kept evidence into the final answer generator.

Use the V3 answer critic agent to self-check and improve the final answer:

```bash
python scripts/ask.py --planner --grade-evidence --critic
```

V3 reviews the draft answer against the already retrieved evidence. It does not retrieve new documents. It helps reduce overclaiming, preserve uncertainty, and improve consulting-style recommendations.

Use the V4 report generator agent to export a professional Markdown report:

```bash
python scripts/ask.py --planner --grade-evidence --critic --report
```

Optional report filename:

```bash
python scripts/ask.py --planner --grade-evidence --critic --report --report-name deutsche_vs_commerzbank_v4.md
```

V4 turns the reviewed answer, retrieval plan, evidence grading summary, critic review, and sources into a reusable report under `outputs/reports/`.

Use the V5 evaluation agent to score the current run:

```bash
python scripts/ask.py --planner --grade-evidence --critic --report --evaluate
```

Optional evaluation filename:

```bash
python scripts/ask.py --planner --grade-evidence --critic --report --evaluate --evaluation-name v5_deutsche_vs_commerzbank_eval.md
```

V5 scores the run with deterministic benchmarking metrics: Retrieval Completeness, Source Relevance, Evidence Grounding, Comparative Reasoning, Risk-Specific Reasoning, Overclaiming Control, Recommendation Quality, Limitations Quality, Source Transparency, and Report Quality.

Use the V6 retrieval repair agent to retry weak or missing evidence tasks:

```bash
python scripts/ask.py --planner --grade-evidence --repair-retrieval --critic --report --evaluate
```

V6 runs after evidence grading and before final answer generation. It detects planner tasks with weak or missing evidence, creates targeted fallback queries, retrieves a small number of additional chunks, re-grades them, and merges kept repaired evidence into the final context.

## V7 — Streamlit Dashboard UI

V7 adds a simple browser dashboard for running and inspecting the same backend pipeline used by the CLI. The app lets you enter a finance question, enable or disable pipeline agents, and inspect the final answer, retrieval plan, evidence grading, retrieval repair, critic review, generated report, and evaluation scores.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the dashboard from the repo root:

```bash
streamlit run apps/streamlit_app.py
```

The app expects `OPENAI_API_KEY` to be available in the environment.

## V8 — Multi-Question Benchmark Dataset

V8 evaluates the Agentic Finance RAG pipeline across multiple finance questions instead of one fixed prompt. It uses `data/evaluation_questions.json`, runs the full pipeline for each question, and saves JSON plus Markdown benchmark results under `outputs/benchmarks/`.

Run the full benchmark:

```bash
python scripts/run_benchmark.py
```

Run only the first three questions:

```bash
python scripts/run_benchmark.py --limit 3
```

Use an explicit question file and output directory:

```bash
python scripts/run_benchmark.py --questions data/evaluation_questions.json --output-dir outputs/benchmarks
```

The benchmark runner uses Query Planner, Evidence Grader, Retrieval Repair, Answer Critic, Report Generator, and Evaluation Agent by default. It continues if a single question fails and records the failure in the benchmark outputs.

### V8.2 — Question-Type-Aware Evaluation

Benchmark questions are not all the same. A single-bank liquidity question should not be penalized heavily for lacking two-bank comparative reasoning. V8.2 keeps raw metric scores visible, but computes the overall score with category-aware weights from the benchmark question metadata.

Example questions:

1. Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk.
2. What are the key regulatory risks mentioned in the documents?
3. Which risk areas should a financial services consultant investigate further?

### V8.3 — Benchmark Error Analysis

V8.3 reads an existing benchmark result JSON and produces a deterministic Markdown error analysis report. It identifies the strongest and weakest questions, summarizes metric weaknesses, analyzes category-level performance, highlights retrieval repair gaps, and recommends practical next improvements.

Analyze the latest benchmark JSON:

```bash
python3 scripts/analyze_benchmark.py
```

Analyze a specific benchmark JSON:

```bash
python3 scripts/analyze_benchmark.py --input outputs/benchmarks/v8_benchmark_results_20260523_022745.json
```

The default report is written to `outputs/evaluations/v8_3_benchmark_error_analysis.md`. This script does not run the RAG pipeline, call OpenAI, retrieve documents, or require an API key.

## V9 — HTML/PDF Report Export

V4 generated professional Markdown reports. V9 adds a report export layer that converts those Markdown reports into styled, shareable HTML and optional PDF. HTML export is built in and reliable. PDF export uses WeasyPrint when installed, and fails gracefully if WeasyPrint or its system dependencies are unavailable.

Export an existing Markdown report to HTML:

```bash
python3 scripts/export_report.py --input outputs/reports/example.md --html
```

Export HTML and PDF:

```bash
python3 scripts/export_report.py --input outputs/reports/example.md --html --pdf
```

Run the full pipeline with report export:

```bash
python3 scripts/ask.py --planner --grade-evidence --repair-retrieval --critic --report --export-html --export-pdf --evaluate
```

PDF export is optional. To enable it, install WeasyPrint:

```bash
pip install weasyprint
```

Depending on the operating system, WeasyPrint may also require system packages. If PDF export fails, the HTML report is still generated.

### V9.1 — PDF / Report Polish

V9.1 improves generated report readability for HTML and PDF exports. It cleans bullet and list rendering, improves table spacing and page-break behavior, adds more consulting-style HTML/PDF styling, and replaces the generic Risk Comparison text with deterministic comparison paragraphs based on available evidence and repair summaries.

## V10 — LangGraph Workflow Refactor

V10 wraps the existing Agentic Finance RAG pipeline in a LangGraph `StateGraph`. Previous versions built the agents and pipeline behavior; V10 keeps that logic intact and adds graph-based orchestration. Each major component becomes a graph node, and conditional edges route retrieval repair, answer criticism, report generation, HTML/PDF export, and evaluation.

The original CLI, benchmark runner, export script, benchmark analysis script, and Streamlit app remain available. The graph workflow is optional through `scripts/run_graph.py`.

Run the graph workflow:

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

Export the workflow as Mermaid:

```bash
python3 scripts/run_graph.py --export-mermaid
```

## Reset Vector DB

```bash
python scripts/reset_vector_db.py
```

The script asks for confirmation before deleting `vector_db/chroma`.

## Cost Optimization

This baseline avoids blindly embedding every page. During ingestion it:

- Extracts text page by page.
- Removes tiny pages.
- Keeps only pages containing finance/risk keywords.
- Caps selected pages per PDF with `--max-pages-per-pdf`.
- Splits only selected pages into chunks of about 1000 characters with 150 character overlap.
- Uses `text-embedding-3-small` for lower embedding cost.
- Retrieves only top 6 chunks by default during Q&A.
- Truncates long retrieved chunks before sending context to `gpt-4o-mini`.

## Models

- Embeddings: `text-embedding-3-small`
- Chat: `gpt-4o-mini`
- Vector database: local ChromaDB at `vector_db/chroma`

## Future Roadmap

- Add fallback retrieval strategies for more institutions and risk types
- Add Reasoning Agent
- Add Risk Agent
- Add Advisor Agent
- Add deployment configuration
