# V1 Query Planner Agent Evaluation

## Evaluation Question

Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?

## Generated Retrieval Plan

1. Deutsche Bank | operational risk | Deutsche Bank operational risk
2. Deutsche Bank | liquidity risk | Deutsche Bank liquidity risk
3. Deutsche Bank | regulatory risk | Deutsche Bank regulatory risk
4. Commerzbank | operational risk | Commerzbank operational risk
5. Commerzbank | liquidity risk | Commerzbank liquidity risk
6. Commerzbank | regulatory risk | Commerzbank regulatory risk
7. EBA | regulatory context | EBA regulatory context banking supervision

## Final Answer

Not generated in this environment because `OPENAI_API_KEY` was not set.

Attempted command:

```bash
printf '%s\nexit\n' 'Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?' | python3 scripts/ask.py --planner
```

Observed result:

```text
Startup failed: OPENAI_API_KEY is not set. Export it before running this command:
export OPENAI_API_KEY='your-api-key'
```

After exporting `OPENAI_API_KEY`, rerun the command above to generate and paste the final retrieved answer into this section.

## Short Comparison Against V0

V0 uses rule-based retrieval directly inside the RAG pipeline. It can retrieve balanced bank and risk-type evidence, but the retrieval plan is implicit in the code.

V1 adds an explicit query planning step before retrieval. The planner turns the user question into structured retrieval tasks, making the retrieval process easier to inspect, evaluate, and later replace with an LLM-based planner.

## Limitations of V1

- The planner is deterministic and rule-based, not yet LLM-driven.
- It currently focuses on the Deutsche Bank vs Commerzbank comparison pattern.
- It supports the core V1 risk dimensions: operational risk, liquidity risk, and regulatory risk.
- The evaluation answer could not be generated in this environment without `OPENAI_API_KEY`.
