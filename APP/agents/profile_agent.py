"""
Profile Agent — Agent 1 in the Career Copilot pipeline.

Reads raw resume text and extracts a structured candidate profile
using Gemini with structured output (schema-enforced JSON).
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from APP.agents.state import AgentState
from APP.core.config import settings
from APP.schemas.profile import ProfileExtraction

logger = logging.getLogger(__name__)


def extract_profile_node(state: AgentState) -> dict:
    """
    Agent 1: Extract structured profile from raw resume text.

    Input  state keys: raw_resume
    Output state keys: extracted_profile  |  error
    """
    logger.info("[Profile Agent] Starting profile extraction for user %s", state.get("user_id"))
    raw_resume = state.get("raw_resume", "")

    if not raw_resume or not raw_resume.strip():
        logger.error("[Profile Agent] No resume text provided.")
        return {"current_step": "profile_agent", "error": "No raw resume provided."}

    if not settings.GEMINI_API_KEY:
        logger.error("[Profile Agent] GEMINI_API_KEY not configured.")
        return {
            "current_step": "profile_agent",
            "error": "GEMINI_API_KEY is not configured. Please set it in your .env file.",
        }

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=settings.GEMINI_API_KEY,
    )
    structured_llm = llm.with_structured_output(ProfileExtraction)

    prompt = (
        "You are an expert HR analyst. Analyze the resume below and extract the "
        "requested fields accurately. Include all skills, every work experience entry, "
        "and all education records you can find.\n\n"
        f"Resume:\n{raw_resume}"
    )

    try:
        extracted: ProfileExtraction = structured_llm.invoke(prompt)
        profile_dict = extracted.model_dump()
        logger.info(
            "[Profile Agent] Extracted %d skills, %d experiences.",
            len(profile_dict.get("skills", [])),
            len(profile_dict.get("experience", [])),
        )
        return {"current_step": "profile_agent", "extracted_profile": profile_dict}
    except Exception as exc:
        logger.exception("[Profile Agent] Extraction failed: %s", exc)
        return {"current_step": "profile_agent", "error": f"Profile extraction failed: {exc}"}
