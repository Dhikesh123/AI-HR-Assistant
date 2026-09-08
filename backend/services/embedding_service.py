"""Embedding service - a thin façade over the configured embedding backend."""
from __future__ import annotations

from typing import List, Sequence

from backend.core.logging_config import get_logger
from backend.rag.chunker import Chunk
from backend.rag.embeddings import EmbeddingError, get_embedder

logger = get_logger(__name__)


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    """Embed arbitrary texts."""
    if not texts:
        return []
    return get_embedder().embed_documents(list(texts))


def embed_chunks(chunks: Sequence[Chunk]) -> List[List[float]]:
    """Embed chunk texts, preserving order."""
    return embed_texts([chunk.text for chunk in chunks])


def embed_query(question: str) -> List[float]:
    """Embed a single query string."""
    return get_embedder().embed_query(question)


def provider_name() -> str:
    """Name of the active embedding backend, for diagnostics."""
    return get_embedder().name


__all__ = [
    "EmbeddingError",
    "embed_chunks",
    "embed_query",
    "embed_texts",
    "provider_name",
]
