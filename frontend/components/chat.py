"""Chat message rendering and feedback controls."""
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from api_client import ApiError
from components.sources import render_sources
from state import client


def render_feedback_controls(message: Dict[str, Any]) -> None:
    """Thumbs up/down buttons for a single assistant message."""
    message_id = message.get("message_id")
    conversation_id = message.get("conversation_id") or st.session_state.get("conversation_id")
    if not message_id or not conversation_id:
        return

    already = st.session_state["feedback_sent"].get(message_id)
    if already:
        st.caption("Thanks for the feedback " + ("👍" if already == "positive" else "👎"))
        return

    st.caption("Was this helpful?")
    up, down, _ = st.columns([1, 1, 8])

    def _send(rating: str) -> None:
        try:
            client().send_feedback(conversation_id, message_id, rating)
            st.session_state["feedback_sent"][message_id] = rating
        except ApiError as exc:
            st.error(f"Could not save feedback: {exc}")

    if up.button("👍", key=f"up_{message_id}", help="This answer was helpful"):
        _send("positive")
        st.rerun()
    if down.button("👎", key=f"down_{message_id}", help="This answer was not helpful"):
        _send("negative")
        st.rerun()


def render_message(message: Dict[str, Any], show_feedback: bool = True) -> None:
    """Render one chat message with its sources and feedback controls."""
    role = message.get("role", "assistant")
    with st.chat_message(role, avatar="🧑‍💼" if role == "user" else "🤖"):
        st.markdown(message.get("content", ""))
        if role == "assistant":
            render_sources(message.get("sources") or [], key=str(message.get("message_id", "")))
            if message.get("answered") is False:
                st.info(
                    "This question is not covered by the indexed HR documents. "
                    "It has been logged for the HR team to review."
                )
            if show_feedback:
                render_feedback_controls(message)


def render_conversation(messages: List[Dict[str, Any]], show_feedback: bool = True) -> None:
    """Render a full message list."""
    for message in messages:
        render_message(message, show_feedback=show_feedback)
