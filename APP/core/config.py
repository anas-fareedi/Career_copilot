from pydantic_settings import BaseSettings
from pydantic import computed_field


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Career Copilot"
    API_V1_STR: str = "/api/v1"

    # Database — pydantic-settings reads these from .env automatically
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "career_copilot"

    # Gemini API — field name must match the env var key (case-insensitive by default)
    GEMINI_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )

    model_config = {
        "case_sensitive": False,
        "env_file": ".env",
        "extra": "ignore",  # ignore unknown env vars in .env safely
    }


settings = Settings()
