"""AI HR Assistant - Streamlit entry point.

Run from the project root:

    streamlit run frontend/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make sibling modules importable no matter how Streamlit is launched.
FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from state import init_state, is_admin, is_authenticated  # noqa: E402

st.set_page_config(
    page_title="AI HR Assistant",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

STYLE = """
<style>
  .block-container {padding-top: 2.5rem; max-width: 1150px;}
  [data-testid="stMetricValue"] {font-size: 1.9rem;}
  section[data-testid="stSidebar"] {width: 310px !important;}
  .stChatMessage {border-radius: 12px;}
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

init_state()

PAGES_DIR = "pages"

if not is_authenticated():
    # Only the login page exists until the user signs in; calling
    # st.navigation also disables Streamlit's automatic page discovery,
    # so no page is reachable without a token.
    pages = [st.Page(f"{PAGES_DIR}/login.py", title="Sign in", icon="🔐", default=True)]
elif is_admin():
    pages = [
        st.Page(f"{PAGES_DIR}/admin_dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page(f"{PAGES_DIR}/employee_chat.py", title="Ask HR", icon="💬"),
        st.Page(f"{PAGES_DIR}/chat_history.py", title="My conversations", icon="🕘"),
    ]
else:
    pages = [
        st.Page(f"{PAGES_DIR}/employee_chat.py", title="Ask HR", icon="💬", default=True),
        st.Page(f"{PAGES_DIR}/chat_history.py", title="My conversations", icon="🕘"),
    ]

st.navigation(pages).run()
