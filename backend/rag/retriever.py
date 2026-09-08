"""Retrieval: turn a question into the most relevant HR chunks."""
from __future__ import annotations

from typing import List

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.rag.embeddings import EmbeddingError, get_embedder
from backend.rag.text_utils import overlap_ratio
from backend.rag.vector_store import RetrievedChunk, VectorStoreError, get_vector_store

logger = get_logger(__name__)


# Re-ranking weights. Vector similarity carries the ranking; keyword overlap
# pulls up the chunk containing the exact policy term; the section title breaks
# ties in favour of the section actually about the question, so an authoritative
# policy section outranks a page that mentions the term only in passing.
VECTOR_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.25
SECTION_WEIGHT = 0.10


def _keyword_overlap(question: str, text: str) -> float:
    """Fraction of meaningful question words that appear in ``text``."""
    return overlap_ratio(question, text)


def _section_overlap(question: str, chunk: RetrievedChunk) -> float:
    """Fraction of question words matched by the chunk's section heading."""
    section = chunk.section
    if not section or section.lower() == "general":
        return 0.0
    return overlap_ratio(question, section)


def retrieve_context(
    question: str,
    top_k: int | None = None,
    min_score: float | None = None,
) -> List[RetrievedChunk]:
    """Embed the question and return the most relevant chunks.

    Results are re-ranked with a light keyword-overlap signal and filtered by a
    relevance floor, which is what lets the assistant answer "I don't know"
    instead of reasoning over irrelevant context.
    """
    question = (question or "").strip()
    if not question:
        return []

    top_k = top_k or settings.TOP_K
    min_score = settings.MIN_RELEVANCE_SCORE if min_score is None else min_score

    try:
        query_embedding = get_embedder().embed_query(question)
    except EmbeddingError as exc:
        logger.error("Query embedding failed: %s", exc)
        raise

    try:
        # Over-fetch, then re-rank and trim to top_k.
        candidates = get_vector_store().query(query_embedding, top_k=max(top_k * 3, top_k))
    except Exception as exc:
        logger.error("Vector search failed: %s", exc)
        raise VectorStoreError(str(exc)) from exc

    for chunk in candidates:
        chunk.score = round(
            VECTOR_WEIGHT * chunk.score
            + KEYWORD_WEIGHT * _keyword_overlap(question, chunk.text)
            + SECTION_WEIGHT * _section_overlap(question, chunk),
            6,
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    relevant = [c for c in candidates if c.score >= min_score][:top_k]

    logger.info(
        "Retrieved %s/%s chunk(s) above threshold %.2f for query",
        len(relevant),
        len(candidates),
        min_score,
    )
    return relevant
