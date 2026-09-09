"""Authentication and authorisation tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_reversible() -> None:
    hashed = hash_password("Secret@12345")
    assert hashed != "Secret@12345"
    assert verify_password("Secret@12345", hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_encodes_subject_and_role() -> None:
    token = decode_access_token(create_access_token("7", "admin"))
    assert token is not None
    assert token["sub"] == "7"
    assert token["role"] == "admin"


def test_invalid_token_is_rejected() -> None:
    assert decode_access_token("not-a-real-token") is None


def test_valid_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "employee@acme.com", "password": "Employee@123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "employee"
    assert "password" not in body["user"]


def test_invalid_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "employee@acme.com", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_login_with_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "nobody@acme.com", "password": "whatever12"}
    )
    assert response.status_code == 401


def test_register_and_duplicate_email(client: TestClient) -> None:
    payload = {"name": "New Joiner", "email": "new.joiner@acme.com", "password": "Joiner@123"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    assert first.json()["user"]["role"] == "employee"

    duplicate = client.post("/api/auth/register", json=payload)
    assert duplicate.status_code == 409


def test_register_cannot_grant_admin_role(client: TestClient) -> None:
    """A crafted body must never mint an administrator.

    /api/auth/register is public, so honouring a client-supplied role would let
    anyone with the URL take over document management.
    """
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Sneaky User",
            "email": "sneaky@acme.com",
            "password": "Sneaky@123",
            "role": "admin",
        },
    )
    # The extra field is rejected outright; either way no admin is created.
    assert response.status_code in (201, 422)
    if response.status_code == 201:
        assert response.json()["user"]["role"] == "employee"

    login = client.post(
        "/api/auth/login", json={"email": "sneaky@acme.com", "password": "Sneaky@123"}
    )
    if login.status_code == 200:
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/auth/me", headers=headers).json()["role"] == "employee"
        assert client.get("/api/documents", headers=headers).status_code == 403


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"name": "Short Pass", "email": "short@acme.com", "password": "abc"},
    )
    assert response.status_code == 422


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_profile(client: TestClient, employee_headers: dict) -> None:
    response = client.get("/api/auth/me", headers=employee_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "employee@acme.com"


def test_employee_cannot_access_admin_routes(client: TestClient, employee_headers: dict) -> None:
    for path in ["/api/documents", "/api/admin/analytics", "/api/admin/questions"]:
        assert client.get(path, headers=employee_headers).status_code == 403


def test_admin_can_access_admin_routes(client: TestClient, admin_headers: dict) -> None:
    for path in ["/api/documents", "/api/admin/analytics", "/api/admin/questions"]:
        assert client.get(path, headers=admin_headers).status_code == 200
