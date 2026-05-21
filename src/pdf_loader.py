"""PDF discovery and page-wise extraction utilities."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.config import RAW_PDF_DIR
from src.text_filter import clean_text


def find_pdfs(raw_pdf_dir: Path = RAW_PDF_DIR) -> list[Path]:
    """Recursively find PDF files below the raw PDF directory."""
    if not raw_pdf_dir.exists():
        return []
    return sorted(raw_pdf_dir.rglob("*.pdf"))


def document_category_for(pdf_path: Path, raw_pdf_dir: Path = RAW_PDF_DIR) -> str:
    """Infer a broad category from the first folder below data/raw_pdfs."""
    try:
        relative = pdf_path.relative_to(raw_pdf_dir)
    except ValueError:
        return "unknown"
    return relative.parts[0] if len(relative.parts) > 1 else "uncategorized"


def get_pdf_page_count(pdf_path: Path) -> int:
    """Return the number of pages in a PDF."""
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def iter_pdf_pages(pdf_path: Path, raw_pdf_dir: Path = RAW_PDF_DIR) -> Iterator[dict[str, Any]]:
    """Yield page text and metadata one page at a time."""
    reader = PdfReader(str(pdf_path))
    category = document_category_for(pdf_path, raw_pdf_dir)

    for page_index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            print(f"Warning: failed to extract {pdf_path.name} page {page_index}: {exc}")
            text = ""

        yield {
            "text": clean_text(text),
            "metadata": {
                "source_file": pdf_path.name,
                "source_path": str(pdf_path),
                "page_number": page_index,
                "document_category": category,
            },
        }

