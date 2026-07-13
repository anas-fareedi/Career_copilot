"""
Job search service — wraps the SerpAPI Google Jobs engine.

Decoupled from the Discovery Agent so the HTTP call can be
mocked/replaced without touching the agent graph.
"""

import logging
from typing import Any, Optional

from serpapi import GoogleSearch

from APP.core.config import settings

logger = logging.getLogger(__name__)


def build_search_query(
    job_title: Optional[str],
    skills: list[str],
    preferences: dict,
) -> str:
    """
    Build a Google Jobs search query from the candidate's profile and preferences.

    Priority:
      1. Preferred roles from user preferences (most specific)
      2. Job title extracted from resume
      3. Fallback: "Software Developer"

    Note: Google Jobs doesn't support structured syntax like "skills: X, Y".
    We keep the query short and natural — just the role title plus 1–2
    top skills as plain keywords — so the search engine can match properly.
    """
    preferred_roles: list[str] = preferences.get("preferred_roles") or []
    target_title = preferred_roles[0] if preferred_roles else (job_title or "Software Developer")

    location_parts: list[str] = preferences.get("preferred_locations") or []
    location_str = " in " + location_parts[0] if location_parts else ""

    # Append at most 2 top skills as natural keywords (not "skills: ..." syntax)
    top_skills = [s for s in skills[:2] if s] if skills else []
    skills_str = " ".join(top_skills)

    query = target_title + location_str
    if skills_str:
        query += f" {skills_str}"

    logger.debug("Built job search query: %r", query)
    return query


def search_jobs(
    job_title: Optional[str],
    skills: list[str],
    preferences: dict,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Search Google Jobs via SerpAPI and return a normalised list of job dicts.

    Each result dict contains:
      title, company, description, location, source_url

    Returns an empty list (not an exception) if the API call fails,
    so the Discovery Agent can decide how to handle it.
    """
    if not settings.SERPAPI_API_KEY:
        logger.error("SERPAPI_API_KEY is not configured — cannot search jobs.")
        return []

    query = build_search_query(job_title, skills, preferences)
    logger.info("Searching Google Jobs with query: %r", query)

    params: dict[str, Any] = {
        "engine": "google_jobs",
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
        "num": max_results,
    }

    # Honour location preference in SerpAPI location field too
    preferred_locations: list[str] = preferences.get("preferred_locations") or []
    if preferred_locations:
        params["location"] = preferred_locations[0]

    try:
        search = GoogleSearch(params)
        raw = search.get_dict()
        jobs_results: list[dict] = raw.get("jobs_results", [])
        logger.info("SerpAPI returned %d raw job results.", len(jobs_results))

        normalised: list[dict[str, Any]] = []
        for job in jobs_results[:max_results]:
            normalised.append(
                {
                    "title": job.get("title", ""),
                    "company": job.get("company_name", ""),
                    "description": job.get("description", ""),
                    "location": job.get("location", ""),
                    "source": "google_jobs",
                    "source_url": job.get("related_links", [{}])[0].get("link", "")
                    if job.get("related_links")
                    else "",
                }
            )
        return normalised

    except Exception as exc:
        logger.exception("SerpAPI request failed: %s", exc)
        return []
