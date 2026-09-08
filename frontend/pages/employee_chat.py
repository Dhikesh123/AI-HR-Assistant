"""Employee chat page."""
from __future__ import annotations

import streamlit as st

from api_client import ApiError
from components.chat import render_conversation, render_message
from components.sidebar import render_sidebar
from state import client, current_user, start_new_chat

SUGGESTIONS = [
    "How many casual leaves do I get?",
    "What is the work from home policy?",
    "How many public holidays are there this year?",
    "What is my medical insurance cover?",
]


def _ask(question: str) -> None:
    """Send a question to the backend and append both messages to the thread."""
    st.session_state["messages"].append({"role": "user", "content": question})

    try:
        with st.spinner("Searching HR documents..."):
            result = client().ask(question, st.session_state.get("conversation_id"))
    except ApiError as exc:
        st.session_state["messages"].pop()
        st.error(str(exc))
        return

    st.session_state["conversation_id"] = result["conversation_id"]
    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result.get("sources", []),
            "message_id": result.get("message_id"),
            "conversation_id": result["conversation_id"],
            "answered": result.get("answered", True),
        }
    )


def render() -> None:
    """Render the employee chat experience."""
    render_sidebar()
    user = current_user() or {}

    st.title("💬 Ask HR")
    st.caption(
        f"Hello, {user.get('name', 'there')} — ask anything about leave, benefits, "
        "attendance or company policy."
    )

    messages = st.session_state.get("messages", [])

    if not messages:
        st.markdown("##### Try one of these")
        columns = st.columns(2)
        for index, suggestion in enumerate(SUGGESTIONS):
            if columns[index % 2].button(suggestion, use_container_width=True, key=f"sug_{index}"):
                _ask(suggestion)
                st.rerun()
        st.divider()

    render_conversation(messages)

    question = st.chat_input("Ask your HR question...")
    if question:
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            _ask(question.strip())
            st.rerun()

    if messages:
        st.divider()
        if st.button("Start a new conversation"):
            start_new_chat()
            st.rerun()


render()
