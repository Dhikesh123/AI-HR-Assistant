"""Vercel serverless entrypoint. Re-exports the FastAPI app defined in backend/main.py."""
from backend.main import app  # noqa: F401
