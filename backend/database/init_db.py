"""Database initialisation and demo seeding."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import BASE_DIR, settings
from backend.core.logging_config import get_logger
from backend.database.database import Base, SessionLocal, engine
from backend.models import User, UserRole  # noqa: F401 - registers all tables
from backend.services import auth_service, document_service

logger = get_logger(__name__)

SAMPLE_DIR = Path(BASE_DIR) / "data" / "sample_hr_documents"


def init_db() -> None:
    """Create tables if they do not exist and ensure the demo accounts exist."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_users(db)


def _seed_users(db: Session) -> None:
    """Create the demo admin and employee accounts on first run."""
    if db.scalar(select(User).limit(1)) is not None:
        return

    auth_service.register_user(
        db,
        name="HR Admin",
        email=settings.SEED_ADMIN_EMAIL,
        password=settings.SEED_ADMIN_PASSWORD,
        role=UserRole.admin,
    )
    auth_service.register_user(
        db,
        name="Demo Employee",
        email=settings.SEED_EMPLOYEE_EMAIL,
        password=settings.SEED_EMPLOYEE_PASSWORD,
        role=UserRole.employee,
    )
    logger.info("Seeded demo admin and employee accounts")


def seed_sample_documents() -> int:
    """Index every sample HR document. Returns the number newly indexed."""
    if not SAMPLE_DIR.exists():
        logger.warning("Sample document directory not found: %s", SAMPLE_DIR)
        return 0

    files = sorted(
        p for p in SAMPLE_DIR.iterdir()
        if p.suffix.lower() in settings.ALLOWED_EXTENSIONS
    )
    if not files:
        logger.warning("No sample documents found in %s", SAMPLE_DIR)
        return 0

    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == UserRole.admin))
        documents = document_service.ingest_sample_documents(
            db, files, uploaded_by=admin.id if admin else None
        )
        for document in documents:
            logger.info(
                "Seeded %s -> %s (%s chunks)",
                document.filename,
                document.status.value,
                document.chunk_count,
            )
        return len(documents)


if __name__ == "__main__":  # pragma: no cover - manual bootstrap
    init_db()
    count = seed_sample_documents()
    print(f"Database initialised. Indexed {count} sample document(s).")
