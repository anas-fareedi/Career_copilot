"""
Pipeline router — /api/v1/pipeline

Handles:
  POST /run               — Manually trigger discovery + tailor pipeline via Celery
  GET  /status/{task_id}  — Poll Celery task result by task ID
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from APP.core.database import get_db
from APP.core.security import CurrentUser, get_current_user, get_or_create_local_user
from APP.models.resume import ResumeVersion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger discovery + tailor pipeline",
)
def trigger_pipeline(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dispatch the discovery + tailor pipeline to a Celery worker immediately.
    Returns a task_id you can poll via GET /pipeline/status/{task_id}.

    Note: The apply agent is NOT included — you must approve applications manually.
    """
    user = get_or_create_local_user(current_user, db)

    # Verify a base resume exists before dispatching
    resume = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.user_id == user.id, ResumeVersion.version_tag == "base")
        .first()
    )
    if not resume or not resume.structured_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resume found. Please upload your resume first via POST /profile/resume.",
        )

    from APP.workers.tasks import run_discovery_and_tailor_for_user
    task = run_discovery_and_tailor_for_user.delay(user.id)

    logger.info("Pipeline manually triggered for user %s — task_id: %s", user.id, task.id)
    return {
        "status": "queued",
        "task_id": task.id,
        "message": "Pipeline dispatched. Poll /pipeline/status/{task_id} for progress.",
    }


@router.get(
    "/status/{task_id}",
    summary="Poll Celery pipeline task status",
)
def get_task_status(task_id: str):
    """
    Poll the result of a dispatched pipeline task.

    Returns:
      - state: PENDING | STARTED | SUCCESS | FAILURE | RETRY
      - result: task output dict (only when SUCCESS)
      - error: error message (only when FAILURE)
    """
    from APP.workers.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    response: dict = {"task_id": task_id, "state": result.state}

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info)
    elif result.state in ("STARTED", "RETRY"):
        response["message"] = "Task is currently running or retrying."
    else:
        response["message"] = "Task is pending in queue."

    return response
