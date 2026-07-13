"""
Applications router — /api/v1/applications

Handles:
  GET  /                    — List all applications for the current user
  GET  /stats               — Dashboard analytics (counts by status)
  POST /{job_id}/tailor     — Trigger Resume Agent for one job
  POST /{job_id}/apply      — Trigger Apply Agent for one application
  PATCH /{app_id}/status   — Manually update application status (e.g. "interviewing")
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.models.jobs import Application, ApplicationStatus, DiscoveredJob
from APP.models.resume import ResumeVersion
from APP.models.user import UserPreferences
from APP.schemas.job import ApplicationRead, ApplicationStats, ApplicationStatusUpdate
from APP.agents.resume_agent import tailor_application_node
from APP.agents.apply_agent import apply_jobs_node

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["Applications"])


@router.get("/", summary="List all applications")
def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated applications for the authenticated user."""
    user = get_or_create_local_user(current_user, db)

    total = db.query(Application).filter(Application.user_id == user.id).count()
    apps = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"total": total, "applications": [ApplicationRead.model_validate(a) for a in apps]}


@router.get("/stats", response_model=ApplicationStats, summary="Dashboard — application counts by status")
def get_stats(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return counts of applications in each status for the dashboard."""
    user = get_or_create_local_user(current_user, db)

    all_apps = db.query(Application).filter(Application.user_id == user.id).all()
    status_counts = {s.value: 0 for s in ApplicationStatus}
    for app in all_apps:
        status_counts[app.status.value] += 1

    return ApplicationStats(
        total=len(all_apps),
        discovered=status_counts["discovered"],
        tailored=status_counts["tailored"],
        submitted=status_counts["submitted"],
        interviewing=status_counts["interviewing"],
        rejected=status_counts["rejected"],
        offered=status_counts["offered"],
    )


@router.post("/{job_id}/tailor", status_code=status.HTTP_200_OK, summary="Tailor resume for a job")
def tailor_application(
    job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the Resume Agent for one discovered job.
    Creates (or updates) an Application row with the tailored documents.
    """
    user = get_or_create_local_user(current_user, db)

    # Validate job ownership
    job = (
        db.query(DiscoveredJob)
        .filter(DiscoveredJob.id == job_id, DiscoveredJob.user_id == user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    # Load base resume
    resume = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.user_id == user.id, ResumeVersion.version_tag == "base")
        .first()
    )
    if not resume or not resume.structured_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resume found. Please upload your resume first.",
        )

    # Run Resume Agent
    agent_state = {
        "user_id": user.id,
        "raw_resume": resume.raw_text or "",
        "user_preferences": {},
        "extracted_profile": resume.structured_data,
        "found_jobs": [
            {
                "title": job.title,
                "company": job.company,
                "description": job.description or "",
                "location": job.location or "",
                "source_url": job.source_url or "",
                "relevance_score": job.relevance_score or 50,
            }
        ],
        "tailoring_results": None,
        "resume_versions": None,
        "application_results": None,
        "notifications_sent": None,
        "current_step": "",
        "error": None,
    }
    result = tailor_application_node(agent_state)

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    tailoring = (result.get("tailoring_results") or [{}])[0]

    # Upsert Application row
    app = db.query(Application).filter(Application.job_id == job_id, Application.user_id == user.id).first()
    if not app:
        app = Application(user_id=user.id, job_id=job_id)
        db.add(app)

    app.tailored_resume = tailoring.get("tailored_resume_summary", "")
    app.tailored_cover_letter = tailoring.get("tailored_cover_letter", "")
    app.tailored_summary = tailoring.get("tailored_resume_summary", "")
    app.match_score = tailoring.get("match_score")
    app.missing_skills = tailoring.get("missing_skills", [])
    app.status = ApplicationStatus.TAILORED

    # Store as a ResumeVersion for history
    db.add(
        ResumeVersion(
            user_id=user.id,
            application_id=app.id if app.id else None,
            raw_text=resume.raw_text,
            tailored_resume=tailoring.get("tailored_resume_summary", ""),
            tailored_cover_letter=tailoring.get("tailored_cover_letter", ""),
            version_tag=f"{job.company[:20]}_{job.title[:20]}".replace(" ", "_").lower(),
        )
    )

    db.commit()
    db.refresh(app)
    logger.info("Tailoring complete for user %s, job %d.", user.id, job_id)

    return {"status": "success", "application": ApplicationRead.model_validate(app)}


@router.post("/{job_id}/apply", status_code=status.HTTP_200_OK, summary="Submit application for a job")
def apply_to_job(
    job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the Apply Agent for one tailored application.
    The agent is stubbed — it logs the intent but does not submit a real form.
    """
    user = get_or_create_local_user(current_user, db)

    app = (
        db.query(Application)
        .filter(Application.job_id == job_id, Application.user_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tailored application found. Run /tailor first.",
        )

    job = db.query(DiscoveredJob).filter(DiscoveredJob.id == job_id).first()

    # Build minimal state for apply agent
    agent_state = {
        "user_id": user.id,
        "raw_resume": "",
        "user_preferences": {},
        "extracted_profile": None,
        "found_jobs": [{"title": job.title, "company": job.company, "source_url": job.source_url or ""}] if job else [],
        "tailoring_results": [
            {
                "job_title": job.title if job else "",
                "company": job.company if job else "",
                "tailored_resume_summary": app.tailored_resume or "",
                "tailored_cover_letter": app.tailored_cover_letter or "",
                "relevance_score": job.relevance_score if job else 50,
            }
        ],
        "resume_versions": None,
        "application_results": None,
        "notifications_sent": None,
        "current_step": "",
        "error": None,
    }

    result = apply_jobs_node(agent_state)
    apply_results: list[dict] = result.get("application_results") or []

    # Update application status
    app.status = ApplicationStatus.SUBMITTED
    app.applied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app)

    logger.info("Apply agent ran for user %s, job %d.", user.id, job_id)
    return {
        "status": "success",
        "application_results": apply_results,
        "application": ApplicationRead.model_validate(app),
    }


@router.patch("/{app_id}/status", response_model=ApplicationRead, summary="Manually update application status")
def update_application_status(
    app_id: int,
    body: ApplicationStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow the user to manually update the status (e.g. after receiving an interview invite)."""
    user = get_or_create_local_user(current_user, db)

    app = (
        db.query(Application)
        .filter(Application.id == app_id, Application.user_id == user.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    app.status = body.status
    if body.notes:
        app.notes = body.notes
    db.commit()
    db.refresh(app)
    return app
