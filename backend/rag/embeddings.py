"""Embedding providers.

Three backends are supported and selected via ``EMBEDDING_PROVIDER``:

* ``openai``                - OpenAI embedding API (best quality, needs a key)
* ``sentence_transformers`` - local transformer model (needs torch)
* ``local``                 - dependency-free hashed lexical embedding

``auto`` picks the best backend that is actually available, so the demo runs
offline out of the box and upgrades automatically once a key is configured.
"""
from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import List

from backend.core.config import settings
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be produced."""


class BaseEmbedder(ABC):
    """Common interface for every embedding backend."""

    name: str = "base"
    dimension: int = 0

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of document chunks."""

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        return self.embed_documents([text])[0]


class LocalHashEmbedder(BaseEmbedder):
    """Deterministic hashed bag-of-ngrams embedding.

    Not as strong as a transformer, but it needs no network or model download,
    which keeps the whole RAG pipeline demonstrable on any machine.
    """

    name = "local-hash"

    def __init__(self, dimension: int | None = None) -> None:
        self.dimension = dimension or settings.LOCAL_EMBEDDING_DIM

    @staticmethod
    def _tokens(text: str) -> List[str]:
        words = _TOKEN_RE.findall(text.lower())
        grams = list(words)
        grams += [f"{a}_{b}" for a, b in zip(words, words[1:])]
        for word in words:
            if len(word) > 5:
                grams += [word[i : i + 4] for i in range(len(word) - 3)]
        return grams

    def _hash(self, token: str) -> tuple[int, float]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        return value % self.dimension, 1.0 if value & (1 << 63) else -1.0

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            counts: dict[str, int] = {}
            for token in self._tokens(text):
                counts[token] = counts.get(token, 0) + 1
            for token, count in counts.items():
                index, sign = self._hash(token)
                vector[index] += sign * (1.0 + math.log(count))
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


class OpenAIEmbedder(BaseEmbedder):
    """Embeddings from any OpenAI-compatible ``/embeddings`` endpoint."""

    name = "openai"

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise EmbeddingError("OPENAI_API_KEY is not configured")
        self.model = settings.EMBEDDING_MODEL
        self.dimension = 0  # discovered on first call

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        import requests

        vectors: List[List[float]] = []
        for start in range(0, len(texts), 64):
            batch = [t.replace("\n", " ") for t in texts[start : start + 64]]
            try:
                response = requests.post(
                    f"{settings.OPENAI_BASE_URL.rstrip('/')}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": batch},
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
            except Exception as exc:
                raise EmbeddingError(f"Embedding request failed: {exc}") from exc

            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)

        if vectors:
            self.dimension = len(vectors[0])
        return vectors


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local transformer embeddings via sentence-transformers."""

    name = "sentence-transformers"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise EmbeddingError("sentence-transformers is not installed") from exc

        self._model = SentenceTransformer(settings.ST_EMBEDDING_MODEL)
        self.dimension = int(self._model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


_embedder: BaseEmbedder | None = None


def _build_embedder() -> BaseEmbedder:
    provider = settings.EMBEDDING_PROVIDER.lower().strip()

    if provider in {"auto", "openai"} and settings.OPENAI_API_KEY:
        try:
            embedder = OpenAIEmbedder()
            logger.info("Embedding provider: openai (%s)", settings.EMBEDDING_MODEL)
            return embedder
        except EmbeddingError as exc:
            if provider == "openai":
                raise
            logger.warning("OpenAI embeddings unavailable (%s); trying next backend", exc)

    if provider in {"auto", "sentence_transformers"}:
        try:
            embedder = SentenceTransformerEmbedder()
            logger.info("Embedding provider: sentence-transformers (%s)", settings.ST_EMBEDDING_MODEL)
            return embedder
        except EmbeddingError as exc:
            if provider == "sentence_transformers":
                raise
            logger.info("sentence-transformers unavailable (%s); using local embeddings", exc)

    logger.info("Embedding provider: local hashed embeddings (dim=%s)", settings.LOCAL_EMBEDDING_DIM)
    return LocalHashEmbedder()


def get_embedder() -> BaseEmbedder:
    """Return the process-wide embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = _build_embedder()
    return _embedder


def reset_embedder() -> None:
    """Drop the cached embedder (used by tests and after config changes)."""
    global _embedder
    _embedder = None
