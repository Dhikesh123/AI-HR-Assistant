"""HTTP client for the AI HR Assistant backend.

The frontend never touches the database, the vector store or the LLM directly -
everything goes through the REST API, so API keys stay server-side.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_TIMEOUT = 120


class ApiError(Exception):
    """A readable error raised for any non-2xx API response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    """Thin wrapper over the backend REST API."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.token = token

    # -- plumbing -------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers={**self._headers(), **kwargs.pop("headers", {})},
                timeout=kwargs.pop("timeout", DEFAULT_TIMEOUT),
                **kwargs,
            )
        except requests.ConnectionError as exc:
            raise ApiError(
                "Cannot reach the backend. Start it with: uvicorn backend.main:app --reload"
            ) from exc
        except requests.Timeout as exc:
            raise ApiError("The request timed out. Please try again.") from exc

        if response.status_code == 204:
            return None

        if response.status_code >= 400:
            detail = "Request failed"
            try:
                body = response.json()
                detail = body.get("detail", detail) if isinstance(body, dict) else detail
            except ValueError:
                detail = response.text[:200] or detail
            if isinstance(detail, list):  # pydantic error list
                detail = "; ".join(str(item.get("msg", item)) for item in detail)
            raise ApiError(str(detail), status_code=response.status_code)

        try:
            return response.json()
        except ValueError:
            return None

    # -- health ---------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health", timeout=10)

    # -- auth -----------------------------------------------------------
    def login(self, email: str, password: str) -> Dict[str, Any]:
        return self._request("POST", "/api/auth/login", json={"email": email, "password": password})

    def register(self, name: str, email: str, password: str, role: str = "employee") -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/auth/register",
            json={"name": name, "email": email, "password": password, "role": role},
        )

    def me(self) -> Dict[str, Any]:
        return self._request("GET", "/api/auth/me")

    # -- chat -----------------------------------------------------------
    def ask(self, question: str, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/chat",
            json={"question": question, "conversation_id": conversation_id},
        )

    def history(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/chat/history")

    def conversation(self, conversation_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/chat/{conversation_id}")

    def delete_conversation(self, conversation_id: int) -> None:
        self._request("DELETE", f"/api/chat/{conversation_id}")

    # -- feedback -------------------------------------------------------
    def send_feedback(
        self,
        conversation_id: int,
        message_id: int,
        rating: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/api/feedback",
            json={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "rating": rating,
                "comment": comment,
            },
        )

    def feedback(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/feedback")

    # -- documents (admin) ----------------------------------------------
    def upload_document(self, filename: str, content: bytes, content_type: str) -> Dict[str, Any]:
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        return self._request("POST", "/api/documents/upload", files=files, timeout=300)

    def documents(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/api/documents")

    def delete_document(self, document_id: int) -> None:
        self._request("DELETE", f"/api/documents/{document_id}")

    def reindex_document(self, document_id: int) -> Dict[str, Any]:
        return self._request("POST", f"/api/documents/{document_id}/reindex", timeout=300)

    # -- admin analytics ------------------------------------------------
    def analytics(self) -> Dict[str, Any]:
        return self._request("GET", "/api/admin/analytics")

    def questions(self, limit: int = 50) -> Dict[str, Any]:
        return self._request("GET", f"/api/admin/questions?limit={limit}")

    def unanswered(self, limit: int = 50) -> Dict[str, Any]:
        return self._request("GET", f"/api/admin/unanswered?limit={limit}")


def backend_status(client: ApiClient) -> Tuple[bool, Dict[str, Any]]:
    """Return ``(is_up, health_payload)`` without raising."""
    try:
        return True, client.health()
    except ApiError:
        return False, {}
