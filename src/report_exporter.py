"""Export generated Markdown reports to styled HTML and optional PDF."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

import markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_project_path(path: str | Path) -> Path:
    """Resolve relative paths from the project root."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def relative_path(path: Path) -> str:
    """Return a project-relative path when possible."""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sanitize_filename(name: str) -> str:
    """Create a safe filename stem while preserving useful words."""
    stem = Path(name).stem
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "agentic_finance_report"


def load_markdown_report(markdown_path: str) -> str:
    """Read a Markdown report from disk."""
    path = resolve_project_path(markdown_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown report not found: {path}")
    return path.read_text(encoding="utf-8")


def ensure_blank_line_before_list(text: str) -> str:
    """Ensure Markdown lists render as lists during export."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and cleaned:
            previous = cleaned[-1].strip()
            if previous and not previous.startswith(("- ", "|", "#")):
                cleaned.append("")
        cleaned.append(line.rstrip())
    return "\n".join(cleaned)


def polish_markdown_for_export(markdown_text: str) -> str:
    """Apply deterministic spacing cleanup before Markdown-to-HTML conversion."""
    text = markdown_text.replace("\r\n", "\n")
    text = re.sub(r"(:)\s+(-\s+)", r"\1\n\n\2", text)
    text = re.sub(r"(\*\*[^*\n]+:\*\*)\s+(-\s+)", r"\1\n\n\2", text)
    text = re.sub(r"\s+(-\s+[A-Z][^-:\n]+(?:\.|;))", r"\n\1", text)
    text = ensure_blank_line_before_list(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_html(markdown_text: str, title: str = "Agentic Finance RAG Report") -> str:
    """Convert Markdown report text to a complete styled HTML document."""
    body = markdown.markdown(
        polish_markdown_for_export(markdown_text),
        extensions=["tables", "fenced_code", "toc"],
        output_format="html5",
    )
    escaped_title = escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      background: #f6f8fb;
      color: #1f2937;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 16px;
      line-height: 1.55;
    }}
    .report-container {{
      max-width: 950px;
      margin: 32px auto;
      background: #ffffff;
      padding: 44px;
      border-radius: 12px;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
    }}
    h1, h2, h3, h4 {{
      line-height: 1.25;
    }}
    h1 {{
      margin-top: 0;
      padding-bottom: 12px;
      border-bottom: 3px solid #1f4e79;
      font-size: 28px;
      color: #111827;
    }}
    h2 {{
      margin-top: 34px;
      padding-bottom: 8px;
      border-bottom: 1px solid #d9e2ec;
      font-size: 22px;
      color: #1f4e79;
      page-break-after: avoid;
    }}
    h3 {{
      margin-top: 24px;
      font-size: 18px;
      color: #334155;
      page-break-after: avoid;
    }}
    p {{
      margin: 10px 0 14px;
    }}
    ul, ol {{
      margin: 8px 0 16px 24px;
      padding-left: 16px;
    }}
    li {{
      margin-bottom: 6px;
    }}
    a {{
      color: #1f4e79;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 18px 0 28px;
      font-size: 13px;
      page-break-inside: avoid;
    }}
    th, td {{
      border: 1px solid #d8dee9;
      padding: 10px 12px;
      vertical-align: top;
    }}
    th {{
      background: #eef3f8;
      color: #111827;
      font-weight: 700;
      text-align: left;
    }}
    tr:nth-child(even) {{
      background: #fbfdff;
    }}
    tr {{
      page-break-inside: avoid;
      page-break-after: auto;
    }}
    blockquote {{
      margin: 1rem 0;
      padding: 0.75rem 1rem;
      border-left: 4px solid #1f4e79;
      background: #eef4ff;
      color: #26364f;
    }}
    pre, code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 0.92em;
    }}
    pre {{
      overflow-x: auto;
      padding: 1rem;
      background: #111827;
      color: #f9fafb;
      border-radius: 6px;
    }}
    code {{
      background: #f3f4f6;
      padding: 2px 5px;
      border-radius: 4px;
    }}
    pre code {{
      background: transparent;
      padding: 0;
    }}
    h2[id*="executive-summary"] + p {{
      padding: 16px 18px;
      border-left: 4px solid #1f4e79;
      background: #eef4ff;
      border-radius: 8px;
    }}
    .footer {{
      margin-top: 40px;
      padding-top: 12px;
      border-top: 1px solid #e5e7eb;
      color: #64748b;
      font-size: 12px;
      text-align: center;
    }}
    @page {{
      margin: 22mm 18mm;
    }}
    @media print {{
      body {{
        background: #ffffff;
      }}
      .report-container {{
        margin: 0;
        padding: 24px;
        max-width: none;
        border: 0;
        border-radius: 0;
        box-shadow: none;
      }}
      h2 {{
        page-break-after: avoid;
      }}
      table {{
        page-break-inside: avoid;
      }}
      a {{
        color: inherit;
        text-decoration: none;
      }}
    }}
    @media (max-width: 720px) {{
      .report-container {{
        margin: 0;
        padding: 28px 20px;
        border-radius: 0;
        box-shadow: none;
      }}
      table {{
        display: block;
        overflow-x: auto;
      }}
    }}
  </style>
</head>
<body>
  <main class="report-container">
{body}
    <footer class="footer">Generated by Agentic Finance RAG</footer>
  </main>
</body>
</html>
"""


def export_report_html(
    markdown_path: str,
    output_dir: str = "outputs/reports_html",
    output_name: str | None = None,
) -> dict:
    """Export a Markdown report to styled HTML."""
    markdown_file = resolve_project_path(markdown_path)
    markdown_text = load_markdown_report(str(markdown_file))
    output_stem = sanitize_filename(output_name or markdown_file.stem)
    output_directory = resolve_project_path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    html_path = output_directory / f"{output_stem}.html"
    title = output_stem.replace("_", " ").replace("-", " ").title()
    html_path.write_text(markdown_to_html(markdown_text, title=title), encoding="utf-8")
    return {
        "markdown_path": relative_path(markdown_file),
        "html_path": relative_path(html_path),
        "html_exported": True,
    }


def export_report_pdf(
    html_path: str,
    output_dir: str = "outputs/reports_pdf",
    output_name: str | None = None,
) -> dict:
    """Export an HTML report to PDF with graceful WeasyPrint fallback."""
    html_file = resolve_project_path(html_path)
    output_stem = sanitize_filename(output_name or html_file.stem)
    output_directory = resolve_project_path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    pdf_path = output_directory / f"{output_stem}.pdf"

    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return {
            "html_path": relative_path(html_file),
            "pdf_path": None,
            "pdf_exported": False,
            "pdf_error": "WeasyPrint is not installed. Install it with: pip install weasyprint",
        }

    try:
        HTML(filename=str(html_file)).write_pdf(str(pdf_path))
    except Exception as exc:
        return {
            "html_path": relative_path(html_file),
            "pdf_path": None,
            "pdf_exported": False,
            "pdf_error": f"WeasyPrint PDF export failed: {exc}",
        }

    return {
        "html_path": relative_path(html_file),
        "pdf_path": relative_path(pdf_path),
        "pdf_exported": True,
        "pdf_error": None,
    }


def export_report(
    markdown_path: str,
    export_html: bool = True,
    export_pdf: bool = False,
    html_output_dir: str = "outputs/reports_html",
    pdf_output_dir: str = "outputs/reports_pdf",
    output_name: str | None = None,
) -> dict:
    """Export a Markdown report to HTML and optionally PDF."""
    result: dict[str, Any] = {
        "markdown_path": relative_path(resolve_project_path(markdown_path)),
        "html_path": None,
        "pdf_path": None,
        "html_exported": False,
        "pdf_exported": False,
        "pdf_error": None,
    }

    if not export_html and export_pdf:
        export_html = True

    if export_html:
        html_result = export_report_html(
            markdown_path=markdown_path,
            output_dir=html_output_dir,
            output_name=output_name,
        )
        result.update(html_result)

    if export_pdf:
        if not result.get("html_path"):
            result["pdf_error"] = "PDF export requires an HTML report, but HTML export was disabled."
        else:
            pdf_result = export_report_pdf(
                html_path=result["html_path"],
                output_dir=pdf_output_dir,
                output_name=output_name,
            )
            result.update(pdf_result)

    return result
