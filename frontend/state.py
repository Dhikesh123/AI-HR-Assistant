"""Streamlit session-state helpers shared by every page."""
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from api_client import ApiClient

DEFAULTS: Dict[str, Any] = {
    "token": None,
    "user": None,
    "conversation_id": None,
    "messages": [],          # [{role, content, sources, message_id, answered}]
    "feedback_sent": {},     # message_id -> rating
    "auth_error": None,
}


def init_state() -> None:
    """Populate any missing session-state keys."""
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value.copy() if isinstance(value, (dict, list)) else value)


def client() -> ApiClient:
    """API client carrying the current access token."""
    return ApiClient(token=st.session_state.get("token"))


def is_authenticated() -> bool:
    return bool(st.session_state.get("token") and st.session_state.get("user"))


def current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("user")


def is_admin() -> bool:
    user = current_user()
    return bool(user and user.get("role") == "admin")


def sign_in(token: str, user: Dict[str, Any]) -> None:
    """Store credentials and reset any previous session's chat state."""
    st.session_state["token"] = token
    st.session_state["user"] = user
    st.session_state["conversation_id"] = None
    st.session_state["messages"] = []
    st.session_state["feedback_sent"] = {}
    st.session_state["auth_error"] = None


def sign_out() -> None:
    """Clear the whole session."""
    for key, value in DEFAULTS.items():
        st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def start_new_chat() -> None:
    """Reset the active conversation without logging out."""
    st.session_state["conversation_id"] = None
    st.session_state["messages"] = []
    st.session_state["feedback_sent"] = {}
