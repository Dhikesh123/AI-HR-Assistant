"""Admin analytics routes (HR admin only)."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.dependencies import require_admin
from backend.database.database import get_db
from backend.models.conversation import Conversation
from backend.models.document import Document, DocumentStatus
from backend.models.feedback import Feedback, FeedbackRating
from backend.models.message import Message, MessageRole
from backend.models.user import User
from backend.schemas.admin import AnalyticsResponse, QuestionItem, QuestionListResponse
from backend.services import rag_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> AnalyticsResponse:
    """Aggregate usage metrics for the admin dashboard."""
    total_questions = _count(
        db, select(func.count()).select_from(Message).where(Message.role == MessageRole.user)
    )
    total_documents = _count(db, select(func.count()).select_from(Document))
    indexed_documents = _count(
        db,
        select(func.count()).select_from(Document).where(Document.status == DocumentStatus.indexed),
    )
    total_users = _count(db, select(func.count()).select_from(User))
    positive = _count(
        db,
        select(func.count()).select_from(Feedback).where(Feedback.rating == FeedbackRating.positive),
    )
    negative = _count(
        db,
        select(func.count()).select_from(Feedback).where(Feedback.rating == FeedbackRating.negative),
    )
    unanswered = _count(
        db,
        select(func.count())
        .select_from(Message)
        .where(Message.role == MessageRole.assistant, Message.answered.is_(False)),
    )
    avg_latency = db.scalar(
        select(func.avg(Message.latency_ms)).where(Message.role == MessageRole.assistant)
    )

    rated = positive + negative
    return AnalyticsResponse(
        total_questions=total_questions,
        total_documents=total_documents,
        indexed_documents=indexed_documents,
        total_users=total_users,
        positive_feedback=positive,
        negative_feedback=negative,
        unanswered_questions=unanswered,
        satisfaction_rate=round(positive / rated * 100, 1) if rated else 0.0,
        avg_latency_ms=int(avg_latency or 0),
        indexed_chunks=rag_service.index_stats()["chunks"],
    )


def _question_rows(db: Session, limit: int, unanswered_only: bool) -> List[QuestionItem]:
    """Employee questions paired with the answered flag of the reply."""
    assistant_alias = Message.__table__.alias("assistant")

    stmt = (
        select(Message, User.email, assistant_alias.c.answered)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .outerjoin(
            assistant_alias,
            (assistant_alias.c.conversation_id == Message.conversation_id)
            & (assistant_alias.c.id > Message.id)
            & (assistant_alias.c.role == MessageRole.assistant.value),
        )
        .where(Message.role == MessageRole.user)
        .order_by(Message.created_at.desc(), assistant_alias.c.id.asc())
        .limit(limit * 4)
    )

    seen: set[int] = set()
    items: List[QuestionItem] = []
    for message, email, answered in db.execute(stmt).all():
        if message.id in seen:
            continue
        seen.add(message.id)
        is_answered = bool(answered) if answered is not None else False
        if unanswered_only and is_answered:
            continue
        items.append(
            QuestionItem(
                message_id=message.id,
                conversation_id=message.conversation_id,
                user_email=email,
                question=message.content,
                answered=is_answered,
                created_at=message.created_at,
            )
        )
        if len(items) >= limit:
            break
    return items


@router.get("/questions", response_model=QuestionListResponse)
def recent_questions(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> QuestionListResponse:
    """Most recent employee questions."""
    items = _question_rows(db, limit=limit, unanswered_only=False)
    total = _count(
        db, select(func.count()).select_from(Message).where(Message.role == MessageRole.user)
    )
    return QuestionListResponse(items=items, total=total)


@router.get("/unanswered", response_model=QuestionListResponse)
def unanswered_questions(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> QuestionListResponse:
    """Questions the assistant could not answer - the HR content gap list."""
    items = _question_rows(db, limit=limit, unanswered_only=True)
    total = _count(
        db,
        select(func.count())
        .select_from(Message)
        .where(Message.role == MessageRole.assistant, Message.answered.is_(False)),
    )
    return QuestionListResponse(items=items, total=total)
