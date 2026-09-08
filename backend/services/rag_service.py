"""RAG orchestration.

This module owns the whole ``document -> vector DB -> retrieval -> LLM ->
answer`` pipeline. API routes call these functions; they never contain RAG
logic themselves.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.rag.chunker import Chunk, create_chunks as _create_chunks
from backend.rag.loader import load_document
from backend.rag.prompts import (
    NO_ANSWER_RESPONSE,
    build_query_rewrite_prompt,
    build_system_prompt,
    build_user_prompt,
)
from backend.rag.retriever import retrieve_context as _retrieve_context
from backend.rag.vector_store import RetrievedChunk, get_vector_store
from backend.services.embedding_service import embed_chunks
from backend.services.llm_service import LLMError, get_llm_service

logger = get_logger(__name__)

History = Sequence[Tuple[str, str]]


@dataclass
class IngestResult:
    """Outcome of indexing one document."""

    document_name: str
    chunk_count: int
    pages: int


@dataclass
class AnswerResult:
    """Outcome of answering one question."""

    answer: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    answered: bool = True
    latency_ms: int = 0
    chunks: List[RetrievedChunk] = field(default_factory=list)
    mode: str = "extractive"


# ----------------------------------------------------------------------
# Ingestion
# ----------------------------------------------------------------------
def create_chunks(text: str, document_name: str = "inline", document_id: int | None = None) -> List[Chunk]:
    """Chunk a raw string (single-page document)."""
    return _create_chunks([(1, text)], document_name=document_name, document_id=document_id)


def create_embeddings(chunks: Sequence[Chunk]) -> List[List[float]]:
    """Embed a list of chunks."""
    return embed_chunks(chunks)


def store_embeddings(chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> List[str]:
    """Persist chunks + embeddings in the vector store; returns the chunk ids."""
    ids = [str(uuid.uuid4()) for _ in chunks]
    get_vector_store().add(ids=ids, chunks=list(chunks), embeddings=list(embeddings))
    return ids


def ingest_document(
    file_path: str | Path,
    document_id: int | None = None,
    document_name: str | None = None,
) -> IngestResult:
    """Full ingestion pipeline: load -> clean -> chunk -> embed -> store."""
    path = Path(file_path)
    name = document_name or path.name

    pages = load_document(path)
    chunks = _create_chunks(pages, document_name=name, document_id=document_id)
    if not chunks:
        raise ValueError(f"No chunks produced for {name}")

    embeddings = create_embeddings(chunks)
    store_embeddings(chunks, embeddings)

    logger.info("Indexed %s: %s page(s), %s chunk(s)", name, len(pages), len(chunks))
    return IngestResult(document_name=name, chunk_count=len(chunks), pages=len(pages))


def delete_document_vectors(document_id: int) -> int:
    """Remove every vector belonging to a document."""
    removed = get_vector_store().delete_document(document_id)
    logger.info("Removed %s vector(s) for document_id=%s", removed, document_id)
    return removed


# ----------------------------------------------------------------------
# Retrieval + generation
# ----------------------------------------------------------------------
def retrieve_context(question: str, top_k: int | None = None) -> List[RetrievedChunk]:
    """Retrieve the most relevant HR chunks for a question."""
    return _retrieve_context(question, top_k=top_k)


def build_sources(chunks: Sequence[RetrievedChunk]) -> List[Dict[str, Any]]:
    """Deduplicated citation list built from retrieved chunks."""
    sources: List[Dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for chunk in chunks:
        key = (chunk.document_name, chunk.page_number)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "document": chunk.document_name,
                "page": chunk.page_number,
                "section": chunk.section,
                "score": round(float(chunk.score), 4),
            }
        )
    return sources


def rewrite_followup(question: str, history: History) -> str:
    """Resolve pronouns in a follow-up question so retrieval stays on topic."""
    if not history:
        return question

    llm = get_llm_service()
    if llm.enabled:
        try:
            rewritten = llm.complete(
                [
                    {"role": "system", "content": "You rewrite HR questions into standalone search queries."},
                    {"role": "user", "content": build_query_rewrite_prompt(question, history)},
                ],
                max_tokens=80,
            )
            if rewritten and len(rewritten) < 300:
                return rewritten.strip().strip('"')
        except LLMError as exc:
            logger.warning("Follow-up rewrite failed (%s); using raw question", exc)

    # Offline heuristic: prepend the last employee question for extra context.
    previous_questions = [content for role, content in history if role == "user"]
    if previous_questions:
        return f"{previous_questions[-1]} {question}"
    return question


def generate_answer(
    question: str,
    context: Sequence[RetrievedChunk],
    history: History | None = None,
) -> tuple[str, str]:
    """Generate an answer from context. Returns ``(answer, mode)``."""
    if not context:
        return NO_ANSWER_RESPONSE, "no-context"

    llm = get_llm_service()
    if llm.enabled:
        try:
            answer = llm.complete(
                [
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": build_user_prompt(question, context, history)},
                ]
            )
            return (answer or NO_ANSWER_RESPONSE), "llm"
        except LLMError as exc:
            logger.error("LLM generation failed (%s); falling back to extractive answer", exc)

    return llm.extractive_answer(question, context), "extractive"


def is_unanswered(answer: str) -> bool:
    """True when the assistant reported that it could not find the information."""
    normalised = answer.strip().lower()
    return normalised.startswith("i could not find this information") or not normalised


def answer_question(
    question: str,
    history: History | None = None,
    top_k: int | None = None,
) -> AnswerResult:
    """Answer an HR question end to end."""
    started = time.perf_counter()
    question = (question or "").strip()
    if not question:
        raise ValueError("Question must not be empty")

    search_query = rewrite_followup(question, history or [])
    chunks = retrieve_context(search_query, top_k=top_k or settings.TOP_K)
    answer, mode = generate_answer(question, chunks, history)

    answered = bool(chunks) and not is_unanswered(answer)
    latency_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "Answered question in %sms (mode=%s, chunks=%s, answered=%s)",
        latency_ms,
        mode,
        len(chunks),
        answered,
    )

    return AnswerResult(
        answer=answer,
        sources=build_sources(chunks) if answered else [],
        answered=answered,
        latency_ms=latency_ms,
        chunks=list(chunks),
        mode=mode,
    )


def index_stats() -> Dict[str, Any]:
    """Diagnostics about the vector index."""
    store = get_vector_store()
    return {"backend": store.backend, "chunks": store.count()}
