"""Chat, conversation history and feedback API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient


def _ask(client: TestClient, headers: dict, question: str, conversation_id=None) -> dict:
    response = client.post(
        "/api/chat",
        headers=headers,
        json={"question": question, "conversation_id": conversation_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/chat", json={"question": "How many leaves?"})
    assert response.status_code == 401


def test_empty_question_is_rejected(client: TestClient, employee_headers: dict) -> None:
    response = client.post("/api/chat", headers=employee_headers, json={"question": "   "})
    assert response.status_code == 422


def test_new_conversation_returns_answer_and_sources(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "How many casual leaves do I get?")
    assert body["conversation_id"]
    assert body["message_id"]
    assert body["answered"] is True
    assert "12" in body["answer"]
    assert body["sources"]
    assert body["sources"][0]["document"]
    assert body["latency_ms"] >= 0


def test_followup_reuses_conversation(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    first = _ask(client, employee_headers, "How many casual leaves do I get?")
    second = _ask(
        client, employee_headers, "Can I carry them forward?", first["conversation_id"]
    )
    assert second["conversation_id"] == first["conversation_id"]

    detail = client.get(f"/api/chat/{first['conversation_id']}", headers=employee_headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 4
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_unanswered_question_is_flagged(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "What is the company's international travel allowance?")
    assert body["answered"] is False
    assert body["sources"] == []
    assert "could not find" in body["answer"].lower()


def test_history_lists_conversations(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    _ask(client, employee_headers, "What is the work from home policy?")
    response = client.get("/api/chat/history", headers=employee_headers)
    assert response.status_code == 200
    conversations = response.json()
    assert conversations
    assert conversations[0]["message_count"] >= 2
    assert conversations[0]["title"]


def test_conversation_titles_come_from_first_question(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "How many public holidays are there?")
    detail = client.get(f"/api/chat/{body['conversation_id']}", headers=employee_headers).json()
    assert detail["title"].startswith("How many public holidays")


def test_user_cannot_read_another_users_conversation(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "What is the notice period?")

    client.post(
        "/api/auth/register",
        json={"name": "Other Person", "email": "other@acme.com", "password": "Other@1234"},
    )
    login = client.post(
        "/api/auth/login", json={"email": "other@acme.com", "password": "Other@1234"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get(f"/api/chat/{body['conversation_id']}", headers=other_headers)
    assert response.status_code == 404


def test_delete_conversation(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "What is the probation period?")
    conversation_id = body["conversation_id"]

    assert client.delete(f"/api/chat/{conversation_id}", headers=employee_headers).status_code == 204
    assert client.get(f"/api/chat/{conversation_id}", headers=employee_headers).status_code == 404


def test_missing_conversation_returns_404(client: TestClient, employee_headers: dict) -> None:
    assert client.get("/api/chat/999999", headers=employee_headers).status_code == 404


# ----------------------------------------------------------------------
# Feedback
# ----------------------------------------------------------------------
def test_submit_and_update_feedback(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "What is my medical insurance cover?")
    payload = {
        "conversation_id": body["conversation_id"],
        "message_id": body["message_id"],
        "rating": "positive",
        "comment": "Helpful answer",
    }
    created = client.post("/api/feedback", headers=employee_headers, json=payload)
    assert created.status_code == 201
    assert created.json()["rating"] == "positive"

    payload["rating"] = "negative"
    updated = client.post("/api/feedback", headers=employee_headers, json=payload)
    assert updated.status_code == 201
    assert updated.json()["rating"] == "negative"
    assert updated.json()["id"] == created.json()["id"]


def test_feedback_rejects_invalid_rating(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "How many sick leaves do I get?")
    response = client.post(
        "/api/feedback",
        headers=employee_headers,
        json={
            "conversation_id": body["conversation_id"],
            "message_id": body["message_id"],
            "rating": "excellent",
        },
    )
    assert response.status_code == 422


def test_feedback_rejects_unknown_message(
    client: TestClient, employee_headers: dict, indexed_corpus: int
) -> None:
    body = _ask(client, employee_headers, "What is the referral bonus?")
    response = client.post(
        "/api/feedback",
        headers=employee_headers,
        json={
            "conversation_id": body["conversation_id"],
            "message_id": 999999,
            "rating": "positive",
        },
    )
    assert response.status_code == 404


def test_admin_analytics_reflect_activity(
    client: TestClient, admin_headers: dict, employee_headers: dict, indexed_corpus: int
) -> None:
    _ask(client, employee_headers, "How many earned leaves do I get?")

    analytics = client.get("/api/admin/analytics", headers=admin_headers).json()
    assert analytics["total_questions"] > 0
    assert analytics["indexed_chunks"] > 0
    assert 0 <= analytics["satisfaction_rate"] <= 100

    questions = client.get("/api/admin/questions", headers=admin_headers).json()
    assert questions["items"]
    assert questions["items"][0]["question"]

    unanswered = client.get("/api/admin/unanswered", headers=admin_headers).json()
    assert all(item["answered"] is False for item in unanswered["items"])
