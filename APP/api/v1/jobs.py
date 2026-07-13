"""
Jobs router — /api/v1/jobs

Handles:
  GET  /               — List discovered jobs for the current user (paginated)
  POST /discover       — Manually trigger the Discovery Agent
  GET  /{job_id}       — Get a single discovered job's detail
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.models.jobs import DiscoveredJob
from APP.models.user import UserPreferences
from APP.models.resume import ResumeVersion
from APP.schemas.job import JobListResponse, JobRead
from APP.agents.discovery_agent import find_opportunities_node

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/", response_model=JobListResponse, summary="List discovered jobs")
def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated discovered jobs for the authenticated user."""
    user = get_or_create_local_user(current_user, db)

    total = db.query(DiscoveredJob).filter(DiscoveredJob.user_id == user.id).count()
    jobs = (
        db.query(DiscoveredJob)
        .filter(DiscoveredJob.user_id == user.id)
        .order_by(DiscoveredJob.relevance_score.desc(), DiscoveredJob.discovered_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return JobListResponse(total=total, jobs=jobs)


@router.post("/discover", status_code=status.HTTP_202_ACCEPTED, summary="Trigger job discovery")
def trigger_discovery(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs the Discovery Agent synchronously for the current user
    and persists found jobs to the database.

    For production use, trigger via the Celery task instead.
    """
    user = get_or_create_local_user(current_user, db)

    # Load profile
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

    # Load preferences
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    prefs_dict = {
        "preferred_roles": prefs.preferred_roles or [] if prefs else [],
        "preferred_locations": prefs.preferred_locations or [] if prefs else [],
        "preferred_companies": prefs.preferred_companies or [] if prefs else [],
        "job_type": prefs.job_type if prefs else "full-time",
        "interests": prefs.interests if prefs else "",
        "goal": prefs.goal if prefs else "",
    }

    agent_state = {
        "user_id": user.id,
        "raw_resume": resume.raw_text or "",
        "user_preferences": prefs_dict,
        "extracted_profile": resume.structured_data,
        "found_jobs": None,
        "tailoring_results": None,
        "resume_versions": None,
        "application_results": None,
        "notifications_sent": None,
        "current_step": "",
        "error": None,
    }

    result = find_opportunities_node(agent_state)

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    found_jobs: list[dict] = result.get("found_jobs") or []

    # Persist jobs to DB
    saved_count = 0
    for job_dict in found_jobs:
        existing = (
            db.query(DiscoveredJob)
            .filter(
                DiscoveredJob.user_id == user.id,
                DiscoveredJob.title == job_dict.get("title"),
                DiscoveredJob.company == job_dict.get("company"),
            )
            .first()
        )
        if not existing:
            db.add(
                DiscoveredJob(
                    user_id=user.id,
                    title=job_dict.get("title", ""),
                    company=job_dict.get("company", ""),
                    description=job_dict.get("description", ""),
                    location=job_dict.get("location", ""),
                    source=job_dict.get("source", "google_jobs"),
                    source_url=job_dict.get("source_url", ""),
                    relevance_score=job_dict.get("relevance_score"),
                )
            )
            saved_count += 1

    db.commit()
    logger.info("Discovery complete for user %s — saved %d new jobs.", user.id, saved_count)

    return {
        "status": "success",
        "jobs_found": len(found_jobs),
        "jobs_saved": saved_count,
    }


@router.get("/{job_id}", response_model=JobRead, summary="Get a discovered job by ID")
def get_job(
    job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single discovered job (must belong to the authenticated user)."""
    user = get_or_create_local_user(current_user, db)

    job = (
        db.query(DiscoveredJob)
        .filter(DiscoveredJob.id == job_id, DiscoveredJob.user_id == user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job
