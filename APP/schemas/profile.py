from pydantic import BaseModel, Field
from typing import List, Optional

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
    """The structured output from Agent 1 (Profile Intelligence)"""
    skills: List[str] = Field(description="A list of technical and soft skills extracted from the resume.")
    experience: List[Experience] = Field(description="List of past work experiences.")
    education: List[Education] = Field(description="Educational background.")
    summary: str = Field(description="A brief AI-generated summary of the candidate's profile.")
