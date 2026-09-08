"""Chat orchestration: conversations, messages, history and feedback."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.models.conversation import Conversation
from backend.models.feedback import Feedback, FeedbackRating
from backend.models.message import Message, MessageRole
from backend.models.user import User, UserRole
from backend.services import rag_service

logger = get_logger(__name__)


class ConversationNotFoundError(LookupError):
    """Raised when a conversation does not exist or is not owned by the user."""


class MessageNotFoundError(LookupError):
    """Raised when a message id does not exist in the given conversation."""


def _title_from_question(question: str) -> str:
    title = " ".join(question.strip().split())
    return (title[:57] + "...") if len(title) > 60 else title or "New conversation"


def get_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    """Fetch a conversation, enforcing ownership (admins may read any)."""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
    if conversation.user_id != user.id and user.role != UserRole.admin:
        # Same error as "missing" so ids cannot be probed.
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
    return conversation


def list_conversations(db: Session, user: User, limit: int = 50) -> List[Conversation]:
    """A user's conversations, most recently updated first."""
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .options(selectinload(Conversation.messages))
    )
    return list(db.scalars(stmt).all())


def delete_conversation(db: Session, conversation_id: int, user: User) -> None:
    """Delete a conversation and its messages."""
    conversation = get_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()


def build_history(conversation: Conversation, turns: int | None = None) -> List[Tuple[str, str]]:
    """Recent ``(role, content)`` pairs used for follow-up questions."""
    turns = turns or settings.HISTORY_TURNS
    messages = conversation.messages[-(turns * 2) :]
    return [(m.role.value, m.content) for m in messages]


def ask(
    db: Session,
    user: User,
    question: str,
    conversation_id: int | None = None,
) -> Tuple[Conversation, Message, rag_service.AnswerResult]:
    """Answer a question and persist both the user and assistant messages."""
    question = (question or "").strip()
    if not question:
        raise ValueError("Question must not be empty")

    if conversation_id is None:
        conversation = Conversation(user_id=user.id, title=_title_from_question(question))
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        history: List[Tuple[str, str]] = []
    else:
        conversation = get_conversation(db, conversation_id, user)
        history = build_history(conversation)

    db.add(Message(conversation_id=conversation.id, role=MessageRole.user, content=question))
    db.commit()

    result = rag_service.answer_question(question, history=history)

    assistant = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=result.answer,
        answered=result.answered,
        latency_ms=result.latency_ms,
    )
    assistant.sources = result.sources
    db.add(assistant)

    conversation.updated_at = conversation.updated_at  # touch via onupdate
    db.add(conversation)
    db.commit()
    db.refresh(assistant)
    db.refresh(conversation)

    logger.info(
        "user_id=%s conversation_id=%s answered=%s sources=%s",
        user.id,
        conversation.id,
        result.answered,
        len(result.sources),
    )
    return conversation, assistant, result


def submit_feedback(
    db: Session,
    user: User,
    conversation_id: int,
    message_id: int,
    rating: FeedbackRating,
    comment: str | None = None,
) -> Feedback:
    """Record thumbs up/down on an assistant message (idempotent per message)."""
    conversation = get_conversation(db, conversation_id, user)

    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation.id:
        raise MessageNotFoundError(f"Message {message_id} not found in conversation {conversation_id}")

    existing = db.scalar(
        select(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user.id)
    )
    if existing:
        existing.rating = rating
        existing.comment = comment
        db.commit()
        db.refresh(existing)
        return existing

    feedback = Feedback(
        user_id=user.id,
        conversation_id=conversation.id,
        message_id=message_id,
        rating=rating,
        comment=comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_feedback(db: Session, user: User, limit: int = 100) -> Sequence[Feedback]:
    """Admins see all feedback; employees see only their own."""
    stmt = select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
    if user.role != UserRole.admin:
        stmt = stmt.where(Feedback.user_id == user.id)
    return list(db.scalars(stmt).all())
