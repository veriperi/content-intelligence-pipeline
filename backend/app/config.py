"""
Central config. All secrets come from environment variables — never hardcode
keys. Copy .env.example to .env and fill in your own values before running.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Postgres
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/content_pipeline",
    )

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Ingestion
    ITUNES_SEARCH_URL: str = "https://itunes.apple.com/search"
    REQUEST_TIMEOUT_SECONDS: int = 15
    MAX_EPISODES_PER_FEED: int = 25  # cap so a single feed can't blow up a run

    # Prompt version — bump this whenever you change the enrichment prompt.
    # Storing this alongside every LLM response lets you A/B or roll back
    # prompt changes without losing historical comparability.
    PROMPT_VERSION: str = "v1"


settings = Settings()
