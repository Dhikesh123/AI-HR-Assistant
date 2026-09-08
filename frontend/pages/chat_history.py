"""Chat history page."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from api_client import ApiError
from components.chat import render_conversation
from components.sidebar import render_sidebar
from state import client


def _format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _open_conversation(conversation_id: int) -> None:
    """Load a past conversation back into the chat page."""
    try:
        detail = client().conversation(conversation_id)
    except ApiError as exc:
        st.error(str(exc))
        return

    st.session_state["conversation_id"] = conversation_id
    st.session_state["messages"] = [
        {
            "role": message["role"],
            "content": message["content"],
            "sources": message.get("sources", []),
            "message_id": message["id"],
            "conversation_id": conversation_id,
            "answered": message.get("answered", True),
        }
        for message in detail.get("messages", [])
    ]


def render() -> None:
    """Render the list of past conversations."""
    render_sidebar()

    st.title("🕘 My conversations")
    st.caption("Reopen a past conversation to continue it, or review the answers you received.")

    try:
        conversations = client().history()
    except ApiError as exc:
        st.error(str(exc))
        return

    if not conversations:
        st.info("No conversations yet. Head to **Ask HR** to get started.")
        return

    for conversation in conversations:
        with st.container(border=True):
            title_col, meta_col, action_col = st.columns([6, 3, 3])
            title_col.markdown(f"**{conversation['title']}**")
            meta_col.caption(
                f"{conversation.get('message_count', 0)} messages · "
                f"{_format_timestamp(conversation['updated_at'])}"
            )

            open_col, delete_col = action_col.columns(2)
            if open_col.button("Open", key=f"open_{conversation['id']}", use_container_width=True):
                _open_conversation(conversation["id"])
                st.rerun()
            if delete_col.button(
                "Delete", key=f"del_{conversation['id']}", use_container_width=True
            ):
                try:
                    client().delete_conversation(conversation["id"])
                    if st.session_state.get("conversation_id") == conversation["id"]:
                        st.session_state["conversation_id"] = None
                        st.session_state["messages"] = []
                    st.rerun()
                except ApiError as exc:
                    st.error(str(exc))

    if st.session_state.get("messages"):
        st.divider()
        st.subheader("Selected conversation")
        render_conversation(st.session_state["messages"], show_feedback=False)


render()
