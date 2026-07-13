"""
Profile router — /api/v1/profile

Handles:
  POST /resume              — Upload PDF resume, extract profile, store in DB
  GET  /                   — Retrieve stored profile + preferences
  PUT  /preferences        — Update job search preferences
  POST /autonomous-mode    — Toggle autonomous mode ON/OFF
  GET  /pipeline-status    — Return current pipeline state + last run time
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.models.user import UserPreferences
from APP.models.resume import ResumeVersion
from APP.schemas.profile import (
    AutonomousModeUpdate,
    PipelineStatusRead,
    ProfileExtraction,
    UserPreferencesRead,
    UserPreferencesUpdate,
)
from APP.services.resume_parser import extract_text_from_pdf
from APP.agents.profile_agent import extract_profile_node

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["Profile"])


@router.post(
    "/resume",
    summary="Upload resume PDF and extract structured profile",
    status_code=status.HTTP_200_OK,
)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts a PDF resume, runs the Profile Agent to extract a structured profile,
    and stores both the raw text and structured data in the DB.

    If the user has autonomous_mode enabled, also dispatches a discovery + tailor
    task so the pipeline reacts immediately to the new resume.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload a PDF.",
        )

    user = get_or_create_local_user(current_user, db)

    raw_bytes = await file.read()
    raw_text = extract_text_from_pdf(raw_bytes)
    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from the PDF. Please check the file.",
        )

    agent_state = {
        "user_id": user.id,
        "raw_resume": raw_text,
        "user_preferences": {},
        "extracted_profile": None,
        "found_jobs": None,
        "tailoring_results": None,
        "resume_versions": None,
        "application_results": None,
        "notifications_sent": None,
        "current_step": "",
        "error": None,
    }
    result = extract_profile_node(agent_state)

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    extracted = result.get("extracted_profile", {})

    existing = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.user_id == user.id, ResumeVersion.version_tag == "base")
        .first()
    )
    if existing:
        existing.raw_text = raw_text
        existing.structured_data = extracted
    else:
        db.add(
            ResumeVersion(
                user_id=user.id,
                raw_text=raw_text,
                structured_data=extracted,
                version_tag="base",
            )
        )
    db.commit()

    logger.info("Resume uploaded and profile extracted for user %s.", user.id)

    # Event trigger: new resume → kick off autonomous pipeline
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if prefs and prefs.autonomous_mode:
        from APP.workers.tasks import run_discovery_and_tailor_for_user
        run_discovery_and_tailor_for_user.delay(user.id)
        logger.info("Autonomous pipeline triggered after resume upload for user %s.", user.id)

    return {"status": "success", "extracted_profile": extracted}


@router.get("/", summary="Get stored profile and preferences")
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's latest extracted profile and their job preferences."""
    user = get_or_create_local_user(current_user, db)

    resume = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.user_id == user.id, ResumeVersion.version_tag == "base")
        .first()
    )
    prefs = (
        db.query(UserPreferences)
        .filter(UserPreferences.user_id == user.id)
        .first()
    )

    return {
        "user": {"id": user.id, "email": user.email},
        "extracted_profile": resume.structured_data if resume else None,
        "preferences": UserPreferencesRead.model_validate(prefs) if prefs else None,
    }


@router.put("/preferences", response_model=UserPreferencesRead, summary="Update job search preferences")
def update_preferences(
    body: UserPreferencesUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update the user's job search preferences.

    If the user has autonomous_mode enabled, dispatches a discovery task
    immediately so new preferences take effect without waiting for the next beat.
    """
    user = get_or_create_local_user(current_user, db)

    prefs = (
        db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    )
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)

    db.commit()
    db.refresh(prefs)
    logger.info("Preferences updated for user %s.", user.id)

    # Event trigger: preferences changed → re-run discovery for new search criteria
    if prefs.autonomous_mode:
        from APP.workers.tasks import run_discovery_for_user
        run_discovery_for_user.delay(user.id)
        logger.info("Discovery re-triggered after preference update for user %s.", user.id)

    return prefs


@router.post(
    "/autonomous-mode",
    response_model=PipelineStatusRead,
    summary="Enable or disable autonomous background pipeline",
)
def set_autonomous_mode(
    body: AutonomousModeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Toggle autonomous mode ON or OFF.

    When enabled:
    - Background Celery tasks run discovery + tailoring every 6 hours.
    - Updating resume or preferences triggers an immediate pipeline run.

    When disabled:
    - No background processing occurs. All runs must be manually triggered.
    """
    user = get_or_create_local_user(current_user, db)

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    prefs.autonomous_mode = body.enabled
    db.commit()
    db.refresh(prefs)

    if body.enabled:
        logger.info("Autonomous mode ENABLED for user %s.", user.id)
        # Kick off an immediate run so the user sees results right away
        from APP.workers.tasks import run_discovery_and_tailor_for_user
        run_discovery_and_tailor_for_user.delay(user.id)
    else:
        logger.info("Autonomous mode DISABLED for user %s.", user.id)

    return PipelineStatusRead.model_validate(prefs)


@router.get(
    "/pipeline-status",
    response_model=PipelineStatusRead,
    summary="Get autonomous pipeline status",
)
def get_pipeline_status(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the current pipeline state, last run time, and Gmail connection status.
    Poll this endpoint to track background task progress.
    """
    user = get_or_create_local_user(current_user, db)

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not prefs:
        return PipelineStatusRead(
            autonomous_mode=False,
            pipeline_status="idle",
            last_pipeline_run_at=None,
            gmail_connected=False,
        )

    return PipelineStatusRead.model_validate(prefs)
