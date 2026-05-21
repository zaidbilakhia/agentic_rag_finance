# V2 Evidence Grader Agent Evaluation

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

## Chunks Retrieved Per Task

Not generated in this environment because `OPENAI_API_KEY` was not set. Chroma similarity search requires OpenAI query embeddings.

## Evidence Grading Summary

Not generated in this environment because retrieval could not run without `OPENAI_API_KEY`.

## Final Answer

Not generated in this environment because `OPENAI_API_KEY` was not set.

Attempted command:

```bash
printf '%s\nexit\n' 'Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk. Which bank appears riskier and what should a consultant recommend?' | python3 scripts/ask.py --planner --grade-evidence
```

Observed result:

```text
Startup failed: OPENAI_API_KEY is not set. Export it before running this command:
export OPENAI_API_KEY='your-api-key'
```

After exporting `OPENAI_API_KEY`, rerun:

```bash
python3 scripts/ask.py --planner --grade-evidence
```

Then ask the evaluation question and paste the full CLI output into this file.

## Comparison Against V0 and V1

V0 is a simple risk-aware RAG baseline. It can answer questions using retrieved chunks, but retrieval and evidence quality checks are mostly direct and rule-driven.

V1 adds a Query Planner Agent. It decomposes a comparison question into explicit retrieval tasks, improving transparency and balanced coverage across banks and risk types.

V2 adds an Evidence Grader Agent after retrieval. It scores each retrieved chunk against its planner task, filters low-relevance chunks, and passes only kept evidence to the final answer generator.

## Limitations of V2

- The evidence grader is deterministic and heuristic-based, not LLM-based.
- It checks keyword, entity, risk-type, and concrete evidence signals, but it does not deeply reason over financial meaning.
- It may under-score useful chunks that use unusual wording.
- It may over-score chunks that contain many relevant terms but limited analytical substance.
- The full evaluation answer could not be generated in this environment without `OPENAI_API_KEY`.
