"""Chat request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Source(BaseModel):
    """A single citation returned with an answer."""

    document: str
    page: Optional[int] = None
    section: Optional[str] = None
    score: Optional[float] = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[int] = None

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question must not be empty")
        return cleaned


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    conversation_id: int
    message_id: int
    answered: bool = True
    latency_ms: int = 0


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: List[Source] = []
    answered: bool = True
    created_at: datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: List[MessageResponse] = []
