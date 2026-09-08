"""LLM access.

Talks to any OpenAI-compatible ``/chat/completions`` endpoint. When no API key
is configured the service falls back to a strictly extractive answerer that
quotes the retrieved HR context, so the end-to-end demo still works offline
without ever inventing information.
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence

import requests

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.rag.prompts import NO_ANSWER_RESPONSE
from backend.rag.text_utils import content_words, stem, tokenize

logger = get_logger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# A candidate sentence must cover at least this fraction of the question's
# meaningful words before the offline answerer will quote it. This is the
# "I don't know" gate for the no-API-key path.
MIN_SENTENCE_OVERLAP = 0.6

# How strongly a lower-ranked retrieval chunk is penalised when picking
# sentences, so the best-matching document wins ties.
RANK_PENALTY = 0.08


class LLMError(RuntimeError):
    """Raised when the LLM provider cannot be reached or returns an error."""


class LLMService:
    """Thin wrapper over an OpenAI-compatible chat completions API."""

    def __init__(self) -> None:
        self.model = settings.LLM_MODEL
        self.enabled = settings.llm_enabled

    @property
    def mode(self) -> str:
        """Which answering backend is active - ``llm`` or ``extractive``."""
        return "llm" if self.enabled else "extractive"

    def complete(
        self,
        messages: Sequence[Dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant text."""
        if not self.enabled:
            raise LLMError("No LLM API key configured")

        payload = {
            "model": self.model,
            "messages": list(messages),
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
        }
        try:
            response = requests.post(
                f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            logger.error("LLM request failed: %s", exc.__class__.__name__)
            raise LLMError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            # Log the status only - the body can echo the prompt back.
            logger.error("LLM provider returned HTTP %s", response.status_code)
            raise LLMError(f"LLM provider returned HTTP {response.status_code}")

        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Unexpected response format from LLM provider") from exc

    # ------------------------------------------------------------------
    # Offline fallback
    # ------------------------------------------------------------------
    @staticmethod
    def _is_boilerplate(sentence: str) -> bool:
        """Headings, document titles, policy codes and FAQ questions are not answers."""
        if not sentence.endswith((".", "!")):
            # Headings and titles carry no terminal punctuation.
            return True
        if "|" in sentence or "HR-POL-" in sentence or "HR-PRO-" in sentence:
            return True
        return "Internal HR document" in sentence

    @classmethod
    def extractive_answer(cls, question: str, chunks: Sequence) -> str:
        """Compose an answer purely from retrieved sentences.

        Every sentence returned comes verbatim from the HR documents, so this
        path is grounded by construction and cannot hallucinate. A sentence must
        cover most of the question's meaningful words to qualify, so a question
        the documents do not actually address falls through to the "could not
        find" response rather than being answered from loosely related text.
        """
        if not chunks:
            return NO_ANSWER_RESPONSE

        q_words = content_words(question)
        if not q_words:
            return NO_ANSWER_RESPONSE

        scored: List[tuple[float, str, str]] = []
        for rank, chunk in enumerate(chunks):
            document = str(chunk.metadata.get("document_name", "the HR documents"))
            # Split per line first so a heading is never glued to the sentence
            # that follows it.
            candidates = [
                part
                for line in chunk.text.splitlines()
                for part in _SENTENCE_RE.split(line)
            ]
            for sentence in candidates:
                sentence = " ".join(sentence.split())
                if len(sentence) < 25 or cls._is_boilerplate(sentence):
                    continue
                s_words = {stem(word) for word in tokenize(sentence)}
                overlap = len(q_words & s_words) / len(q_words)
                if overlap < MIN_SENTENCE_OVERLAP:
                    continue
                # Prefer sentences from better-ranked chunks and with numbers.
                bonus = 0.1 if any(ch.isdigit() for ch in sentence) else 0.0
                scored.append((overlap + bonus - rank * RANK_PENALTY, sentence, document))

        if not scored:
            return NO_ANSWER_RESPONSE

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: List[str] = []
        documents: List[str] = []
        for _, sentence, document in scored:
            if sentence in selected:
                continue
            selected.append(sentence)
            if document not in documents:
                documents.append(document)
            if len(selected) == 3:
                break

        return (
            "Based on the HR documents:\n\n"
            + " ".join(selected)
            + f"\n\n(Source: {', '.join(documents)})"
        )


_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Return the process-wide LLM service."""
    global _service
    if _service is None:
        _service = LLMService()
        logger.info("LLM service initialised in %s mode", _service.mode)
    return _service


def reset_llm_service() -> None:
    """Drop the cached service (used by tests and after config changes)."""
    global _service
    _service = None
