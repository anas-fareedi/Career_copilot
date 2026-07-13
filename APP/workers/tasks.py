"""
Celery task definitions for Career Copilot background jobs.

Tasks:
  run_full_pipeline(user_id)                    — Run all 5 agents for one user
  run_discovery_for_user(user_id)               — Run Discovery Agent only for one user
  run_discovery_and_tailor_for_user(user_id)    — Run Discovery + Tailor agents (autonomous mode)
  run_discovery_for_all_users()                 — Beat task: discovery for ALL autonomous users
  run_discovery_and_tailor_for_all_users()      — Beat task: discovery + tailor for ALL autonomous users

Dispatching examples:
  from APP.workers.tasks import run_discovery_and_tailor_for_user
  run_discovery_and_tailor_for_user.delay(user_id="abc-123")
"""

import logging
from datetime import datetime, timezone

from APP.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_autonomous_user_ids(db) -> list[str]:
    """Return user IDs of all users with autonomous_mode=True and a base resume."""
    from APP.models.resume import ResumeVersion
    from APP.models.user import UserPreferences

    autonomous_user_ids = {
        row.user_id
        for row in db.query(UserPreferences.user_id)
        .filter(UserPreferences.autonomous_mode == True)  # noqa: E712
        .all()
    }

    resume_user_ids = {
        row.user_id
        for row in db.query(ResumeVersion.user_id)
        .filter(ResumeVersion.version_tag == "base")
        .distinct()
        .all()
    }

    return list(autonomous_user_ids & resume_user_ids)


def _set_pipeline_status(db, user_id: str, status: str) -> None:
    """Update pipeline_status and last_pipeline_run_at for a user's preferences."""
    from APP.models.user import UserPreferences

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if prefs:
        prefs.pipeline_status = status
        if status in ("done", "error"):
            prefs.last_pipeline_run_at = datetime.now(timezone.utc)
        db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="APP.workers.tasks.run_full_pipeline")
