from langchain_google_genai import ChatGoogleGenerativeAI
from APP.agents.state import AgentState
from APP.schemas.profile import ProfileExtraction
from APP.core.config import settings


def extract_profile_node(state: AgentState) -> dict:
    """
    Agent 1: Reads raw resume and extracts a structured profile using Gemini.
    Returns the profile as a plain dict for LangGraph state serialization.
    """
    print("--- AGENT 1: EXTRACTING PROFILE ---")
    raw_resume = state.get("raw_resume", "")

    if not raw_resume or not raw_resume.strip():
        return {"error": "No raw resume provided."}

    if not settings.GEMINI_API_KEY:
        return {"error": "GEMINI_API_KEY is not configured. Please set it in your .env file."}

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=settings.GEMINI_API_KEY,
    )
    structured_llm = llm.with_structured_output(ProfileExtraction)

    prompt = (
        "Analyze the following resume and extract the requested fields accurately.\n\n"
        f"Resume:\n{raw_resume}"
    )

    try:
        extracted: ProfileExtraction = structured_llm.invoke(prompt)
        # Convert to plain dict so LangGraph state remains serializable
        return {"extracted_profile": extracted.model_dump()}
    except Exception as e:
        return {"error": f"Profile extraction failed: {e}"}
