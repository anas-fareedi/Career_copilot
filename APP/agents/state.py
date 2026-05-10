from typing import TypedDict, Optional, List


class AgentState(TypedDict):
    """
    The state of the career copilot workflow.
    Uses plain Python types so LangGraph can serialize/deserialize cleanly.
    """
    # Resume content extracted from the uploaded PDF
    raw_resume: str

    # User-supplied preferences from the form
    interests: str        # e.g. "AI, machine learning, backend"
    goal: str             # e.g. "Land a software engineering role at a product company"
    job_type: str         # e.g. "internship", "full-time", "part-time", "remote"
    job_category: str     # e.g. "Software Engineering", "Data Science", "Product Management"

    # Agent outputs — stored as plain dicts for LangGraph serialization
    extracted_profile: Optional[dict]
    found_jobs: Optional[List[dict]]
    tailoring_results: Optional[List[dict]]

    # A non-None value means the pipeline was halted due to an error
    error: Optional[str]
