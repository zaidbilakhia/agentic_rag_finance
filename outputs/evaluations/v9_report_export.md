# V9 HTML/PDF Report Export

## What V9 Adds

V9 adds a professional export layer for existing Agentic Finance RAG Markdown reports.

The new report flow is:

```text
Agentic RAG pipeline
-> Markdown report
-> styled HTML export
-> optional PDF export
```

V9 does not change retrieval, evidence grading, retrieval repair, answer criticism, benchmarking, or evaluation logic.

## Why This Follows V8.3

V8.3 made benchmark quality easier to inspect through deterministic error analysis. V9 focuses on portfolio and demo polish by making generated reports easier to share with reviewers, stakeholders, and future users.

## Commands

Export an existing Markdown report to HTML:

```bash
python3 scripts/export_report.py --input outputs/reports/risk_report_20260522_233821.md --html
```

Export HTML and PDF:

```bash
python3 scripts/export_report.py --input outputs/reports/risk_report_20260522_233821.md --html --pdf
```

Run the full pipeline with export:

```bash
python3 scripts/ask.py --planner --grade-evidence --repair-retrieval --critic --report --export-html --export-pdf --evaluate
```

## Expected Outputs

HTML reports are written under:

```text
outputs/reports_html/
```

PDF reports are written under:

```text
outputs/reports_pdf/
```

Pipeline result metadata now includes:

- `html_report_path`
- `pdf_report_path`
- `export_summary`

## Limitations

- HTML export depends on the Python `markdown` package.
- PDF export is optional and depends on WeasyPrint.
- WeasyPrint may require system-level dependencies depending on the environment.
- If PDF export fails, HTML export still succeeds and the PDF error is reported clearly.
- V9 exports generated report files only; it does not validate financial truth outside retrieved documents.

## PDF Dependency Note

Install WeasyPrint only when PDF export is needed:

```bash
pip install weasyprint
```

If WeasyPrint is not installed, PDF export returns a message such as:

```text
WeasyPrint is not installed. Install it with: pip install weasyprint
```
