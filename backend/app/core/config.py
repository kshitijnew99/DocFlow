from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://docflow:docflow_secret@localhost:5432/docflow_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # App
    SECRET_KEY: str = "dev-secret-key"
    ENVIRONMENT: str = "development"
    AUTO_CREATE_TABLES: bool = True
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".txt", ".pdf", ".csv", ".json", ".md", ".xml"]
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:3001,"
        "http://127.0.0.1:3001"
    )

    # SSE / Pub-Sub
    REDIS_PUBSUB_CHANNEL_PREFIX: str = "docflow:job:"

    # Keyword Extraction
    KEYWORD_EXTRACTOR: str = "yake"  # auto | keybert | yake | frequency
    KEYWORD_TOP_N: int = 10
    KEYWORD_NGRAM_MIN: int = 1
    KEYWORD_NGRAM_MAX: int = 2
    KEYBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
