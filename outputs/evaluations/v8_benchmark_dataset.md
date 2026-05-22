# V8 Multi-Question Benchmark Dataset

## What V8 Adds

V8 adds a small benchmark dataset and a batch runner for evaluating the Agentic Finance RAG pipeline across multiple finance questions.

New files:

- `data/evaluation_questions.json`
- `scripts/run_benchmark.py`

The benchmark runner calls the existing backend pipeline instead of reimplementing retrieval, grading, repair, criticism, reporting, or evaluation logic.

## Why Benchmark Testing Was Added After V7

V7 made the system demo-ready through a Streamlit dashboard. V8 adds repeatable benchmark coverage so the project can show performance across more than one hand-tested question.

## Dataset Location

```text
data/evaluation_questions.json
```

The dataset includes questions covering:

- full bank comparison
- single-bank liquidity risk
- single-bank operational risk
- regulatory risk comparison
- missing Commerzbank liquidity evidence behavior
- EBA regulatory context
- consultant recommendations
- evidence strength and weakness
- source-backed executive summaries

## Benchmark Runner Command

```bash
python3 scripts/run_benchmark.py
```

Optional limited run:

```bash
python3 scripts/run_benchmark.py --limit 3
```

## Metrics Aggregated

The benchmark aggregates V5 evaluation metrics:

- Retrieval Completeness
- Source Relevance
- Evidence Grounding
- Comparative Reasoning
- Risk-Specific Reasoning
- Overclaiming Control
- Recommendation Quality
- Limitations Quality
- Source Transparency
- Report Quality

## Expected Outputs

Timestamped benchmark files are saved under:

```text
outputs/benchmarks/
```

Expected files:

- `v8_benchmark_results_YYYYMMDD_HHMMSS.json`
- `v8_benchmark_results_YYYYMMDD_HHMMSS.md`

## Limitations

- The benchmark dataset is intentionally small.
- The evaluator is deterministic and heuristic.
- Results are not a human expert review.
- The benchmark does not verify financial truth outside retrieved sources.
- Outputs are not investment advice.
