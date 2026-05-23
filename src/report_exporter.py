"""Export generated Markdown reports to styled HTML and optional PDF."""

from __future__ import annotations

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


def markdown_to_html(markdown_text: str, title: str = "Agentic Finance RAG Report") -> str:
    """Convert Markdown report text to a complete styled HTML document."""
    body = markdown.markdown(
        markdown_text,
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
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --page: #ffffff;
      --text: #1f2933;
      --muted: #5f6b7a;
      --line: #d8dee8;
      --accent: #2454a6;
      --accent-soft: #eef4ff;
      --table-head: #f0f3f8;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.62;
    }}
    .page {{
      max-width: 900px;
      margin: 32px auto;
      padding: 48px 56px;
      background: var(--page);
      border: 1px solid var(--line);
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
    }}
    h1, h2, h3, h4 {{
      color: #111827;
      line-height: 1.25;
      margin: 1.6em 0 0.55em;
    }}
    h1 {{
      margin-top: 0;
      padding-bottom: 0.5em;
      border-bottom: 2px solid var(--accent);
      font-size: 2rem;
    }}
    h2 {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 0.25em;
      font-size: 1.35rem;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 1.08rem;
      page-break-after: avoid;
    }}
    p, ul, ol, table, pre {{
      margin-top: 0;
      margin-bottom: 1rem;
    }}
    a {{
      color: var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.94rem;
      page-break-inside: auto;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 9px 11px;
      vertical-align: top;
    }}
    th {{
      background: var(--table-head);
      font-weight: 650;
      text-align: left;
    }}
    tr {{
      page-break-inside: avoid;
      page-break-after: auto;
    }}
    blockquote {{
      margin: 1rem 0;
      padding: 0.75rem 1rem;
      border-left: 4px solid var(--accent);
      background: var(--accent-soft);
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
      background: #eef1f5;
      padding: 0.1rem 0.25rem;
      border-radius: 4px;
    }}
    pre code {{
      background: transparent;
      padding: 0;
    }}
    h2:first-of-type + p,
    h2:first-of-type + ul {{
      padding: 1rem;
      border: 1px solid #cfe0ff;
      background: var(--accent-soft);
      border-radius: 6px;
    }}
    .footer {{
      margin-top: 3rem;
      padding-top: 1rem;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.88rem;
      text-align: center;
    }}
    @page {{
      margin: 22mm 18mm;
    }}
    @media print {{
      body {{
        background: #ffffff;
      }}
      .page {{
        margin: 0;
        padding: 0;
        max-width: none;
        border: 0;
        box-shadow: none;
      }}
      a {{
        color: inherit;
        text-decoration: none;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        margin: 0;
        padding: 28px 20px;
        border: 0;
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
  <main class="page">
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
