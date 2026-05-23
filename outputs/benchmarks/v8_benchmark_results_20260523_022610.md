# V8 Multi-Question Benchmark Report

## 1. Benchmark Summary

- Questions evaluated: 2
- Questions completed: 2
- Questions failed: 0
- Average overall score: 4.0/5
- Pipeline used:
  - Query Planner Agent
  - Evidence Grader Agent
  - Retrieval Repair Agent
  - Answer Critic Agent
  - Report Generator Agent
  - Evaluation Agent

## 2. Average Metric Scores

| Metric | Average Score |
|---|---|
| Retrieval Completeness | 4.0/5 |
| Source Relevance | 3.0/5 |
| Evidence Grounding | 4.5/5 |
| Comparative Reasoning | 2.5/5 |
| Risk-Specific Reasoning | 3.5/5 |
| Overclaiming Control | 3.5/5 |
| Recommendation Quality | 3.5/5 |
| Limitations Quality | 4.0/5 |
| Source Transparency | 5.0/5 |
| Report Quality | 5.0/5 |

## 3. Per-Question Results

| ID | Category | Overall Score | Main Weakness | Report | Evaluation |
|---|---|---|---|---|---|
| q1_bank_risk_comparison | bank_comparison | 4.2/5 | Evidence relevance could be improved. | [v8_q1_bank_risk_comparison_report.md](../../outputs/reports/v8_q1_bank_risk_comparison_report.md) | [v8_q1_bank_risk_comparison_evaluation.md](../../outputs/evaluations/v8_q1_bank_risk_comparison_evaluation.md) |
| q2_deutsche_liquidity_framework | single_bank_liquidity | 3.7/5 | Evidence relevance could be improved. | [v8_q2_deutsche_liquidity_framework_report.md](../../outputs/reports/v8_q2_deutsche_liquidity_framework_report.md) | [v8_q2_deutsche_liquidity_framework_evaluation.md](../../outputs/evaluations/v8_q2_deutsche_liquidity_framework_evaluation.md) |

## 4. Observed Strengths

- The benchmark runner exercises the full Agentic RAG pipeline across multiple question categories.
- Successful runs preserve report and evaluation artifacts for inspection.
- The V5 evaluator provides consistent metric scores for comparing question-level behavior.
- Missing or weak evidence can be surfaced through repair summaries and evaluation weaknesses.

## 5. Observed Weaknesses

- Some tasks may still have weak or missing evidence after retrieval repair.
- Retrieval repair may not always find stronger evidence if the vector database lacks relevant chunks.
- Report risk comparison sections may remain generic for some question shapes.
- The current deterministic evaluator is useful for consistency but not a substitute for expert review.

## 6. Recommendations for Next Iteration

- Improve question-specific query planning for single-bank and single-risk questions.
- Add more domain-specific fallback queries for liquidity, capital, and regulatory evidence.
- Add stricter benchmark scoring once more labeled expectations are available.
- Expand the benchmark dataset with more banks, more reports, and more regulation-focused questions.

## 7. Benchmark Limitations

- The benchmark dataset is intentionally small.
- Evaluation is deterministic and heuristic.
- This is not a human expert review.
- The benchmark does not verify financial truth outside retrieved sources.
- The benchmark output is not investment advice.
