"""
Career Copilot — FastAPI application entry point.

Run with:
  uvicorn APP.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from APP.core.config import settings
from APP.core.database import engine
from APP.models.base import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: create DB tables on startup, clean up on shutdown.
    All models must be imported before `create_all` so their metadata is registered.
    """
    logger.info("Starting up Career Copilot API...")

    # Import all models so SQLAlchemy metadata is populated
    import APP.models.user   # noqa: F401
    import APP.models.jobs   # noqa: F401
    import APP.models.resume  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")
    except Exception as exc:
        logger.warning("Could not connect to database on startup: %s. Continuing without DB.", exc)

    # Pre-compile the LangGraph pipeline so the first request is fast
    try:
        from APP.agents.supervisor import copilot_graph  # noqa: F401
        logger.info("LangGraph supervisor pipeline compiled and ready.")
    except Exception as exc:
        logger.warning("Could not pre-compile LangGraph pipeline: %s", exc)

    yield

    logger.info("Shutting down Career Copilot API.")


def create_app() -> FastAPI:
    """App factory — creates and configures the FastAPI application."""

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.2.0",
        description=(
            "AI-powered career agent: autonomous job discovery, resume tailoring, "
            "application submission, and status tracking."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    from APP.api.v1.auth import router as auth_router
    from APP.api.v1.profile import router as profile_router
    from APP.api.v1.jobs import router as jobs_router
    from APP.api.v1.applications import router as applications_router
    from APP.api.v1.pipeline import router as pipeline_router
    from APP.api.v1.gmail import router as gmail_router

    prefix = settings.API_V1_STR  # "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(profile_router, prefix=prefix)
    app.include_router(jobs_router, prefix=prefix)
    app.include_router(applications_router, prefix=prefix)
    app.include_router(pipeline_router, prefix=prefix)
    app.include_router(gmail_router, prefix=prefix)

    # ── Health endpoints ───────────────────────────────────────────────────────
    @app.get("/", tags=["Health"])
    def root():
        return {
            "status": "ok",
            "service": settings.PROJECT_NAME,
            "version": "0.2.0",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
