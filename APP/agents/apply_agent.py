"""
Apply Agent — Agent 4 in the Career Copilot pipeline.

STATUS: STUBBED for MVP.

This agent is responsible for autonomously submitting job applications
using browser automation (Playwright). In stub mode it:
  - Logs what it *would* do for each application
  - Marks each application as "submitted" in the result list
  - Does NOT actually open a browser or submit any forms

Real implementation will use Playwright to:
  1. Navigate to the job's application URL
  2. Auto-fill application forms with tailored resume content
  3. Upload tailored resume PDF
  4. Submit the form and confirm receipt
  5. Retry on transient failures
"""

import logging

from APP.agents.state import AgentState
from APP.core.config import settings

logger = logging.getLogger(__name__)


def apply_jobs_node(state: AgentState) -> dict:
    """
    Agent 4: Submit job applications (STUBBED).

    Input  state keys: tailoring_results, found_jobs, user_id
    Output state keys: application_results
    """
    logger.info("[Apply Agent] Starting application submission for user %s", state.get("user_id"))

    tailoring_results: list[dict] = state.get("tailoring_results") or []
    found_jobs: list[dict] = state.get("found_jobs") or []

    if not tailoring_results:
        logger.warning("[Apply Agent] No tailoring results — nothing to apply for.")
        return {"current_step": "apply_agent", "application_results": []}

    # Build a quick lookup: company+title → source_url
    job_url_map: dict[str, str] = {
        f"{j.get('company', '')}|{j.get('title', '')}": j.get("source_url", "")
        for j in found_jobs
    }

    if not settings.AUTO_APPLY:
        logger.info(
            "[Apply Agent] AUTO_APPLY is disabled — dry-run mode. "
            "Set AUTO_APPLY=true in .env to enable real submissions."
        )

    application_results: list[dict] = []
    for tailored in tailoring_results:
        if tailored.get("error"):
            # Skip jobs where tailoring itself failed
            continue

        company = tailored.get("company", "Unknown Company")
        title = tailored.get("job_title", "Unknown Position")
        url = job_url_map.get(f"{company}|{title}", "")

        if settings.AUTO_APPLY:
            # ── Real implementation would go here ─────────────────────────────
            # from playwright.async_api import async_playwright
            # async with async_playwright() as p:
            #     browser = await p.chromium.launch(headless=True)
            #     page = await browser.new_page()
            #     await page.goto(url)
            #     ...fill form, upload resume, submit...
            # ─────────────────────────────────────────────────────────────────
            logger.warning(
                "[Apply Agent] AUTO_APPLY is enabled but real automation is not yet implemented. "
                "Marking as submitted (stub)."
            )
            status = "submitted_stub"
            message = f"[STUB] Would submit to: {url or 'URL not available'}"
        else:
            status = "pending_review"
            message = f"Dry-run: application ready for {title} at {company}. Enable AUTO_APPLY to submit."

        logger.info("[Apply Agent] %s — %s", title, message)
        application_results.append(
            {
                "job_title": title,
                "company": company,
                "source_url": url,
                "status": status,
                "message": message,
            }
        )

    logger.info("[Apply Agent] Processed %d applications.", len(application_results))
    return {"current_step": "apply_agent", "application_results": application_results}
