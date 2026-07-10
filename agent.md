# Career Copilot — Autonomous AI Career Agent

## Vision

Career Copilot is an AI-powered SaaS platform that autonomously discovers relevant job opportunities, tailors application materials, submits applications, and tracks the user's job search with minimal manual effort.

The goal is to act as a **24/7 AI career agent**, not just a chatbot.

---

# Core Features (MVP)

### User Onboarding

* User authentication
* Resume upload
* Skills, experience, education, interests
* Preferred roles, locations, companies, salary
* Connect Gmail (OAuth)

### Job Discovery

* Monitor supported job portals
* Monitor Gmail for new opportunities
* Filter jobs based on user preferences
* Rank jobs using AI relevance scoring

### AI Resume & Cover Letter

* Analyze job descriptions
* Generate ATS-optimized resume versions
* Generate personalized cover letters
* Maintain resume version history

### Autonomous Job Application

* Automatically fill application forms
* Upload tailored resume & cover letter
* Submit applications using browser automation
* Retry failed applications when possible

### Application Tracking

* Track application status
* Store application history
* Notify users of important updates
* Dashboard with analytics

---

# AI Agent Architecture

## Supervisor Agent

Coordinates the complete workflow and delegates tasks.

## Job Discovery Agent

Finds and filters new job opportunities.

## Resume Agent

Optimizes resumes and generates cover letters.

## Apply Agent

Handles browser automation and job submissions.

## Notification Agent

Sends application updates and alerts.

---

# High-Level Workflow

User Setup

↓

AI Monitors Jobs & Gmail

↓

Relevant Job Found

↓

Analyze Job Description

↓

Tailor Resume

↓

Generate Cover Letter

↓

Auto-fill Application

↓

Submit Application

↓

Track Status

↓

Notify User

---

# Scalable Architecture

* Frontend (Next.js)
* FastAPI Backend
* LangGraph Agent Layer
* Background Worker Queue
* Browser Automation Workers
* PostgreSQL Database
* Redis Queue
* Notification Service

Each service should remain modular to support future scaling.

---

# Tech Stack

## Frontend

* Next.js
* TypeScript
* Tailwind CSS

## Backend

* FastAPI
* Python

## AI

* LangGraph (Agent orchestration)
* LangChain (LLM framework)
* OpenAI / Gemini / Claude (pluggable)

## Browser Automation

* Playwright

## Database & Authentication

* PostgreSQL (Supabase)
* Supabase Auth

## Background Processing

* Redis
* Celery / ARQ / Dramatiq (TBD)

## CI/CD

* GitHub Actions

## Observability

* LangSmith

## Deployment

* Docker

---

# Future Roadmap

* Multi-job portal connectors
* AI interview preparation
* Application analytics dashboard
* Calendar integration
* Team & recruiter dashboards
* Subscription plans
* Kubernetes deployment
* Prometheus + Grafana monitoring
* Optional Knowledge Service (RAG using LlamaIndex + Vector Database)

---

# Design Principles

* Modular service architecture
* Agent-first workflow
* Human-in-the-loop for configurable actions
* Scalable SaaS architecture
* Provider-agnostic LLM support
* Production-ready from day one
* RAG remains an optional future enhancement, not a dependency for the MVP