def run_full_pipeline(self, user_id: str) -> dict:
    """
    Run the complete 5-agent pipeline (profile → discovery → resume → apply → notify)
    for one user and persist results to the database.

    Args:
        user_id: Supabase UUID of the target user.

    Returns:
        Summary dict with counts of jobs found, tailored, and applied.
    """
    logger.info("[Task:run_full_pipeline] Starting for user %s", user_id)

    from APP.core.database import SessionLocal
    from APP.models.jobs import Application, ApplicationStatus, DiscoveredJob
    from APP.models.resume import ResumeVersion
    from APP.models.user import UserPreferences
    from APP.agents.supervisor import copilot_graph

    db = SessionLocal()
    try:
        _set_pipeline_status(db, user_id, "running")

        resume = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.user_id == user_id, ResumeVersion.version_tag == "base")
            .first()
        )
        if not resume or not resume.structured_data:
            logger.warning("[Task:run_full_pipeline] No resume for user %s — skipping.", user_id)
            _set_pipeline_status(db, user_id, "error")
            return {"status": "skipped", "reason": "No resume on file."}

        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        prefs_dict = {
            "preferred_roles": prefs.preferred_roles or [] if prefs else [],
            "preferred_locations": prefs.preferred_locations or [] if prefs else [],
            "preferred_companies": prefs.preferred_companies or [] if prefs else [],
            "job_type": prefs.job_type if prefs else "full-time",
            "interests": prefs.interests if prefs else "",
            "goal": prefs.goal if prefs else "",
        }

        initial_state = {
            "user_id": user_id,
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

        final_state = copilot_graph.invoke(initial_state)

        if final_state.get("error"):
            logger.error("[Task:run_full_pipeline] Pipeline error for user %s: %s", user_id, final_state["error"])
            _set_pipeline_status(db, user_id, "error")
            return {"status": "error", "error": final_state["error"]}

        found_jobs: list[dict] = final_state.get("found_jobs") or []
        saved_jobs = 0
        job_id_map: dict[str, int] = {}

        for job_dict in found_jobs:
            existing = (
                db.query(DiscoveredJob)
                .filter(
                    DiscoveredJob.user_id == user_id,
                    DiscoveredJob.title == job_dict.get("title"),
                    DiscoveredJob.company == job_dict.get("company"),
                )
                .first()
            )
            if not existing:
                new_job = DiscoveredJob(
                    user_id=user_id,
                    title=job_dict.get("title", ""),
                    company=job_dict.get("company", ""),
                    description=job_dict.get("description", ""),
                    location=job_dict.get("location", ""),
                    source=job_dict.get("source", "google_jobs"),
                    source_url=job_dict.get("source_url", ""),
                    relevance_score=job_dict.get("relevance_score"),
                )
                db.add(new_job)
                db.flush()
                job_id_map[f"{job_dict.get('company')}|{job_dict.get('title')}"] = new_job.id
                saved_jobs += 1
            else:
                job_id_map[f"{existing.company}|{existing.title}"] = existing.id

        tailoring_results: list[dict] = final_state.get("tailoring_results") or []
        saved_apps = 0

        for tailored in tailoring_results:
            if tailored.get("error"):
                continue
            key = f"{tailored.get('company')}|{tailored.get('job_title')}"
            db_job_id = job_id_map.get(key)

            app = Application(
                user_id=user_id,
                job_id=db_job_id,
                tailored_resume=tailored.get("tailored_resume_summary", ""),
                tailored_cover_letter=tailored.get("tailored_cover_letter", ""),
                tailored_summary=tailored.get("tailored_resume_summary", ""),
                match_score=tailored.get("match_score"),
                missing_skills=tailored.get("missing_skills", []),
                status=ApplicationStatus.TAILORED,
            )
            db.add(app)
            saved_apps += 1

        db.commit()
        _set_pipeline_status(db, user_id, "done")

        summary = {
            "status": "success",
            "user_id": user_id,
            "jobs_found": len(found_jobs),
            "jobs_saved_to_db": saved_jobs,
            "applications_tailored": saved_apps,
            "notifications_sent": len(final_state.get("notifications_sent") or []),
        }
        logger.info("[Task:run_full_pipeline] Complete: %s", summary)
        return summary

    except Exception as exc:
        logger.exception("[Task:run_full_pipeline] Unhandled error for user %s: %s", user_id, exc)
        try:
            _set_pipeline_status(db, user_id, "error")
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="APP.workers.tasks.run_discovery_for_user")
def run_discovery_for_user(self, user_id: str) -> dict:
    """
    Run only the Discovery Agent for one user and persist new jobs to the DB.
    Lighter alternative to run_full_pipeline when only discovery is needed.
    """
    logger.info("[Task:run_discovery_for_user] Starting for user %s", user_id)

    from APP.core.database import SessionLocal
    from APP.models.jobs import DiscoveredJob
    from APP.models.resume import ResumeVersion
    from APP.models.user import UserPreferences
    from APP.agents.discovery_agent import find_opportunities_node

    db = SessionLocal()
    try:
        resume = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.user_id == user_id, ResumeVersion.version_tag == "base")
            .first()
        )
        if not resume or not resume.structured_data:
            return {"status": "skipped", "reason": "No resume on file."}

        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        prefs_dict = {
            "preferred_roles": prefs.preferred_roles or [] if prefs else [],
            "preferred_locations": prefs.preferred_locations or [] if prefs else [],
            "job_type": prefs.job_type if prefs else "full-time",
        }

        agent_state = {
            "user_id": user_id,
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
        found_jobs: list[dict] = result.get("found_jobs") or []

        saved = 0
        for job_dict in found_jobs:
            existing = (
                db.query(DiscoveredJob)
                .filter(
                    DiscoveredJob.user_id == user_id,
                    DiscoveredJob.title == job_dict.get("title"),
                    DiscoveredJob.company == job_dict.get("company"),
                )
                .first()
            )
            if not existing:
                db.add(
                    DiscoveredJob(
                        user_id=user_id,
                        title=job_dict.get("title", ""),
                        company=job_dict.get("company", ""),
                        description=job_dict.get("description", ""),
                        location=job_dict.get("location", ""),
                        source=job_dict.get("source", "google_jobs"),
                        source_url=job_dict.get("source_url", ""),
                        relevance_score=job_dict.get("relevance_score"),
                    )
                )
                saved += 1

        db.commit()
        summary = {"status": "success", "jobs_found": len(found_jobs), "jobs_saved": saved}
        logger.info("[Task:run_discovery_for_user] %s", summary)
        return summary

    except Exception as exc:
        logger.exception("[Task:run_discovery_for_user] Error for user %s: %s", user_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="APP.workers.tasks.run_discovery_and_tailor_for_user")
def run_discovery_and_tailor_for_user(self, user_id: str) -> dict:
    """
    Autonomous mode task: Run Discovery + Resume Tailor agents for one user.
    Persists new jobs and tailored applications. Does NOT run apply agent —
    user must approve before submission.
    """
    logger.info("[Task:run_discovery_and_tailor] Starting for user %s", user_id)

    from APP.core.database import SessionLocal
    from APP.models.jobs import Application, ApplicationStatus, DiscoveredJob
    from APP.models.resume import ResumeVersion
    from APP.models.user import UserPreferences
    from APP.agents.discovery_agent import find_opportunities_node
    from APP.agents.resume_agent import tailor_application_node

    db = SessionLocal()
    try:
        _set_pipeline_status(db, user_id, "running")

        resume = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.user_id == user_id, ResumeVersion.version_tag == "base")
            .first()
        )
        if not resume or not resume.structured_data:
            logger.warning("[Task:run_discovery_and_tailor] No resume for user %s — skipping.", user_id)
            _set_pipeline_status(db, user_id, "error")
            return {"status": "skipped", "reason": "No resume on file."}

        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        prefs_dict = {
            "preferred_roles": prefs.preferred_roles or [] if prefs else [],
            "preferred_locations": prefs.preferred_locations or [] if prefs else [],
            "preferred_companies": prefs.preferred_companies or [] if prefs else [],
            "job_type": prefs.job_type if prefs else "full-time",
            "interests": prefs.interests if prefs else "",
            "goal": prefs.goal if prefs else "",
            # Pass Gmail token so discovery agent can scan inbox
            "gmail_token": prefs.gmail_token if prefs else None,
        }

        # ── Step 1: Discovery ────────────────────────────────────────────────
        discovery_state = {
            "user_id": user_id,
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
        discovery_result = find_opportunities_node(discovery_state)
        found_jobs: list[dict] = discovery_result.get("found_jobs") or []

        # Persist discovered jobs
        saved_jobs = 0
        job_id_map: dict[str, int] = {}
        for job_dict in found_jobs:
            existing = (
                db.query(DiscoveredJob)
                .filter(
                    DiscoveredJob.user_id == user_id,
                    DiscoveredJob.title == job_dict.get("title"),
                    DiscoveredJob.company == job_dict.get("company"),
                )
                .first()
            )
            if not existing:
                new_job = DiscoveredJob(
                    user_id=user_id,
                    title=job_dict.get("title", ""),
                    company=job_dict.get("company", ""),
                    description=job_dict.get("description", ""),
                    location=job_dict.get("location", ""),
                    source=job_dict.get("source", "google_jobs"),
                    source_url=job_dict.get("source_url", ""),
                    relevance_score=job_dict.get("relevance_score"),
                )
                db.add(new_job)
                db.flush()
                job_id_map[f"{job_dict.get('company')}|{job_dict.get('title')}"] = new_job.id
                saved_jobs += 1
            else:
                job_id_map[f"{existing.company}|{existing.title}"] = existing.id

        db.commit()
        logger.info("[Task:run_discovery_and_tailor] Saved %d new jobs for user %s", saved_jobs, user_id)

        # ── Step 2: Tailor top jobs ──────────────────────────────────────────
        if not found_jobs:
            _set_pipeline_status(db, user_id, "done")
            return {"status": "success", "jobs_found": 0, "jobs_saved": 0, "applications_tailored": 0}

        tailor_state = {**discovery_state, "found_jobs": found_jobs}
        tailor_result = tailor_application_node(tailor_state)

        tailoring_results: list[dict] = tailor_result.get("tailoring_results") or []
        saved_apps = 0

        for tailored in tailoring_results:
            if tailored.get("error"):
                continue
            # Find the DB job ID
            key = f"{tailored.get('company')}|{tailored.get('job_title')}"
            db_job_id = job_id_map.get(key)

            # Check if application already exists
            existing_app = (
                db.query(Application)
                .filter(Application.user_id == user_id, Application.job_id == db_job_id)
                .first()
            ) if db_job_id else None

            if not existing_app:
                db.add(Application(
                    user_id=user_id,
                    job_id=db_job_id,
                    tailored_resume=tailored.get("tailored_resume_summary", ""),
                    tailored_cover_letter=tailored.get("tailored_cover_letter", ""),
                    tailored_summary=tailored.get("tailored_resume_summary", ""),
                    match_score=tailored.get("match_score"),
                    missing_skills=tailored.get("missing_skills", []),
                    status=ApplicationStatus.TAILORED,
                ))
                saved_apps += 1

        db.commit()
        _set_pipeline_status(db, user_id, "done")

        summary = {
            "status": "success",
            "jobs_found": len(found_jobs),
            "jobs_saved": saved_jobs,
            "applications_tailored": saved_apps,
        }
        logger.info("[Task:run_discovery_and_tailor] Complete: %s", summary)
        return summary

    except Exception as exc:
        logger.exception("[Task:run_discovery_and_tailor] Error for user %s: %s", user_id, exc)
        try:
            _set_pipeline_status(db, user_id, "error")
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="APP.workers.tasks.run_discovery_for_all_users")
def run_discovery_for_all_users() -> dict:
    """
    Beat task: iterate over autonomous users who have a base resume and
    dispatch individual discovery tasks for each.
    """
    logger.info("[Task:run_discovery_for_all_users] Starting periodic discovery sweep.")

    from APP.core.database import SessionLocal
    db = SessionLocal()
    try:
        user_ids = _get_autonomous_user_ids(db)
        logger.info("[Task:run_discovery_for_all_users] Dispatching for %d autonomous users.", len(user_ids))
        for uid in user_ids:
            run_discovery_for_user.delay(uid)
        return {"status": "dispatched", "users": len(user_ids)}
    finally:
        db.close()


@celery_app.task(name="APP.workers.tasks.run_discovery_and_tailor_for_all_users")
def run_discovery_and_tailor_for_all_users() -> dict:
    """
    Beat task: run discovery + tailoring for all autonomous users every 6 hours.
    This is the primary autonomous mode task.
    """
    logger.info("[Task:run_discovery_and_tailor_for_all_users] Starting autonomous sweep.")

    from APP.core.database import SessionLocal
    db = SessionLocal()
    try:
        user_ids = _get_autonomous_user_ids(db)
        logger.info(
            "[Task:run_discovery_and_tailor_for_all_users] Dispatching for %d autonomous users.", len(user_ids)
        )
        for uid in user_ids:
            run_discovery_and_tailor_for_user.delay(uid)
        return {"status": "dispatched", "users": len(user_ids)}
    finally:
        db.close()
