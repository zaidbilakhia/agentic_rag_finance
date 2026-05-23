# V8.1 Planner Generalization Improvement

## Why V8.1 Was Needed

The V8 benchmark showed that the planner worked well for the original two-bank comparison question, but it was too narrow for single-bank and single-risk questions.

The clearest weakness was:

- `q2_deutsche_liquidity_framework`: 3.2/5

For that question, the previous planner created only one broad task:

- `Deutsche Bank liquidity risk`

That was not enough retrieval coverage for a question asking about liquidity risk management framework and risk flags.

## Planner Cases Improved

V8.1 keeps the original two-bank comparison behavior intact and adds deterministic task expansion for:

- single-bank liquidity risk questions
- single-bank operational risk questions
- single-bank regulatory risk questions
- single-risk comparison questions
- missing or weak evidence questions
- EBA-only regulatory context questions

## Example Improvement

Question:

```text
Summarize Deutsche Bank's liquidity risk management framework and identify key risk flags.
```

The planner now generates focused retrieval tasks such as:

- `Deutsche Bank liquidity risk management framework`
- `Deutsche Bank short-term liquidity risk`
- `Deutsche Bank structural funding risk`
- `Deutsche Bank liquidity stress testing`
- `Deutsche Bank LCR NSFR funding ratios`
- `Deutsche Bank liquidity risk flags`

## Expected Impact

- Better retrieval coverage for benchmark questions beyond the original comparison prompt.
- Stronger evidence for single-bank liquidity, operational, and regulatory questions.
- More useful retrieval repair because weak tasks are now more specific.
- Improved benchmark behavior for `q2_deutsche_liquidity_framework` and similar questions.

## Limitations

- The planner remains deterministic and rule-based.
- It does not infer every possible finance concept yet.
- The evaluation framework may still need additional question-type-aware scoring for non-comparison questions.
- This change improves retrieval planning, not the underlying vector database content.
