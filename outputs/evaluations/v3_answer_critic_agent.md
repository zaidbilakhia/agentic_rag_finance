# V3 Answer Critic Agent Evaluation

## Evaluation Question

Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?

## Generated Retrieval Plan

Expected planner output:

1. Deutsche Bank | operational risk | Deutsche Bank operational risk
2. Deutsche Bank | liquidity risk | Deutsche Bank liquidity risk
3. Deutsche Bank | regulatory risk | Deutsche Bank regulatory risk
4. Commerzbank | operational risk | Commerzbank operational risk
5. Commerzbank | liquidity risk | Commerzbank liquidity risk
6. Commerzbank | regulatory risk | Commerzbank regulatory risk
7. EBA | regulatory context | EBA regulatory context banking supervision

## Chunks Retrieved Per Task

Not generated in this environment because `OPENAI_API_KEY` was not set.

## Evidence Grading Summary

Not generated in this environment because retrieval could not run without `OPENAI_API_KEY`.

## Draft Answer

Not generated in this environment because `OPENAI_API_KEY` was not set.

## Answer Critic Summary

Not generated in this environment because the draft answer could not be created without `OPENAI_API_KEY`.

## Improved Final Answer

Not generated in this environment because `OPENAI_API_KEY` was not set.

Attempted command:

```bash
printf '%s\nexit\n' 'Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?' | python3 scripts/ask.py --planner --grade-evidence --critic
```

Expected behavior after exporting `OPENAI_API_KEY`:

- Generate the V1 retrieval plan.
- Retrieve Chroma chunks per planner task.
- Grade evidence using V2.
- Generate a draft consulting-style answer.
- Run the V3 answer critic without retrieving new documents.
- Print the critic summary and improved final answer.

## Comparison Against V0, V1, and V2

V0 is a simple risk-aware RAG baseline that retrieves and answers directly.

V1 adds a Query Planner Agent, making retrieval structured and inspectable.

V2 adds an Evidence Grader Agent, filtering weak chunks before answer generation.

V3 adds an Answer Critic Agent, reviewing the draft answer against retrieved evidence and rewriting it more carefully when it overclaims, misses uncertainty, or needs a stronger consulting-style recommendation.

## Limitations of V3

- The critic uses an LLM call, so it depends on `OPENAI_API_KEY`.
- The critic does not retrieve new documents and cannot fix missing evidence.
- The critic can improve answer caution and structure, but it is not a substitute for quantitative risk analysis.
- The full evaluation could not be generated in this environment without `OPENAI_API_KEY`.
