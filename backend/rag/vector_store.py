"""Vector store abstraction.

ChromaDB is used when it is installed; otherwise an equivalent JSON-backed
local store with the same interface takes over so the RAG pipeline keeps
working. Both stores persist under ``CHROMA_DIR``.
"""
from __future__ import annotations

import json
import math
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.rag.chunker import Chunk

logger = get_logger(__name__)


class VectorStoreError(RuntimeError):
    """Raised when the vector database is unavailable or a query fails."""


@dataclass
class RetrievedChunk:
    """A chunk returned from a similarity search."""

    text: str
    metadata: Dict[str, Any]
    score: float

    @property
    def document_name(self) -> str:
        return str(self.metadata.get("document_name", "unknown"))

    @property
    def page_number(self) -> int | None:
        page = self.metadata.get("page_number")
        return int(page) if page is not None else None

    @property
    def section(self) -> str | None:
        section = self.metadata.get("section")
        return str(section) if section else None


class BaseVectorStore(ABC):
    """Interface implemented by every vector store backend."""

    backend: str = "base"

    @abstractmethod
    def add(
        self,
        ids: Sequence[str],
        chunks: Sequence[Chunk],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        """Persist chunks and their embeddings."""

    @abstractmethod
    def query(self, embedding: Sequence[float], top_k: int) -> List[RetrievedChunk]:
        """Return the ``top_k`` most similar chunks."""

    @abstractmethod
    def delete_document(self, document_id: int) -> int:
        """Remove every chunk belonging to ``document_id``; returns the count."""

    @abstractmethod
    def count(self) -> int:
        """Total number of stored chunks."""

    @abstractmethod
    def reset(self) -> None:
        """Delete every stored chunk."""


def _clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma only accepts scalar metadata values."""
    return {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}


class ChromaVectorStore(BaseVectorStore):
    """Persistent ChromaDB collection using cosine distance."""

    backend = "chromadb"

    def __init__(self) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_DIR,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids, chunks, embeddings) -> None:
        self._collection.add(
            ids=list(ids),
            documents=[c.text for c in chunks],
            metadatas=[_clean_metadata(c.metadata) for c in chunks],
            embeddings=[list(map(float, e)) for e in embeddings],
        )

    def query(self, embedding, top_k) -> List[RetrievedChunk]:
        total = self.count()
        if total == 0:
            return []
        result = self._collection.query(
            query_embeddings=[list(map(float, embedding))],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            RetrievedChunk(
                text=doc,
                metadata=dict(meta or {}),
                score=max(0.0, 1.0 - float(dist)),
            )
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]

    def delete_document(self, document_id: int) -> int:
        existing = self._collection.get(where={"document_id": int(document_id)})
        ids = existing.get("ids", []) or []
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def count(self) -> int:
        return int(self._collection.count())

    def reset(self) -> None:
        self._client.delete_collection(settings.CHROMA_COLLECTION)
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )


class LocalVectorStore(BaseVectorStore):
    """JSON-backed cosine-similarity store used when ChromaDB is unavailable."""

    backend = "local-json"

    def __init__(self) -> None:
        directory = Path(settings.CHROMA_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        self._path = directory / (settings.CHROMA_COLLECTION + "_local.json")
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            self._records = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Could not read local vector store (%s); starting empty", exc)
            self._records = []

    def _persist(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._records), encoding="utf-8")
        tmp.replace(self._path)

    def add(self, ids, chunks, embeddings) -> None:
        with self._lock:
            for chunk_id, chunk, embedding in zip(ids, chunks, embeddings):
                self._records.append(
                    {
                        "id": chunk_id,
                        "text": chunk.text,
                        "metadata": _clean_metadata(chunk.metadata),
                        "embedding": [float(v) for v in embedding],
                    }
                )
            self._persist()

    def query(self, embedding, top_k) -> List[RetrievedChunk]:
        with self._lock:
            records = list(self._records)
        if not records:
            return []

        query_vector = [float(v) for v in embedding]
        query_norm = math.sqrt(sum(v * v for v in query_vector)) or 1.0

        scored: List[tuple[float, Dict[str, Any]]] = []
        for record in records:
            vector = record["embedding"]
            if len(vector) != len(query_vector):
                continue
            dot = sum(a * b for a, b in zip(query_vector, vector))
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            scored.append((dot / (query_norm * norm), record))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(text=rec["text"], metadata=dict(rec["metadata"]), score=max(0.0, score))
            for score, rec in scored[:top_k]
        ]

    def delete_document(self, document_id: int) -> int:
        with self._lock:
            before = len(self._records)
            self._records = [
                r for r in self._records if r["metadata"].get("document_id") != int(document_id)
            ]
            removed = before - len(self._records)
            if removed:
                self._persist()
        return removed

    def count(self) -> int:
        return len(self._records)

    def reset(self) -> None:
        with self._lock:
            self._records = []
            self._persist()


_store: BaseVectorStore | None = None
_store_lock = threading.Lock()


def get_vector_store() -> BaseVectorStore:
    """Return the process-wide vector store, preferring ChromaDB."""
    global _store
    with _store_lock:
        if _store is None:
            try:
                _store = ChromaVectorStore()
                logger.info("Vector store backend: chromadb (%s)", settings.CHROMA_DIR)
            except Exception as exc:
                logger.warning("ChromaDB unavailable (%s); using local JSON vector store", exc)
                _store = LocalVectorStore()
        return _store


def reset_vector_store_singleton() -> None:
    """Drop the cached store instance (used by tests)."""
    global _store
    with _store_lock:
        _store = None
