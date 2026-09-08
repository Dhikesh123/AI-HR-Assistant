"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import admin, auth, chat, documents, feedback
from backend.core.config import settings
from backend.core.logging_config import configure_logging, get_logger
from backend.database.init_db import init_db
from backend.services import rag_service
from backend.services.embedding_service import provider_name
from backend.services.llm_service import get_llm_service

configure_logging()
logger = get_logger(__name__)

DESCRIPTION = """
Enterprise-style **AI HR Assistant**.

Employees ask HR questions and receive answers grounded in the company's HR
documents, with source citations. HR admins upload and manage those documents
and review usage analytics.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and warm the RAG components on startup."""
    init_db()
    stats = rag_service.index_stats()
    logger.info(
        "%s ready | embeddings=%s | vector store=%s (%s chunks) | llm=%s",
        settings.APP_NAME,
        provider_name(),
        stats["backend"],
        stats["chunks"],
        get_llm_service().mode,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(feedback.router)
app.include_router(admin.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a readable message instead of raw pydantic errors."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"Invalid value for '{field}': {first.get('msg', 'validation error')}"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the detail, return a generic message (never leak internals)."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again."},
    )


@app.get("/", tags=["health"])
def root() -> dict:
    """Service banner."""
    return {"service": settings.APP_NAME, "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["health"])
def health() -> dict:
    """Health probe including RAG component status."""
    stats = rag_service.index_stats()
    return {
        "status": "ok",
        "embedding_provider": provider_name(),
        "vector_store": stats["backend"],
        "indexed_chunks": stats["chunks"],
        "llm_mode": get_llm_service().mode,
        "llm_model": settings.LLM_MODEL if settings.llm_enabled else None,
        "top_k": settings.TOP_K,
    }
