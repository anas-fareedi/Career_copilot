from pydantic import BaseModel, Field, field_validator
from typing import List


class MockJob(BaseModel):
    title: str
    company: str
    description: str
    required_skills: List[str]


class ApplicationTailoringResult(BaseModel):
    tailored_resume_summary: str
    missing_skills: List[str]
    match_score: int = Field(description="Match score between candidate and job, from 0 to 100.")
    cover_letter_snippet: str

    @field_validator("match_score")
    @classmethod
    def clamp_match_score(cls, v: int) -> int:
        """Clamp the match score to a valid 0–100 range regardless of what the LLM returns."""
        return max(0, min(100, v))
