"""Feedback routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.dependencies import get_current_user
from backend.database.database import get_db
from backend.models.user import User
from backend.schemas.feedback import FeedbackRequest, FeedbackResponse
from backend.services import chat_service

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """Record thumbs up/down on an assistant answer."""
    try:
        feedback = chat_service.submit_feedback(
            db,
            user=current_user,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            rating=payload.rating,
            comment=payload.comment,
        )
    except chat_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except chat_service.MessageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FeedbackResponse.model_validate(feedback)


@router.get("", response_model=List[FeedbackResponse])
def list_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeedbackResponse]:
    """Admins see all feedback; employees see only their own."""
    return [FeedbackResponse.model_validate(f) for f in chat_service.list_feedback(db, current_user)]
