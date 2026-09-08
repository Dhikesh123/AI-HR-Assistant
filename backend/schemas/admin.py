"""Admin analytics schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AnalyticsResponse(BaseModel):
    total_questions: int
    total_documents: int
    indexed_documents: int
    total_users: int
    positive_feedback: int
    negative_feedback: int
    unanswered_questions: int
    satisfaction_rate: float
    avg_latency_ms: int
    indexed_chunks: int


class QuestionItem(BaseModel):
    message_id: int
    conversation_id: int
    user_email: Optional[str] = None
    question: str
    answered: bool
    created_at: datetime


class QuestionListResponse(BaseModel):
    items: List[QuestionItem]
    total: int
