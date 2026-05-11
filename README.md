# Career_copilot
Multi-agent system for automation to applying jobs and internship s completely

## pending
-One deployed demo (or 60s screencast) reachable from README..
-3 prepared project pitches (30s, 2min, 5min versions).
-Advanced scaling/infra — fix by documenting tradeoffs and showing a simple cost/latency estimate for your deployed app.

# AI Career Copilot — Master Project Prompt

Build an AI-powered multi-agent career copilot platform that helps students discover internships/jobs, tailor applications, automate repetitive workflows, and track progress throughout the hiring journey.

The system should act like an autonomous AI placement assistant that continuously works on behalf of the user.

---

# Core Product Vision

The platform should:

* understand a student profile deeply,
* analyze resumes and credentials,
* discover relevant internships/jobs,
* tailor resumes and cover letters,
* automate application workflows,
* track application progress,
* and continuously improve recommendations using AI agents.

The product is intended as an MVP for a hackathon and should prioritize strong backend architecture and intelligent workflows over frontend complexity.

---

# UI Requirement

For MVP:

* Use Streamlit or Gradio for a simple input-output interface.
* No advanced frontend framework is required initially.
* Focus on functionality, workflows, and agent orchestration.

The UI should allow:

* resume upload,
* user profile input,
* job search initiation,
* viewing recommendations,
* viewing generated resumes/cover letters,
* tracking application progress,
* and displaying notes/todos/insights.

---

# System Architecture

Build the project using a modular multi-agent architecture.

---

# Agent 1 — Profile Intelligence Agent

Responsibilities:

* Analyze uploaded resumes and user profile data.
* Extract skills, projects, education, certifications, interests, and experience.
* Create and maintain a dynamic structured user profile.
* Store/update profile insights in the database.
* Generate embeddings for semantic matching.

Inputs:

* Resume PDF
* User information
* GitHub
* LinkedIn
* Portfolio links
* Skills and preferences

Outputs:

* Structured profile
* Skill embeddings
* Career insights
* Missing skill analysis

---

# Agent 2 — Opportunity Finder Agent

Responsibilities:

* Fetch user profile from database.
* Search internships/jobs from multiple platforms.
* Match opportunities using semantic similarity.
* Rank opportunities by:

  * skill match,
  * ATS compatibility,
  * eligibility,
  * role alignment,
  * and selection probability.
* Store opportunities in database.
* Update application statuses.

Features:

* Semantic search
* Match scoring
* Skill gap analysis
* Recommendation engine

Outputs:

* Ranked internships/jobs
* Match percentage
* Eligibility insights

---

# Agent 3 — Resume & Cover Letter Tailoring Agent

Responsibilities:

* Read job descriptions.
* Generate tailored ATS-optimized resumes.
* Generate personalized cover letters.
* Create multiple resume versions for different roles.
* Store generated documents in database.

Features:

* Keyword optimization
* Role-specific tailoring
* ATS optimization
* Company-specific cover letters

Outputs:

* Tailored resume
* Tailored cover letter
* Resume match score

---

# Agent 4 — Workflow Orchestrator & Progress Analyzer

Responsibilities:

* Coordinate all agents.
* Monitor workflow execution.
* Track progress and status.
* Collect insights from all agents.
* Generate notes/todos/tasks automatically.
* Maintain workflow state and history.

Features:

* Multi-agent communication
* Workflow orchestration
* Progress analytics
* Gap analysis
* Notes and reminders

Example outputs:

* “User lacks Docker experience.”
* “Resume match improved by 14%.”
* “3 applications pending review.”

---

# Agent 5 — Auto Apply & Form Filling Agent

Responsibilities:

* Automate repetitive application tasks.
* Fill application forms automatically.
* Upload tailored resumes and cover letters.
* Store application status updates.
* Support semi-automated submission approval.

Features:

* Browser automation
* Form autofill
* Resume upload
* Workflow tracking

---

# Agent 6 — Interview Preparation Agent (Optional)

Responsibilities:

* Generate interview questions.
* Create mock interview sessions.
* Suggest weak areas.
* Prepare role-specific interview material.

Features:

* Resume-based interview prep
* Behavioral questions
* Technical preparation
* Learning roadmap suggestions

---

# Shared Workflow Notes System

The platform should maintain a persistent notes/todo system that stores:

* pending tasks,
* reminders,
* application notes,
* workflow insights,
* missing skills,
* and progress observations.

This notes system should be accessible across agents.

---

# Recommended Tech Stack

Frontend/UI:

* Streamlit or Gradio

Backend:

* FastAPI

AI Agent Framework:

* LangGraph
* LangChain

LLM:

* Gemini API

Database:

* PostgreSQL

Vector Search:

* pgvector

Browser Automation:

* Playwright
* AgentQL

Workflow Automation:

* n8n (optional)

Deployment:

* Railway / Render
* Supabase / Neon for PostgreSQL

---

# Database Design

Create tables/models for:

* users
* user_profiles
* resumes
* jobs
* applications
* cover_letters
* workflow_notes
* agent_logs
* interview_preparation

Use PostgreSQL with:

* relational schema,
* JSONB support,
* and vector embeddings using pgvector.

---

# Workflow

1. User uploads resume and profile.
2. Agent 1 analyzes and stores profile data.
3. Agent 2 searches and ranks opportunities.
4. Agent 3 tailors resumes and cover letters.
5. Agent 4 orchestrates workflows and generates insights.
6. Agent 5 automates applications and form filling.
7. Optional Agent 6 prepares interview workflows.

---

# Product Goals

The system should:

* reduce manual internship search effort,
* increase application quality,
* improve match accuracy,
* automate repetitive workflows,
* and act as a persistent AI-powered career assistant.

---

# Development Priorities

Prioritize:

1. Backend architecture
2. Agent orchestration
3. Database design
4. Workflow automation
5. AI reasoning quality
6. Functional MVP UI

Do not prioritize:

* complex frontend design,
* animations,
* or unnecessary UI complexity.

---

# Final Product Positioning

“An AI-powered autonomous career copilot that helps students discover opportunities, optimize applications, automate workflows, and improve hiring success through intelligent multi-agent collaboration.”
