import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from APP.agents.orchestrator import copilot_graph
from APP.core.config import settings
from APP.core.database import engine
from APP.models.base import Base
from APP.utils import extract_text_from_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create all database tables (idempotent — skips existing tables).
    This avoids a crash on first run when tables don't exist yet.
    """
    logger.info("Starting up — creating database tables if they don't exist...")
    # Import all models so their metadata is registered before create_all
    import APP.models.user  # noqa: F401
    import APP.models.jobs  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ready.")
    except Exception as e:
        logger.warning(
            f"Could not connect to database on startup: {e}. Continuing without DB."
        )

    # Import graph here (deferred) so startup errors in graph init are visible clearly
    app.state.copilot_graph = copilot_graph
    logger.info("LangGraph pipeline compiled and ready.")

    yield  # App runs here

    logger.info("Shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", tags=["Health"])
def read_root():
    return {"status": "ok", "message": f"Welcome to {settings.PROJECT_NAME}!"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/copilot/run", tags=["Copilot"])
async def run_copilot(resume_file: UploadFile = File(...)):
    """
    Run the full career copilot pipeline from a PDF resume:
    1. Profile extraction (Agent 1)
    2. Opportunity finding (Agent 2 — mocked)
    3. Resume tailoring (Agent 3)
    """
    if resume_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF.")

    try:
        # Read content from the uploaded file
        resume_content = await resume_file.read()
        raw_resume = extract_text_from_pdf(resume_content)

        if not raw_resume or not raw_resume.strip():
            raise HTTPException(
                status_code=400, detail="Could not extract text from the PDF."
            )

    except Exception as e:
        logger.exception("Failed to read or parse PDF file.")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {e}")

    initial_state = {
        "raw_resume": raw_resume.strip(),
        "extracted_profile": None,
        "found_jobs": None,
        "tailoring_results": None,
        "error": None,
    }

    try:
        copilot_graph = app.state.copilot_graph
        final_state = copilot_graph.invoke(initial_state)
        
        logger.info(f"Final state keys: {final_state.keys()}")
        logger.info(f"Error in final state: {final_state.get('error')}")

        if final_state.get("error"):
            logger.error(f"Pipeline error: {final_state['error']}")
            raise HTTPException(status_code=500, detail=final_state["error"])

        return {
            "status": "success",
            "extracted_profile": final_state.get("extracted_profile"),
            "found_jobs": final_state.get("found_jobs"),
            "tailoring_results": final_state.get("tailoring_results"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled error in copilot pipeline")
        raise HTTPException(status_code=500, detail=str(e))
