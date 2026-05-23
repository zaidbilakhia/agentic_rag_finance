#!/usr/bin/env python3
"""Export an existing Markdown report to styled HTML and optional PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.report_exporter import export_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse report export CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Export an Agentic Finance RAG Markdown report to HTML and optional PDF."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the Markdown report to export.",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Export styled HTML. Default when neither --html nor --pdf is provided.",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also export PDF using WeasyPrint when available.",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="Optional output filename stem for exported files.",
    )
    parser.add_argument(
        "--html-output-dir",
        default="outputs/reports_html",
        help="Directory for HTML reports. Default: outputs/reports_html",
    )
    parser.add_argument(
        "--pdf-output-dir",
        default="outputs/reports_pdf",
        help="Directory for PDF reports. Default: outputs/reports_pdf",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    export_html = args.html or not args.pdf

    try:
        result = export_report(
            markdown_path=args.input,
            export_html=export_html,
            export_pdf=args.pdf,
            html_output_dir=args.html_output_dir,
            pdf_output_dir=args.pdf_output_dir,
            output_name=args.output_name,
        )
    except Exception as exc:
        print(f"Report export failed: {exc}")
        return 1

    if result.get("html_exported"):
        print("HTML report saved to:")
        print(result["html_path"])

    if args.pdf:
        if result.get("pdf_exported"):
            print("\nPDF report saved to:")
            print(result["pdf_path"])
        else:
            print("\nPDF export failed:")
            print(result.get("pdf_error") or "Unknown PDF export error.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
