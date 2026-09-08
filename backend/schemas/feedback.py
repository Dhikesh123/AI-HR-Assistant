"""Feedback schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.feedback import FeedbackRating


class FeedbackRequest(BaseModel):
    conversation_id: int
    message_id: int
    rating: FeedbackRating
    comment: Optional[str] = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    message_id: int
    rating: FeedbackRating
    comment: Optional[str] = None
    created_at: datetime
