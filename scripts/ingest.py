#!/usr/bin/env python3
"""Ingest selected finance/risk PDF pages into local ChromaDB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_MAX_PAGES_PER_PDF,
    RAW_PDF_DIR,
    require_openai_api_key,
)
from src.pdf_loader import find_pdfs, get_pdf_page_count, iter_pdf_pages  # noqa: E402
from src.text_filter import is_useful_page  # noqa: E402
from src.vector_store import create_vector_store, reset_vector_db, vector_db_exists  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest finance PDFs into ChromaDB.")
    parser.add_argument(
        "--max-pages-per-pdf",
        type=int,
        default=DEFAULT_MAX_PAGES_PER_PDF,
        help=f"Maximum useful pages to embed per PDF. Default: {DEFAULT_MAX_PAGES_PER_PDF}",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reset an existing vector DB before ingesting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate selected pages and chunks without calling OpenAI embeddings.",
    )
    return parser.parse_args()


def confirm_reset() -> bool:
    answer = input(
        f"Vector DB already exists at {CHROMA_DIR}. Reset it and continue? [y/N]: "
    ).strip().lower()
    return answer in {"y", "yes"}


def build_documents(max_pages_per_pdf: int) -> tuple[list[Document], int, int]:
    pdf_paths = find_pdfs(RAW_PDF_DIR)
    if not pdf_paths:
        raise FileNotFoundError(f"No PDFs found in {RAW_PDF_DIR}")

    print(f"PDFs found: {len(pdf_paths)}")
    all_documents: list[Document] = []
    total_selected_pages = 0
    total_selected_chars = 0

    for pdf_path in pdf_paths:
        page_count = get_pdf_page_count(pdf_path)
        useful_pages = 0
        selected_page_docs: list[Document] = []

        print(f"\nProcessing: {pdf_path.name}")
        print(f"Total pages: {page_count}")

        for page in iter_pdf_pages(pdf_path, RAW_PDF_DIR):
            text = page["text"]
            if not is_useful_page(text):
                continue

            selected_page_docs.append(
                Document(page_content=text, metadata=page["metadata"])
            )
            useful_pages += 1
            total_selected_chars += len(text)

            if useful_pages >= max_pages_per_pdf:
                break

        print(f"Useful pages selected: {useful_pages}")
        all_documents.extend(selected_page_docs)
        total_selected_pages += useful_pages

    return all_documents, total_selected_pages, total_selected_chars


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(documents)


def main() -> int:
    args = parse_args()

    if args.max_pages_per_pdf <= 0:
        print("--max-pages-per-pdf must be greater than 0.")
        return 1

    if vector_db_exists(CHROMA_DIR):
        if args.force:
            print(f"--force set. Resetting existing vector DB at {CHROMA_DIR}")
            reset_vector_db(CHROMA_DIR)
        elif args.dry_run:
            print(f"Existing vector DB found at {CHROMA_DIR}; dry-run will not modify it.")
        elif confirm_reset():
            reset_vector_db(CHROMA_DIR)
        else:
            print("Exiting without changes.")
            return 0

    try:
        page_documents, total_pages, total_chars = build_documents(args.max_pages_per_pdf)
    except Exception as exc:
        print(f"Ingestion failed during PDF loading: {exc}")
        return 1

    if not page_documents:
        print("\nNo useful pages matched the configured finance/risk keywords.")
        return 0

    chunks = split_documents(page_documents)
    estimated_tokens = max(1, total_chars // 4)

    print("\nIngestion summary")
    print(f"Useful pages selected across PDFs: {total_pages}")
    print(f"Total chunks created: {len(chunks)}")
    print(f"Estimated character volume before embedding: {total_chars:,}")
    print(f"Approximate token volume before embedding: {estimated_tokens:,}")
    print(f"Vector DB location: {CHROMA_DIR}")

    if args.dry_run:
        print("\nDry-run complete. No embeddings were created.")
        return 0

    try:
        require_openai_api_key()
        create_vector_store(chunks, CHROMA_DIR)
    except Exception as exc:
        print(f"Embedding/vector store creation failed: {exc}")
        return 1

    print("\nIngestion complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

