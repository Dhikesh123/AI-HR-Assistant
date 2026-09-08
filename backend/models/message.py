"""Message ORM model."""
from __future__ import annotations

import enum
import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.database import Base
from backend.models.user import utcnow


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    @property
    def sources(self) -> list[dict[str, Any]]:
        """Decoded source citations attached to an assistant message."""
        if not self.sources_json:
            return []
        try:
            return json.loads(self.sources_json)
        except json.JSONDecodeError:
            return []

    @sources.setter
    def sources(self, value: list[dict[str, Any]]) -> None:
        self.sources_json = json.dumps(value, ensure_ascii=False)
