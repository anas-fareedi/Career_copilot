from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Career Copilot"
    API_V1_STR: str = "/api/v1"

    # ─── Database ────────────────────────────────────────────────────────────
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "career_copilot"
    POSTGRES_PORT: int = 5432

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        # Prefer SUPABASE_DB_URL if provided (Supabase hosted PostgreSQL)
        if self.SUPABASE_DB_URL:
            return self.SUPABASE_DB_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ─── Supabase ─────────────────────────────────────────────────────────────
    # Found in: Supabase Dashboard → Settings → API → JWT Secret
    SUPABASE_JWT_SECRET: str = ""
    # Found in: Supabase Dashboard → Settings → API → service_role key (secret)
    SUPABASE_SERVICE_KEY: str = ""
    # Found in: Supabase Dashboard → Settings → API → anon key (public)
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_URL: str = ""

    # Optional: Supabase PostgreSQL connection string (overrides POSTGRES_* settings).
    # Found in: Supabase Dashboard → Settings → Database → Connection string → URI
    # Format: postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    SUPABASE_DB_URL: str = ""

    # ─── AI / LLM ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""  # optional — pluggable LLM support

    # ─── Google OAuth / Gmail ─────────────────────────────────────────────────
    # Found in: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Must match exactly what's registered in Google Cloud Console
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/gmail/callback"

    # ─── Job Discovery ────────────────────────────────────────────────────────
    SERPAPI_API_KEY: str = ""
    MAX_JOBS_TO_DISCOVER: int = 10   # max raw results from SerpAPI
    MAX_JOBS_TO_TAILOR: int = 5      # max jobs the Resume Agent will process

    # ─── Application Workflow ─────────────────────────────────────────────────
    # Set to True to let Apply Agent auto-submit without human confirmation
    AUTO_APPLY: bool = False

    # ─── Redis / Celery ───────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    @computed_field  # type: ignore[misc]
    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @computed_field  # type: ignore[misc]
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @computed_field  # type: ignore[misc]
    @property
    def CORS_ORIGINS(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {
        "case_sensitive": False,
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
