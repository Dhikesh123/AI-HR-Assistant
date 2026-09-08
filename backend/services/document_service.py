"""Document management: validation, storage, indexing and deletion."""
from __future__ import annotations

import shutil
import unicodedata
import uuid
from pathlib import Path
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.models.document import Document, DocumentStatus
from backend.services import rag_service

logger = get_logger(__name__)


class DocumentValidationError(ValueError):
    """Raised for an invalid file type, empty file or oversized upload."""


class DocumentNotFoundError(LookupError):
    """Raised when a document id does not exist."""


def _safe_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from an upload name."""
    name = Path(filename or "").name
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._- ")
    return name.strip() or "document"


def validate_upload(filename: str, size_bytes: int) -> str:
    """Validate an upload and return its normalised extension."""
    extension = Path(filename or "").suffix.lower()
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file type '{extension or 'unknown'}'. "
            f"Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    if size_bytes <= 0:
        raise DocumentValidationError("Uploaded file is empty")
    if size_bytes > settings.max_upload_bytes:
        raise DocumentValidationError(
            f"File is too large ({size_bytes / 1_048_576:.1f} MB). "
            f"Maximum is {settings.MAX_UPLOAD_MB} MB"
        )
    return extension


def save_upload(content: bytes, filename: str) -> Path:
    """Persist upload bytes under ``UPLOAD_DIR`` with a collision-free name."""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    target = upload_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    target.write_bytes(content)
    return target


def create_document(
    db: Session,
    *,
    filename: str,
    file_path: Path,
    file_type: str,
    file_size: int,
    uploaded_by: int | None,
) -> Document:
    """Insert a document row in ``processing`` state."""
    document = Document(
        filename=_safe_filename(filename),
        file_path=str(file_path),
        file_type=file_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
        status=DocumentStatus.processing,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def index_document(db: Session, document: Document) -> Document:
    """Run the RAG ingestion pipeline and update the document status."""
    try:
        rag_service.delete_document_vectors(document.id)
        result = rag_service.ingest_document(
            document.file_path,
            document_id=document.id,
            document_name=document.filename,
        )
        document.status = DocumentStatus.indexed
        document.chunk_count = result.chunk_count
        document.error_message = None
        logger.info("Document %s indexed (%s chunks)", document.filename, result.chunk_count)
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.chunk_count = 0
        document.error_message = str(exc)[:500]
        logger.error("Document %s failed to index: %s", document.filename, exc)
    finally:
        db.add(document)
        db.commit()
        db.refresh(document)
    return document


def list_documents(db: Session) -> List[Document]:
    """All documents, newest first."""
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())


def get_document(db: Session, document_id: int) -> Document:
    """Fetch one document or raise ``DocumentNotFoundError``."""
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} not found")
    return document


def delete_document(db: Session, document_id: int) -> None:
    """Delete a document, its file on disk and its vectors."""
    document = get_document(db, document_id)
    rag_service.delete_document_vectors(document.id)

    file_path = Path(document.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError as exc:
            logger.warning("Could not delete file %s: %s", file_path, exc)

    db.delete(document)
    db.commit()
    logger.info("Deleted document %s (id=%s)", document.filename, document_id)


def reindex_document(db: Session, document_id: int) -> Document:
    """Re-run ingestion for an existing document."""
    document = get_document(db, document_id)
    if not Path(document.file_path).exists():
        document.status = DocumentStatus.failed
        document.error_message = "Source file is missing from disk"
        db.commit()
        db.refresh(document)
        return document

    document.status = DocumentStatus.processing
    db.commit()
    return index_document(db, document)


def ingest_sample_documents(db: Session, paths: Sequence[Path], uploaded_by: int | None) -> List[Document]:
    """Copy sample files into ``uploads/`` and index them (used by the seeder)."""
    documents: List[Document] = []
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    existing = {d.filename for d in list_documents(db)}
    for source in paths:
        if source.name in existing:
            continue
        target = upload_dir / f"{uuid.uuid4().hex[:8]}_{source.name}"
        shutil.copyfile(source, target)
        document = create_document(
            db,
            filename=source.name,
            file_path=target,
            file_type=source.suffix.lower(),
            file_size=target.stat().st_size,
            uploaded_by=uploaded_by,
        )
        documents.append(index_document(db, document))
    return documents
