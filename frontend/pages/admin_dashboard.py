"""HR admin dashboard: analytics, document management and question review."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from api_client import ApiError
from components.sidebar import render_sidebar
from state import client, is_admin

STATUS_ICONS = {"indexed": "✅", "processing": "⏳", "failed": "❌"}


def _format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _metrics(analytics: Dict[str, Any]) -> None:
    row1 = st.columns(4)
    row1[0].metric("Documents", analytics.get("total_documents", 0))
    row1[1].metric("Questions asked", analytics.get("total_questions", 0))
    row1[2].metric("Satisfaction", f"{analytics.get('satisfaction_rate', 0):.0f}%")
    row1[3].metric("Unanswered", analytics.get("unanswered_questions", 0))

    row2 = st.columns(4)
    row2[0].metric("Indexed chunks", analytics.get("indexed_chunks", 0))
    row2[1].metric("👍 Positive", analytics.get("positive_feedback", 0))
    row2[2].metric("👎 Negative", analytics.get("negative_feedback", 0))
    row2[3].metric("Avg. latency", f"{analytics.get('avg_latency_ms', 0)} ms")


def _upload_section() -> None:
    st.subheader("Upload HR document")
    uploaded = st.file_uploader(
        "PDF, DOCX, TXT or Markdown (max 20 MB)",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=False,
    )
    if uploaded is not None and st.button("Upload and index", type="primary"):
        with st.spinner(f"Processing {uploaded.name}..."):
            try:
                result = client().upload_document(uploaded.name, uploaded.getvalue(), uploaded.type)
                document = result["document"]
                if document["status"] == "failed":
                    st.error(result["message"])
                else:
                    st.success(result["message"])
                    st.rerun()
            except ApiError as exc:
                st.error(str(exc))


def _documents_section(documents: List[Dict[str, Any]]) -> None:
    st.subheader("HR documents")
    if not documents:
        st.info("No documents yet. Upload one above, or run `python -m backend.database.init_db`.")
        return

    for document in documents:
        with st.container(border=True):
            info, meta, actions = st.columns([5, 3, 3])
            icon = STATUS_ICONS.get(document["status"], "•")
            info.markdown(f"{icon} **{document['filename']}**")
            if document.get("error_message"):
                info.caption(f"⚠️ {document['error_message']}")
            meta.caption(
                f"{document['chunk_count']} chunks · "
                f"{document['file_size'] / 1024:.0f} KB · "
                f"{_format_timestamp(document['created_at'])}"
            )
            reindex_col, delete_col = actions.columns(2)
            if reindex_col.button(
                "Re-index", key=f"re_{document['id']}", use_container_width=True
            ):
                with st.spinner("Re-indexing..."):
                    try:
                        client().reindex_document(document["id"])
                        st.success(f"{document['filename']} re-indexed")
                        st.rerun()
                    except ApiError as exc:
                        st.error(str(exc))
            if delete_col.button("Delete", key=f"rm_{document['id']}", use_container_width=True):
                try:
                    client().delete_document(document["id"])
                    st.rerun()
                except ApiError as exc:
                    st.error(str(exc))


def _questions_table(items: List[Dict[str, Any]], empty_message: str) -> None:
    if not items:
        st.info(empty_message)
        return
    frame = pd.DataFrame(
        [
            {
                "Question": item["question"],
                "Employee": item.get("user_email", ""),
                "Answered": "Yes" if item["answered"] else "No",
                "Asked": _format_timestamp(item["created_at"]),
            }
            for item in items
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def _feedback_table(entries: List[Dict[str, Any]]) -> None:
    if not entries:
        st.info("No feedback submitted yet.")
        return
    frame = pd.DataFrame(
        [
            {
                "Rating": "👍" if entry["rating"] == "positive" else "👎",
                "Comment": entry.get("comment") or "-",
                "Conversation": entry["conversation_id"],
                "When": _format_timestamp(entry["created_at"]),
            }
            for entry in entries
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render() -> None:
    """Render the admin dashboard."""
    render_sidebar()

    if not is_admin():
        st.error("This page requires HR administrator access.")
        return

    st.title("📊 HR Admin Dashboard")

    api = client()
    try:
        analytics = api.analytics()
    except ApiError as exc:
        st.error(str(exc))
        return

    _metrics(analytics)
    st.divider()

    documents_tab, questions_tab, unanswered_tab, feedback_tab = st.tabs(
        ["Documents", "Recent questions", "Content gaps", "Feedback"]
    )

    with documents_tab:
        _upload_section()
        st.divider()
        try:
            _documents_section(api.documents())
        except ApiError as exc:
            st.error(str(exc))

    with questions_tab:
        st.subheader("What employees are asking")
        try:
            _questions_table(api.questions().get("items", []), "No questions asked yet.")
        except ApiError as exc:
            st.error(str(exc))

    with unanswered_tab:
        st.subheader("Questions the documents did not cover")
        st.caption("Use this list to decide which HR policies need to be written or uploaded.")
        try:
            _questions_table(
                api.unanswered().get("items", []),
                "Every question so far was answered from the documents.",
            )
        except ApiError as exc:
            st.error(str(exc))

    with feedback_tab:
        st.subheader("Employee feedback")
        try:
            _feedback_table(api.feedback())
        except ApiError as exc:
            st.error(str(exc))


render()
