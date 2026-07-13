"""
Job and application Pydantic schemas.

Used by the job discovery API routes and application tracking API routes.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from APP.models.jobs import ApplicationStatus


# ─── Discovered Job schemas ───────────────────────────────────────────────────

class JobRead(BaseModel):
    """A discovered job posting returned from the API."""
    id: int
    title: str
    company: str
    description: Optional[str] = None
    location: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    relevance_score: Optional[int] = None
    discovered_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    total: int
    jobs: List[JobRead]


# ─── Application schemas ──────────────────────────────────────────────────────

class ApplicationRead(BaseModel):
    """Full application detail returned from the API."""
    id: int
    job_id: Optional[int] = None
    tailored_resume: Optional[str] = None
    tailored_cover_letter: Optional[str] = None
    tailored_summary: Optional[str] = None
    match_score: Optional[int] = None
    missing_skills: Optional[List[str]] = None
    status: ApplicationStatus
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    """Request body for manually updating an application's status."""
    status: ApplicationStatus
    notes: Optional[str] = None


# ─── Tailoring result (from Resume Agent) ────────────────────────────────────

class ApplicationTailoringResult(BaseModel):
    """
    The structured output produced by the Resume Agent for one job.
    Stored in Application.tailored_* columns and returned in API responses.
    """
    tailored_resume_summary: str
    tailored_cover_letter: str
    missing_skills: List[str]
    match_score: int = Field(description="Candidate-to-job match score (0–100).")

    @field_validator("match_score")
    @classmethod
    def clamp_match_score(cls, v: int) -> int:
        return max(0, min(100, v))


# ─── Dashboard analytics ─────────────────────────────────────────────────────

class ApplicationStats(BaseModel):
    """Aggregated counts by status for the dashboard."""
    total: int
    discovered: int
    tailored: int
    submitted: int
    interviewing: int
    rejected: int
    offered: int
