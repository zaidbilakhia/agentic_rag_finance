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

Example questions:

1. Compare Deutsche Bank and Commerzbank based on operational risk, liquidity risk, and regulatory risk.
2. What are the key regulatory risks mentioned in the documents?
3. Which risk areas should a financial services consultant investigate further?

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

- Add Query Planner Agent
- Add Reasoning Agent
- Add Risk Agent
- Add Advisor Agent
- Add Streamlit dashboard
