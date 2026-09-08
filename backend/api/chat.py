"""Chat routes. Thin wrappers around ``chat_service``."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.dependencies import get_current_user
from backend.database.database import get_db
from backend.models.user import User
from backend.rag.embeddings import EmbeddingError
from backend.rag.vector_store import VectorStoreError
from backend.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    MessageResponse,
)
from backend.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _to_message_response(message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        role=message.role.value,
        content=message.content,
        sources=message.sources,
        answered=message.answered,
        created_at=message.created_at,
    )


@router.post("", response_model=ChatResponse)
def ask_question(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Ask an HR question and get a grounded answer with citations."""
    try:
        conversation, message, result = chat_service.ask(
            db,
            user=current_user,
            question=payload.question,
            conversation_id=payload.conversation_id,
        )
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector database unavailable: {exc}",
        ) from exc

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        conversation_id=conversation.id,
        message_id=message.id,
        answered=result.answered,
        latency_ms=result.latency_ms,
    )


@router.get("/history", response_model=List[ConversationSummary])
def history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ConversationSummary]:
    """List the current user's conversations."""
    conversations = chat_service.list_conversations(db, current_user)
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            message_count=len(c.messages),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationDetail:
    """Fetch one conversation with its full message list."""
    try:
        conversation = chat_service.get_conversation(db, conversation_id, current_user)
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[_to_message_response(m) for m in conversation.messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete one of the current user's conversations."""
    try:
        chat_service.delete_conversation(db, conversation_id, current_user)
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
