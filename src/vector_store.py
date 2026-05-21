"""Chroma vector store helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from src.config import CHROMA_DIR, EMBEDDING_MODEL


def get_embedding_function() -> OpenAIEmbeddings:
    """Create the configured OpenAI embedding client."""
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def vector_db_exists(chroma_dir: Path = CHROMA_DIR) -> bool:
    """Check whether a persisted Chroma directory already exists."""
    return chroma_dir.exists() and any(chroma_dir.iterdir())


def create_vector_store(
    documents,
    chroma_dir: Path = CHROMA_DIR,
    collection_name: str = "finance_documents",
) -> Chroma:
    """Embed documents and persist them to local Chroma."""
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma.from_documents(
        documents=documents,
        embedding=get_embedding_function(),
        persist_directory=str(chroma_dir),
        collection_name=collection_name,
    )


def load_vector_store(
    chroma_dir: Path = CHROMA_DIR,
    collection_name: str = "finance_documents",
) -> Chroma:
    """Load an existing local Chroma vector store."""
    if not vector_db_exists(chroma_dir):
        raise FileNotFoundError(
            f"No vector database found at {chroma_dir}. Run ingestion first."
        )
    return Chroma(
        persist_directory=str(chroma_dir),
        embedding_function=get_embedding_function(),
        collection_name=collection_name,
    )


def list_source_files(vector_store: Chroma) -> list[str]:
    """Return unique source_file metadata values stored in Chroma."""
    try:
        result = vector_store.get(include=["metadatas"])
    except Exception:
        return []

    source_files = {
        metadata.get("source_file")
        for metadata in result.get("metadatas", [])
        if metadata and metadata.get("source_file")
    }
    return sorted(source_files)


def similarity_search_by_source_file(
    vector_store: Chroma,
    query: str,
    source_files: list[str],
    k: int,
) -> list[Document]:
    """Retrieve similar chunks restricted to one or more exact source_file values.

    Chroma supports exact metadata filters reliably. If a local Chroma version
    does not support the `$in` operator, fall back to one exact filter per file.
    """
    if not source_files or k <= 0:
        return []

    if len(source_files) == 1:
        return vector_store.similarity_search(
            query,
            k=k,
            filter={"source_file": source_files[0]},
        )

    try:
        return vector_store.similarity_search(
            query,
            k=k,
            filter={"source_file": {"$in": source_files}},
        )
    except Exception:
        documents: list[Document] = []
        per_file_k = max(1, k)
        for source_file in source_files:
            documents.extend(
                vector_store.similarity_search(
                    query,
                    k=per_file_k,
                    filter={"source_file": source_file},
                )
            )
        return documents[:k]


def reset_vector_db(chroma_dir: Path = CHROMA_DIR) -> None:
    """Delete the local Chroma vector database directory."""
    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
