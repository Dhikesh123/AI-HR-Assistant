"""Sidebar: identity, quick actions and backend status."""
from __future__ import annotations

import streamlit as st

from api_client import backend_status
from state import client, current_user, is_admin, sign_out, start_new_chat


def render_sidebar() -> None:
    """Render the shared sidebar for authenticated users."""
    user = current_user() or {}

    with st.sidebar:
        st.markdown("### 🏢 AI HR Assistant")
        st.markdown(
            f"**{user.get('name', 'User')}**  \n"
            f"{user.get('email', '')}  \n"
            f"`{user.get('role', 'employee')}`"
        )
        st.divider()

        if not is_admin():
            if st.button("➕ New conversation", use_container_width=True):
                start_new_chat()
                st.rerun()

        if st.button("Sign out", use_container_width=True):
            sign_out()
            st.rerun()

        st.divider()
        with st.expander("System status", expanded=False):
            up, health = backend_status(client())
            if not up:
                st.error("Backend unreachable")
            else:
                st.success("Backend online")
                st.caption(
                    f"Answer mode: **{health.get('llm_mode', 'n/a')}**  \n"
                    f"Embeddings: `{health.get('embedding_provider', 'n/a')}`  \n"
                    f"Vector store: `{health.get('vector_store', 'n/a')}`  \n"
                    f"Indexed chunks: **{health.get('indexed_chunks', 0)}**  \n"
                    f"Top-K: **{health.get('top_k', '-')}**"
                )
                if health.get("llm_mode") == "extractive":
                    st.info(
                        "Running without an LLM key: answers are quoted directly "
                        "from the HR documents. Set OPENAI_API_KEY in .env for "
                        "generated answers."
                    )

        st.caption("Answers come only from indexed HR documents.")
