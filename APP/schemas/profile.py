from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ─── Resume extraction schemas (used by Profile Agent) ───────────────────────

class Experience(BaseModel):
    company: str
    role: str
    duration: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_year: Optional[str] = None


class ProfileExtraction(BaseModel):
    """Structured output from the Profile Agent (LLM structured extraction)."""
    skills: List[str] = Field(description="Technical and soft skills extracted from the resume.")
    experience: List[Experience] = Field(description="Past work experiences.")
    education: List[Education] = Field(description="Educational background.")
    summary: str = Field(description="AI-generated summary of the candidate's profile.")
    job_title: Optional[str] = Field(
        default=None,
        description="Most recent or target job title inferred from the resume.",
    )


# ─── User preferences schemas (used by profile API routes) ───────────────────

class UserPreferencesUpdate(BaseModel):
    """Request body for PUT /api/v1/profile/preferences."""
    preferred_roles: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    preferred_companies: Optional[List[str]] = None
    job_type: Optional[str] = None          # full-time | part-time | remote | internship
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    interests: Optional[str] = None
    goal: Optional[str] = None


class UserPreferencesRead(BaseModel):
    """Response body for GET /api/v1/profile."""
    preferred_roles: List[str] = []
    preferred_locations: List[str] = []
    preferred_companies: List[str] = []
    job_type: str = "full-time"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    interests: Optional[str] = None
    goal: Optional[str] = None
    autonomous_mode: bool = False
    pipeline_status: str = "idle"
    last_pipeline_run_at: Optional[datetime] = None
    gmail_connected: bool = False

    model_config = {"from_attributes": True}


# ─── Autonomous mode schemas ──────────────────────────────────────────────────

class AutonomousModeUpdate(BaseModel):
    """Request body for POST /api/v1/profile/autonomous-mode."""
    enabled: bool


class PipelineStatusRead(BaseModel):
    """Response body for GET /api/v1/profile/pipeline-status."""
    autonomous_mode: bool
    pipeline_status: str          # idle | running | error | done
    last_pipeline_run_at: Optional[datetime] = None
    gmail_connected: bool

    model_config = {"from_attributes": True}
