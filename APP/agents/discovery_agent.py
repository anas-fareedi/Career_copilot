"""
Discovery Agent — Agent 2 in the Career Copilot pipeline.

Responsibilities:
  1. Search for relevant jobs via SerpAPI (Google Jobs engine).
  2. Score each job's relevance using Gemini (0–100).
  3. Return a list of enriched job dicts sorted by relevance score.

Gmail monitoring is stubbed — placeholder is included for future implementation.
"""

import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from APP.agents.state import AgentState
from APP.core.config import settings
from APP.services.job_search import search_jobs

logger = logging.getLogger(__name__)


def _score_jobs_with_ai(
    jobs: list[dict[str, Any]],
    profile: dict,
    preferences: dict,
    llm: ChatGoogleGenerativeAI,
) -> list[dict[str, Any]]:
    """
    Use the LLM to score each job's relevance to the candidate's profile
    and preferences. Returns the same list with `relevance_score` populated.

    We score in a single batch prompt to minimise token round-trips.
    """
    if not jobs:
        return jobs

    candidate_summary = (
        f"Candidate summary: {profile.get('summary', 'N/A')}\n"
        f"Skills: {', '.join(profile.get('skills', []))}\n"
        f"Target roles: {', '.join(preferences.get('preferred_roles', []))}\n"
        f"Job type: {preferences.get('job_type', 'full-time')}\n"
        f"Goal: {preferences.get('goal', 'N/A')}"
    )

    jobs_text = "\n".join(
        f"Job {i + 1}: {job.get('title')} at {job.get('company')} — {job.get('description', '')[:300]}"
        for i, job in enumerate(jobs)
    )

    prompt = (
        "You are an expert career advisor. Score each job listing's relevance to the "
        "candidate on a scale from 0 to 100 (100 = perfect match).\n\n"
        f"{candidate_summary}\n\n"
        f"Job listings:\n{jobs_text}\n\n"
        "Respond with ONLY a comma-separated list of integer scores in the same order as the jobs. "
        "Example: 85,72,60,45,90"
    )

    try:
        response = llm.invoke(prompt)
        raw_scores = response.content.strip().split(",")
        scores = [max(0, min(100, int(s.strip()))) for s in raw_scores if s.strip().isdigit()]

        for i, job in enumerate(jobs):
            job["relevance_score"] = scores[i] if i < len(scores) else 50

        logger.info(
            "[Discovery Agent] Scored %d jobs. Top score: %d",
            len(jobs),
            max((j.get("relevance_score", 0) for j in jobs), default=0),
        )
    except Exception as exc:
        logger.warning("[Discovery Agent] AI scoring failed (%s) — assigning default scores.", exc)
        for job in jobs:
            job["relevance_score"] = 50

    return sorted(jobs, key=lambda j: j.get("relevance_score", 0), reverse=True)


