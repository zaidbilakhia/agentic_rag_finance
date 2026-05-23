# V8.2 Question-Type-Aware Evaluation

## Why V8.2 Was Needed

V8 and V8.1 expanded the benchmark and improved query planning, but the evaluator still treated every question as if it were the original two-bank comparison prompt.

That made single-bank questions score lower than they should because metrics such as comparative reasoning were weighted the same as evidence grounding and source relevance.

## q2 Issue

Question:

```text
Summarize Deutsche Bank's liquidity risk management framework and identify key risk flags.
```

This is a single-bank liquidity question. Before V8.2, the raw comparative reasoning score could strongly reduce the overall score even though a direct Deutsche Bank liquidity answer does not need to compare both banks.

Recent scores:

- before V8.1: 3.2/5
- after V8.1: 3.4/5

## What Changed

The Evaluation Agent now:

- detects or receives the benchmark question category
- supports category aliases from `data/evaluation_questions.json`
- keeps raw metric scores visible
- applies category-aware metric weights to calculate the overall score
- excludes comparative reasoning for single-bank liquidity, operational, and regulatory questions
- records `category_used`, `raw_scores`, `metric_weights`, and `weighted_overall_score`
- saves metric weights in Markdown evaluation reports

## Expected Impact

- Single-bank questions should no longer be unfairly penalized for lacking two-bank comparison.
- q2 should improve because comparative reasoning is excluded from its weighted overall score.
- Bank comparison questions still emphasize comparative reasoning, risk-specific reasoning, evidence grounding, and overclaiming control.
- Benchmark averages should become more meaningful across mixed question types.

## Limitations

- Raw metric scores can still reveal weak dimensions even when downweighted.
- The evaluator remains deterministic and heuristic.
- Category-aware weighting improves fairness but does not prove financial correctness.
- Further work may add category-specific raw scoring, especially for retrieval completeness.
