# V6 Retrieval Repair Agent

## What V6 Adds

V6 adds a deterministic Retrieval Repair Agent that runs after evidence grading and before final answer generation. It detects planner tasks with weak or missing kept evidence, retries retrieval with controlled fallback queries, re-grades repaired chunks, and merges any kept repaired evidence into the final context.

## Why V6 Was Needed

The V5 evaluation exposed a clear coverage gap:

- Commerzbank / liquidity risk had 0 kept evidence

This meant the planner created the right task and retrieval returned chunks, but the Evidence Grader removed weak evidence and the system answered with a missing-evidence caveat. V6 attempts a targeted repair before final answer generation.

## Repair Strategy

For weak tasks, V6 generates fallback queries from the entity and risk type. Example Commerzbank liquidity risk repair queries:

1. Commerzbank liquidity risk management
2. Commerzbank funding risk
3. Commerzbank liquidity coverage ratio
4. Commerzbank LCR NSFR

The repair pass is intentionally bounded:

- maximum repair queries per weak task: 4
- chunks per repair query: 3
- final kept repaired chunks per task: 2

## Command Used

```bash
python3 scripts/ask.py --planner --grade-evidence --repair-retrieval --critic --report --evaluate
```

## Expected Output

The terminal should show:

- retrieval mode
- generated retrieval plan
- chunks retrieved
- evidence grading summary
- retrieval repair summary
- answer critic summary
- final answer
- report path
- evaluation summary

Example repair summary:

```text
Retrieval repair summary:
- Commerzbank / liquidity risk: improved
  - repair queries:
    1. Commerzbank liquidity risk management
    2. Commerzbank funding risk
    3. Commerzbank liquidity coverage ratio
    4. Commerzbank LCR NSFR
  - additional chunks retrieved: 8
  - additional chunks kept: 1
  - best repaired score: 0.62
```

## Limitations

- V6 does not retrieve everything blindly.
- V6 only repairs weak planner tasks.
- V6 is deterministic and does not use an LLM.
- V6 may still fail if the ingested vector database lacks relevant pages.
- V6 improves coverage attempts, not the underlying source documents.
