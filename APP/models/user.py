"""
User-related SQLAlchemy models.

User.id is the Supabase UUID (string) — not a locally auto-incremented integer.
This keeps the local DB in sync with Supabase Auth without a separate mapping table.
"""

from sqlalchemy import Boolean, Column, String, Text, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.sql import func

from APP.models.base import Base


class User(Base):
    """
    Mirrors a Supabase Auth user in the local PostgreSQL database.
    Created/updated on first authenticated API call (upsert in security.py).
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True)          # Supabase UUID
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserPreferences(Base):
    """
    Job search preferences set by the user during onboarding or in settings.
    One-to-one with User (enforced via unique FK).
    """
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Role & location preferences
    preferred_roles = Column(JSON, default=list)        # e.g. ["Software Engineer", "ML Engineer"]
    preferred_locations = Column(JSON, default=list)    # e.g. ["Remote", "New York"]
    preferred_companies = Column(JSON, default=list)    # e.g. ["Google", "Stripe"]
    job_type = Column(String, default="full-time")      # full-time | part-time | remote | internship

    # Salary range (optional)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)

    # Free-text fields used as context for the AI agents
    interests = Column(Text, nullable=True)   # e.g. "AI, distributed systems, open source"
    goal = Column(Text, nullable=True)        # e.g. "Land a senior SWE role at a product company"

    # Gmail OAuth token (encrypted JSON blob — stored for Gmail monitoring)
    gmail_token = Column(JSON, nullable=True)
    gmail_connected = Column(Boolean, default=False, nullable=False)

    # Autonomous mode — user opts in to background pipeline execution
    autonomous_mode = Column(Boolean, default=False, nullable=False)
    pipeline_status = Column(String, default="idle", nullable=False)  # idle | running | error | done
    last_pipeline_run_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
