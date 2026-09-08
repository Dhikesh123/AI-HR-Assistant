"""Document routes (HR admin only)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.dependencies import require_admin
from backend.core.logging_config import get_logger
from backend.database.database import get_db
from backend.models.user import User
from backend.schemas.document import DocumentResponse, DocumentUploadResponse
from backend.services import document_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentUploadResponse:
    """Upload an HR document and index it into the vector store."""
    content = await file.read()

    try:
        extension = document_service.validate_upload(file.filename or "", len(content))
    except document_service.DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    logger.info("Admin id=%s uploading %s (%s bytes)", admin.id, file.filename, len(content))

    file_path = document_service.save_upload(content, file.filename or "document")
    document = document_service.create_document(
        db,
        filename=file.filename or file_path.name,
        file_path=file_path,
        file_type=extension,
        file_size=len(content),
        uploaded_by=admin.id,
    )
    document = document_service.index_document(db, document)

    if document.status.value == "failed":
        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(document),
            message=f"Document saved but processing failed: {document.error_message}",
        )

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        message=f"Document indexed successfully ({document.chunk_count} chunks)",
    )


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> List[DocumentResponse]:
    """List every uploaded HR document."""
    return [DocumentResponse.model_validate(d) for d in document_service.list_documents(db)]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentResponse:
    """Fetch metadata for a single document."""
    try:
        document = document_service.get_document(db, document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    """Delete a document, its file and its vectors."""
    try:
        document_service.delete_document(db, document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> DocumentResponse:
    """Re-run extraction, chunking and embedding for a document."""
    try:
        document = document_service.reindex_document(db, document_id)
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if document.status.value == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Re-indexing failed: {document.error_message}",
        )
    return DocumentResponse.model_validate(document)


@router.get("/config/limits", response_model=dict)
def upload_limits(admin: User = Depends(require_admin)) -> dict:
    """Expose upload constraints so the UI can validate before sending."""
    return {
        "allowed_extensions": settings.ALLOWED_EXTENSIONS,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }
