# V9.1 PDF / Report Polish

## What V9.1 Fixes

V9.1 improves the readability of generated Markdown, HTML, and PDF reports without changing the RAG pipeline logic.

It focuses on:

- Cleaner Markdown bullet and list formatting.
- Better handling of bold labels followed by lists.
- Cleaner limitations and answer critic sections.
- More readable consulting-style HTML/PDF styling.
- Better table padding, spacing, and page-break behavior.
- A deterministic Risk Comparison section with real comparison paragraphs.

## Observed V9 Issues

- Some bullet points rendered inline in PDF output.
- Consultant Recommendation and Limitations sections could look cramped.
- Tables were readable but needed more spacing.
- The Risk Comparison section sometimes used generic placeholder text.
- PDF output worked, but did not yet look polished enough for a consulting report.

## Formatting Improvements

The report generator now normalizes Markdown spacing before writing reports. It inserts blank lines before lists, formats recurring bullet lists consistently, and uses evidence and repair metadata to create short comparison paragraphs for operational, liquidity, and regulatory risk.

The HTML exporter now uses a more polished embedded stylesheet with:

- A wider report container.
- Cleaner heading hierarchy.
- Improved list margins.
- More table padding.
- Alternating table rows.
- Better print/PDF page-break behavior.
- A subtle Executive Summary callout style.

## Commands Used

Compile all Python files:

```bash
python3 -m py_compile src/*.py scripts/*.py apps/*.py
```

Check the export CLI:

```bash
python3 scripts/export_report.py --help
```

Export an existing Markdown report:

```bash
python3 scripts/export_report.py \
  --input outputs/reports/risk_report_20260522_233821.md \
  --html
```

Export HTML and PDF when WeasyPrint is available:

```bash
python3 scripts/export_report.py \
  --input outputs/reports/risk_report_20260522_233821.md \
  --html \
  --pdf
```

## Limitations

- V9.1 improves formatting and deterministic report sections only.
- It does not change retrieval, planning, grading, repair, criticism, benchmarking, or evaluation scoring.
- Existing Markdown reports must be regenerated to receive the improved Risk Comparison section.
- PDF quality still depends on WeasyPrint and its local system dependencies.
- The report remains an evidence-based RAG output, not a human finance expert review.
