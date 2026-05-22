# V7 Streamlit Dashboard UI

## What V7 Adds

V7 adds a local Streamlit dashboard for running the existing Agentic Finance RAG pipeline from a browser.

The dashboard supports:

- entering a finance question
- enabling Query Planner, Evidence Grader, Retrieval Repair, Answer Critic, Report Generator, and Evaluation Agent options
- inspecting the final answer
- viewing the generated retrieval plan
- reviewing chunks retrieved per task
- inspecting evidence grading results
- reviewing retrieval repair status
- viewing answer critic feedback
- previewing and downloading generated Markdown reports
- previewing and downloading evaluation Markdown files

## Why UI Was Added After V6

V6 made the backend pipeline more complete by detecting weak or missing evidence and attempting targeted retrieval repair. After that, a browser UI became useful because the pipeline now has multiple intermediate artifacts that are easier to inspect in tabs than in terminal output.

## Dashboard Features

- Clean sidebar controls for pipeline options
- Advanced settings for evidence grading and retrieval repair
- Tabbed result inspection
- Graceful `OPENAI_API_KEY` warning
- Reuses `src.rag_chain.run_rag_pipeline` instead of duplicating backend logic

## Command Used

```bash
streamlit run apps/streamlit_app.py
```

## Screenshot

Not included yet. Run the app locally with:

```bash
streamlit run apps/streamlit_app.py
```

## Limitations

- The dashboard is local-only and has no authentication.
- The app does not manage document ingestion yet.
- Long-running RAG calls may take time depending on OpenAI API latency.
- The UI is intentionally simple and does not introduce a separate web backend.
