import os
from serpapi import GoogleSearch
from APP.agents.state import AgentState
from APP.core.config import settings

def find_opportunities_node(state: AgentState) -> dict:
    """
    Agent 2: Real opportunity finder.
    Searches for jobs online using SerpApi based on the extracted profile.
    """
    print("--- AGENT 2: FINDING REAL OPPORTUNITIES ---")
    extracted_profile = state.get("extracted_profile")
    
    print(f"Extracted profile: {extracted_profile}")

    if not extracted_profile:
        print("ERROR: No extracted profile found")
        return {"error": "No extracted profile found. Cannot search for jobs."}

    # Ensure the API key is set
    if not settings.SERPAPI_API_KEY or settings.SERPAPI_API_KEY == "your_serpapi_api_key_here":
        print("ERROR: SERPAPI_API_KEY not configured")
        return {"error": "SERPAPI_API_KEY not configured in APP/core/config.py."}

    skills = extracted_profile.get("skills", [])
    job_title = extracted_profile.get("job_title", "Software Developer") # Default search
    query = f"{job_title} with skills in {', '.join(skills)}" if skills else job_title
    
    print(f"Search query: {query}")
    print(f"SerpApi key present: {bool(settings.SERPAPI_API_KEY)}")

    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
    }

    try:
        print("Calling SerpApi...")
        search = GoogleSearch(params)
        results = search.get_dict()
        
        print(f"SerpApi response keys: {results.keys()}")
        
        jobs_results = results.get("jobs_results", [])
        
        print(f"Jobs found: {len(jobs_results)}")
        if jobs_results:
            print(f"First job: {jobs_results[0]}")

        if not jobs_results:
            print("No jobs found in results")
            return {"found_jobs": []}

        # Limit to 5 jobs to keep it manageable
        result_jobs = jobs_results[:5]
        print(f"Returning {len(result_jobs)} jobs")
        return {"found_jobs": result_jobs}

    except Exception as e:
        print(f"Error searching for jobs: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Failed to fetch job opportunities: {e}"}

