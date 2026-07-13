"""
LangGraph shared state for the Career Copilot agent pipeline.

All 5 agents read from and write to this state object.
The Supervisor Agent uses `current_step` to track progress
and `error` to halt the pipeline on failure.
"""

from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    """
    Shared state passed through the 5-agent LangGraph pipeline.

    Input keys are set before the graph is invoked.
    Output keys are populated by each agent node in sequence.
    """

    # ── Input (set before invoking the graph) ─────────────────────────────────
    user_id: str            # Supabase UUID of the authenticated user
    raw_resume: str         # Plain text extracted from uploaded PDF
    user_preferences: dict  # UserPreferences dict (roles, locations, job_type, etc.)

    # ── Profile Agent output ──────────────────────────────────────────────────
    extracted_profile: Optional[dict]   # ProfileExtraction.model_dump()

    # ── Discovery Agent output ────────────────────────────────────────────────
    found_jobs: Optional[List[dict]]    # Normalised job dicts, sorted by relevance_score

    # ── Resume Agent output ───────────────────────────────────────────────────
    tailoring_results: Optional[List[dict]]  # One ApplicationTailoringResult per job
    resume_versions: Optional[List[dict]]    # Stored ResumeVersion IDs (for audit trail)

    # ── Apply Agent output ────────────────────────────────────────────────────
    application_results: Optional[List[dict]]  # {job_id, status, message} per job

    # ── Notification Agent output ─────────────────────────────────────────────
    notifications_sent: Optional[List[str]]    # Summary strings of sent notifications

    # ── Pipeline control ──────────────────────────────────────────────────────
    current_step: str           # Name of the node currently executing
    error: Optional[str]        # Non-None → pipeline halted, downstream agents skipped
