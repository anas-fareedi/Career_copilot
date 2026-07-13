"""
Resume Agent — Agent 3 in the Career Copilot pipeline.

For each discovered job (up to MAX_JOBS_TO_TAILOR), generates:
  - An ATS-optimised tailored resume summary
  - A personalised cover letter
  - A match score (0–100) and list of missing skills

Uses Gemini structured output for reliable, schema-enforced responses.
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from APP.agents.state import AgentState
from APP.core.config import settings
from APP.schemas.job import ApplicationTailoringResult

logger = logging.getLogger(__name__)


def _tailor_for_job(
    profile: dict,
    job: dict,
    llm: ChatGoogleGenerativeAI,
) -> dict:
    """
    Invoke the LLM to tailor the candidate's application for one job.
    Returns an ApplicationTailoringResult as a plain dict.
    """
    structured_llm = llm.with_structured_output(ApplicationTailoringResult)

    candidate_skills = ", ".join(profile.get("skills", []))
    candidate_summary = profile.get("summary", "")
    job_title = job.get("title", "Unknown Position")
    company = job.get("company", "Unknown Company")
    job_description = job.get("description", "")[:2000]  # cap token usage

    prompt = (
        "You are an expert career coach and resume writer. "
        "Tailor the candidate's application for the job below.\n\n"
        f"Candidate Summary:\n{candidate_summary}\n\n"
        f"Candidate Skills: {candidate_skills}\n\n"
        f"Target Job Title: {job_title}\n"
        f"Company: {company}\n"
        f"Job Description:\n{job_description}\n\n"
        "Produce:\n"
        "1. tailored_resume_summary — 2-3 sentence ATS-optimised summary that highlights "
        "the most relevant parts of the candidate's background for THIS specific role.\n"
        "2. tailored_cover_letter — A complete, professional cover letter (3-4 paragraphs) "
        "personalised for this company and role.\n"
        "3. missing_skills — A list of skills/requirements mentioned in the job description "
        "that the candidate does NOT currently have.\n"
        "4. match_score — An integer from 0 to 100 representing how well the candidate "
        "fits this role (100 = perfect match)."
    )

    result: ApplicationTailoringResult = structured_llm.invoke(prompt)
    result_dict = result.model_dump()
    result_dict["job_title"] = job_title
    result_dict["company"] = company
    result_dict["relevance_score"] = job.get("relevance_score", 50)
    return result_dict


def tailor_application_node(state: AgentState) -> dict:
    """
    Agent 3: Tailor resume and generate cover letter for top N discovered jobs.

    Input  state keys: extracted_profile, found_jobs
    Output state keys: tailoring_results  |  error
    """
    logger.info("[Resume Agent] Starting tailoring for user %s", state.get("user_id"))

    extracted_profile: dict = state.get("extracted_profile") or {}
    found_jobs: list = state.get("found_jobs") or []

    if not extracted_profile:
        logger.error("[Resume Agent] Missing extracted profile.")
        return {
            "current_step": "resume_agent",
            "error": "Missing extracted profile — cannot tailor application.",
        }

    if not found_jobs:
        logger.warning("[Resume Agent] No jobs to tailor for.")
        return {"current_step": "resume_agent", "tailoring_results": []}

    if not settings.GEMINI_API_KEY:
        return {
            "current_step": "resume_agent",
            "error": "GEMINI_API_KEY is not configured.",
        }

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.4,
        google_api_key=settings.GEMINI_API_KEY,
    )

    # Process top N jobs (sorted by relevance_score from Discovery Agent)
    jobs_to_process = found_jobs[: settings.MAX_JOBS_TO_TAILOR]
    logger.info(
        "[Resume Agent] Tailoring for %d jobs (max configured: %d).",
        len(jobs_to_process),
        settings.MAX_JOBS_TO_TAILOR,
    )

    tailoring_results: list[dict] = []
    for i, job in enumerate(jobs_to_process):
        job_label = f"{job.get('title', '?')} @ {job.get('company', '?')}"
        try:
            logger.info("[Resume Agent] Processing job %d/%d: %s", i + 1, len(jobs_to_process), job_label)
            result = _tailor_for_job(extracted_profile, job, llm)
            tailoring_results.append(result)
        except Exception as exc:
            logger.exception("[Resume Agent] Failed to tailor for %s: %s", job_label, exc)
            # Append a partial failure entry rather than stopping the whole pipeline
            tailoring_results.append(
                {
                    "job_title": job.get("title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "error": str(exc),
                }
            )

    logger.info("[Resume Agent] Tailoring complete — %d results.", len(tailoring_results))
    return {"current_step": "resume_agent", "tailoring_results": tailoring_results}
