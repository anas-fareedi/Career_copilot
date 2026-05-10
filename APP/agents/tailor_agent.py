from langchain_google_genai import ChatGoogleGenerativeAI
from APP.agents.state import AgentState
from APP.core.config import settings


def tailor_application_node(state: AgentState) -> dict:
    """
    Agent 3: Tailors the resume and generates a cover letter snippet for the top job.
    Only processes the first job to minimise token usage.
    """
    print("--- AGENT 3: TAILORING APPLICATION ---")
    extracted_profile: dict = state.get("extracted_profile") or {}
    found_jobs: list = state.get("found_jobs") or []

    if not extracted_profile:
        print("ERROR: No extracted profile found.")
        return {"error": "Missing extracted profile — cannot tailor application."}
    if not found_jobs:
        print("ERROR: No jobs found.")
        return {"error": "No jobs found — cannot tailor application."}

    try:
        # Only process the first job to save tokens
        job: dict = found_jobs[0]
        print(f"Job keys available: {job.keys()}")
        
        candidate_skills = ", ".join(extracted_profile.get("skills", []))
        job_title = job.get('title', 'Unknown Position')
        company = job.get('company_name', 'Unknown Company')
        
        print(f"Creating prompt for: {job_title} at {company}")

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.7,
            google_api_key=settings.GEMINI_API_KEY,
        )

        # Build a comprehensive prompt
        prompt = (
            "You are an expert career coach. Create a brief tailoring for this job match.\n\n"
            f"Candidate Skills: {candidate_skills}\n"
            f"Job Title: {job_title}\n"
            f"Company: {company}\n\n"
            "Respond with EXACTLY this format (one line per field):\n"
            "TAILORED_SUMMARY: Brief 1-2 sentence summary\n"
            "MISSING_SKILLS: skill1, skill2, skill3\n"
            "MATCH_SCORE: 75\n"
            "COVER_LETTER: Brief cover letter opening"
        )

        print("Calling LLM...")
        response = llm.invoke(prompt)
        response_text = response.content
        print(f"LLM Response:\n{response_text}")

        # Parse the response with better error handling
        result = {
            "tailored_resume_summary": "Tailored resume summary pending",
            "missing_skills": ["Leadership", "Data Analysis"],
            "match_score": 75,
            "cover_letter_snippet": "I am excited about this opportunity",
        }

        # Try to parse if response has the expected format
        lines = response_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("TAILORED_SUMMARY:"):
                result["tailored_resume_summary"] = line.replace("TAILORED_SUMMARY:", "").strip()
            elif line.startswith("MISSING_SKILLS:"):
                skills_str = line.replace("MISSING_SKILLS:", "").strip()
                result["missing_skills"] = [s.strip() for s in skills_str.split(",") if s.strip()]
            elif line.startswith("MATCH_SCORE:"):
                try:
                    score_str = line.replace("MATCH_SCORE:", "").strip().split()[0]
                    result["match_score"] = max(0, min(100, int(score_str)))
                except (ValueError, IndexError, TypeError):
                    result["match_score"] = 75
            elif line.startswith("COVER_LETTER:"):
                result["cover_letter_snippet"] = line.replace("COVER_LETTER:", "").strip()

        print(f"Parsed result: {result}")
        return {"tailoring_results": [result]}

    except Exception as e:
        print(f"EXCEPTION in tailor_application_node: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Tailoring failed: {str(e)}"}
