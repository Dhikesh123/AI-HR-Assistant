"""Frontend smoke tests.

These render the real Streamlit pages with Streamlit's AppTest harness, so a
broken import, a bad widget key or a crashing page is caught by CI rather than
by a person clicking through the UI.

They talk to a live backend on ``API_BASE_URL``; when none is running the tests
skip rather than fail.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
APP_PATH = FRONTEND_DIR / "app.py"

if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from streamlit.testing.v1 import AppTest  # noqa: E402


def _backend_credentials() -> tuple[str, dict] | None:
    """Log in against a live backend, or return None when it is not running."""
    from api_client import ApiClient, ApiError

    client = ApiClient()
    try:
        client.health()
        result = client.login("employee@acme.com", "Employee@123")
    except ApiError:
        return None
    return result["access_token"], result["user"]


@pytest.fixture(scope="module")
def credentials() -> tuple[str, dict]:
    creds = _backend_credentials()
    if creds is None:
        pytest.skip("No live backend on API_BASE_URL; start uvicorn to run frontend tests")
    return creds


def _app(signed_in: tuple[str, dict] | None = None) -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    if signed_in:
        token, user = signed_in
        app.session_state["token"] = token
        app.session_state["user"] = user
        app.session_state["messages"] = []
        app.session_state["feedback_sent"] = {}
        app.session_state["conversation_id"] = None
    return app


def test_login_page_renders_without_auth() -> None:
    app = _app().run()
    assert not app.exception
    body = " ".join(str(element.value) for element in app.markdown)
    assert "AI HR Assistant" in body


def test_employee_chat_page_renders(credentials: tuple[str, dict]) -> None:
    app = _app(credentials).run()
    assert not app.exception
    assert any("Ask HR" in title.value for title in app.title)


def test_chat_history_page_renders(credentials: tuple[str, dict]) -> None:
    app = _app(credentials)
    app.run()
    assert not app.exception


def test_admin_dashboard_blocks_employees(credentials: tuple[str, dict]) -> None:
    """An employee session must not be given the admin page."""
    token, user = credentials
    assert user["role"] == "employee"
    app = _app((token, user)).run()
    assert not app.exception
    rendered = " ".join(str(element.value) for element in app.title)
    assert "Admin" not in rendered


def test_admin_dashboard_renders_for_admin() -> None:
    from api_client import ApiClient, ApiError

    client = ApiClient()
    try:
        client.health()
        result = client.login("admin@acme.com", "Admin@123")
    except ApiError:
        pytest.skip("No live backend on API_BASE_URL")

    app = _app((result["access_token"], result["user"])).run()
    assert not app.exception
    assert any("Dashboard" in title.value for title in app.title)
