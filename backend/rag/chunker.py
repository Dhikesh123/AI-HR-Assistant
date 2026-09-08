"""Text chunking with section detection.

Uses LangChain's ``RecursiveCharacterTextSplitter`` when available and falls back
to an equivalent local implementation otherwise, so the pipeline always runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from backend.core.config import settings
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]

# Headings look like "3. Leave Entitlement", "LEAVE ENTITLEMENT" or "Section 4:".
_HEADING_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*[.)]?\s+)?(?P<title>[A-Z][A-Za-z0-9 ,&/()'-]{3,70})\s*:?\s*$"
)
# Longest an unnumbered heading may be, in words. Keeps prose and running
# footers from being mistaken for section titles.
_MAX_UNNUMBERED_HEADING_WORDS = 6


@dataclass
class Chunk:
    """A single retrievable unit of text plus its citation metadata."""

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def _split_local(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Recursive character splitter used when LangChain is unavailable."""

    def split(segment: str, separators: Sequence[str]) -> List[str]:
        if len(segment) <= chunk_size:
            return [segment] if segment.strip() else []
        if not separators:
            return [segment[i : i + chunk_size] for i in range(0, len(segment), chunk_size)]

        sep, rest = separators[0], separators[1:]
        parts = segment.split(sep) if sep else list(segment)
        pieces: List[str] = []
        for part in parts:
            piece = part + sep if sep else part
            if len(piece) > chunk_size:
                pieces.extend(split(piece, rest))
            elif piece.strip():
                pieces.append(piece)
        return pieces

    pieces = split(text, SEPARATORS)

    merged: List[str] = []
    buffer = ""
    for piece in pieces:
        if len(buffer) + len(piece) <= chunk_size:
            buffer += piece
            continue
        if buffer.strip():
            merged.append(buffer.strip())
        overlap = buffer[-chunk_overlap:] if chunk_overlap and buffer else ""
        buffer = overlap + piece
    if buffer.strip():
        merged.append(buffer.strip())
    return merged


def split_text(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> List[str]:
    """Split raw text into overlapping chunks."""
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=SEPARATORS,
            length_function=len,
        )
        return [c for c in splitter.split_text(text) if c.strip()]
    except ImportError:
        return _split_local(text, chunk_size, chunk_overlap)


def detect_section(text: str, fallback: str = "General") -> str:
    """Best-effort section title for a block of text (used in citations)."""
    for line in text.splitlines()[:4]:
        stripped = line.strip()
        if not stripped or len(stripped) > 80 or stripped.endswith("."):
            continue
        match = _HEADING_RE.match(stripped)
        if not match:
            continue
        title = match.group("title").strip()
        if not match.group("number") and len(title.split()) > _MAX_UNNUMBERED_HEADING_WORDS:
            continue
        if title.isupper():
            title = title.title()
        return title
    return fallback


def create_chunks(
    pages: Iterable[Tuple[int, str]],
    document_name: str,
    document_id: int | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> List[Chunk]:
    """Turn extracted pages into chunks carrying citation metadata."""
    chunks: List[Chunk] = []
    current_section = "General"

    for page_number, page_text in pages:
        for piece in split_text(page_text, chunk_size, chunk_overlap):
            current_section = detect_section(piece, fallback=current_section)
            chunks.append(
                Chunk(
                    text=piece,
                    metadata={
                        "document_name": document_name,
                        "document_id": document_id,
                        "page_number": page_number,
                        "section": current_section,
                        "chunk_index": len(chunks),
                    },
                )
            )

    logger.info("Created %s chunk(s) for %s", len(chunks), document_name)
    return chunks
