# V5 Evaluation Agent / Benchmarking Framework

## What V5 Adds

V5 adds a deterministic Evaluation Agent that scores one completed Agentic Finance RAG run. It does not change retrieval, evidence grading, answer criticism, or report generation. It measures the quality of the current run using structured metrics and saves the results as Markdown.

## Command Used

```bash
python3 scripts/ask.py --planner --grade-evidence --critic --report --evaluate --evaluation-name v5_deutsche_vs_commerzbank_eval.md
```

## Metrics Used

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

## Example Evaluation Summary

```text
Evaluation summary:
- Retrieval Completeness: 4/5
- Source Relevance: 4/5
- Evidence Grounding: 4/5
- Comparative Reasoning: 4/5
- Risk-Specific Reasoning: 5/5
- Overclaiming Control: 4/5
- Recommendation Quality: 4/5
- Limitations Quality: 5/5
- Source Transparency: 5/5
- Report Quality: 4/5
- Overall Score: 4.3/5
```

## Comparison Against Earlier Milestones

V0: Simple risk-aware RAG baseline that retrieves and answers directly.

V1: Adds a Query Planner Agent for structured retrieval.

V2: Adds an Evidence Grader Agent for relevance-based filtering.

V3: Adds an Answer Critic Agent for self-checking and safer final answers.

V4: Adds a Report Generator Agent for professional Markdown report output.

V5: Adds an Evaluation Agent for deterministic quality scoring and benchmarking.

## Limitations of V5

- The evaluation is deterministic and heuristic-based.
- It is not a substitute for human expert review.
- It does not verify external truth beyond retrieved sources.
- It does not provide investment advice.
- Scores are most useful for comparing runs over time, not as absolute quality guarantees.