def _scan_gmail(user_id: str, preferences: dict, llm) -> list[dict[str, Any]]:
    """
    Scan the user's Gmail inbox for job-related emails using the stored OAuth token.
    Returns a list of normalised job dicts (same format as SerpAPI results).
    Falls back to an empty list on any error so discovery continues regardless.
    """
    gmail_token: dict | None = preferences.get("gmail_token")
    if not gmail_token:
        logger.info("[Discovery Agent] No Gmail token for user %s — skipping inbox scan.", user_id)
        return []

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning("[Discovery Agent] google-api-python-client not installed — skipping Gmail scan.")
        return []

    try:
        creds = Credentials(
            token=gmail_token.get("token"),
            refresh_token=gmail_token.get("refresh_token"),
            token_uri=gmail_token.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=gmail_token.get("client_id"),
            client_secret=gmail_token.get("client_secret"),
            scopes=gmail_token.get("scopes"),
        )

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        # Search for job-related emails in the last 30 days
        query = (
            "(subject:\"job opportunity\" OR subject:\"we found a job\" "
            "OR subject:\"job alert\" OR subject:\"hiring\" OR subject:\"internship\""
            "OR subject:\"application received\" OR subject:\"interview\") "
            "newer_than:30d"
        )
        result = service.users().messages().list(
            userId="me", q=query, maxResults=10
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            logger.info("[Discovery Agent] No job emails found for user %s.", user_id)
            return []

        # Extract subject + snippet from each matching email
        email_summaries = []
        for msg in messages[:10]:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")
            sender = headers.get("From", "")
            snippet = msg_data.get("snippet", "")
            email_summaries.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}")

        logger.info("[Discovery Agent] Found %d job emails for user %s.", len(email_summaries), user_id)

        # Use LLM to extract structured job info from emails
        emails_text = "\n\n---\n".join(email_summaries)
        prompt = (
            "You are an expert at extracting job opportunity information from emails.\n"
            "Below are email summaries. For each that describes a real job or internship opportunity, "
            "extract the job details.\n\n"
            f"{emails_text}\n\n"
            "Respond with ONLY valid JSON: a list of objects, each with keys: "
            "title, company, location, description, source_url. "
            "Use empty string for unknown fields. If no jobs found, return [].\n"
            "Example: [{\"title\": \"SDE Intern\", \"company\": \"Google\", "
            "\"location\": \"Remote\", \"description\": \"...\", \"source_url\": \"\"}]"
        )

        response = llm.invoke(prompt)
        raw = response.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        import json
        jobs_from_gmail = json.loads(raw)
        for job in jobs_from_gmail:
            job["source"] = "gmail"

        logger.info("[Discovery Agent] Extracted %d jobs from Gmail for user %s.", len(jobs_from_gmail), user_id)
        return jobs_from_gmail

    except Exception as exc:
        logger.warning("[Discovery Agent] Gmail scan failed for user %s: %s — continuing without Gmail.", user_id, exc)
        return []


def find_opportunities_node(state: AgentState) -> dict:
    """
    Agent 2: Discover and score relevant job opportunities.

    Input  state keys: extracted_profile, user_preferences, user_id
    Output state keys: found_jobs  |  error

    Sources:
      1. SerpAPI (Google Jobs) — always active
      2. Gmail inbox scan — only if user has connected Gmail (gmail_token in preferences)
    """
    logger.info("[Discovery Agent] Starting job discovery for user %s", state.get("user_id"))

    extracted_profile: dict = state.get("extracted_profile") or {}
    user_preferences: dict = state.get("user_preferences") or {}
    user_id: str = state.get("user_id", "")

    if not extracted_profile:
        logger.error("[Discovery Agent] No extracted profile in state.")
        return {
            "current_step": "discovery_agent",
            "error": "No extracted profile found. Cannot search for jobs.",
        }

    # ── Build LLM (shared across scoring + Gmail extraction) ──────────────────
    llm = None
    if settings.GEMINI_API_KEY:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY,
        )
    else:
        logger.warning("[Discovery Agent] GEMINI_API_KEY not set — AI scoring and Gmail extraction disabled.")

    # ── 1. Search via SerpAPI ─────────────────────────────────────────────────
    raw_jobs = search_jobs(
        job_title=extracted_profile.get("job_title"),
        skills=extracted_profile.get("skills", []),
        preferences=user_preferences,
        max_results=settings.MAX_JOBS_TO_DISCOVER,
    )

    # ── 2. Scan Gmail inbox (real implementation if token present) ────────────
    gmail_jobs = _scan_gmail(user_id, user_preferences, llm) if llm else []
    all_jobs = raw_jobs + gmail_jobs

    if not all_jobs:
        logger.warning("[Discovery Agent] No jobs found from any source.")
        return {"current_step": "discovery_agent", "found_jobs": []}

    # ── 3. AI relevance scoring ───────────────────────────────────────────────
    if llm:
        scored_jobs = _score_jobs_with_ai(all_jobs, extracted_profile, user_preferences, llm)
    else:
        scored_jobs = all_jobs

    logger.info("[Discovery Agent] Returning %d scored jobs (%d from SerpAPI, %d from Gmail).",
                len(scored_jobs), len(raw_jobs), len(gmail_jobs))
    return {"current_step": "discovery_agent", "found_jobs": scored_jobs}
