from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Document Extraction API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.7-flash"
    GEMINI_TIMEOUT_S: int = 90
    # USD per 1M tokens for cost estimates. 0 disables (prices change, set them in .env).
    PRICE_INPUT_PER_MTOK: float = 0.0
    PRICE_OUTPUT_PER_MTOK: float = 0.0

    # Upload limits: reject early, before spending a model call on a bad file.
    MAX_UPLOAD_MB: int = 10
    MAX_PDF_PAGES: int = 20

    # Abuse protection for a public demo.
    RATE_LIMIT_EXTRACTIONS: int = 10
    RATE_LIMIT_WINDOW_S: int = 600
    MAX_CONCURRENT_EXTRACTIONS: int = 3

    CORS_ORIGINS: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
