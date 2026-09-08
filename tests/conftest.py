"""Shared pytest fixtures.

Every test runs against a throwaway SQLite database and a throwaway vector
store directory, so tests never touch the developer's real data.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

TMP_ROOT = Path(tempfile.mkdtemp(prefix="hr_assistant_tests_"))

# Environment must be set before backend.core.config is first imported.
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{(TMP_ROOT / 'test.db').as_posix()}",
        "CHROMA_DIR": str(TMP_ROOT / "chroma"),
        "CHROMA_COLLECTION": "test_hr_documents",
        "UPLOAD_DIR": str(TMP_ROOT / "uploads"),
        "OPENAI_API_KEY": "",
        "EMBEDDING_PROVIDER": "local",
        "JWT_SECRET_KEY": "test-secret-key",
        "LOG_LEVEL": "WARNING",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from backend.core.config import settings  # noqa: E402
from backend.database.database import Base, engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.rag.vector_store import get_vector_store  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_hr_documents"


@pytest.fixture(scope="session", autouse=True)
def _prepare_environment() -> Iterator[None]:
    """Create a clean schema and vector collection for the test session."""
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    get_vector_store().reset()
    yield


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """FastAPI test client (runs the app lifespan, which seeds demo users)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": settings.SEED_ADMIN_EMAIL, "password": settings.SEED_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def employee_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": settings.SEED_EMPLOYEE_EMAIL, "password": settings.SEED_EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def employee_headers(employee_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {employee_token}"}


@pytest.fixture(scope="session")
def indexed_corpus(client: TestClient, admin_token: str) -> int:
    """Index the sample HR documents once for the whole test session."""
    from backend.services import rag_service

    if rag_service.index_stats()["chunks"] > 0:
        return rag_service.index_stats()["chunks"]

    for index, path in enumerate(sorted(SAMPLE_DIR.glob("*.pdf")), start=1):
        rag_service.ingest_document(path, document_id=1000 + index, document_name=path.name)
    return rag_service.index_stats()["chunks"]
