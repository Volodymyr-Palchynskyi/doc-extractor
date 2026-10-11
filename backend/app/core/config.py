from functools import lru_cache
from typing import Literal

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

    # "gemini" calls the model. "demo" replays recorded model output for the bundled sample documents only,
    # so the whole app (UI included) can be tried without an API key or quota. "auto" picks gemini when an
    # API key is set and demo otherwise, so a fresh clone works out of the box.
    EXTRACTOR: Literal["auto", "gemini", "demo"] = "auto"

    # Uploaded documents are kept in memory only, so the UI can show page images next to the fields.
    # They expire on their own and can be deleted by the user; nothing is written to disk.
    DOC_TTL_S: int = 900
    MAX_STORED_DOCS: int = 50
    MAX_STORED_MB: int = 200

    # Upload limits: reject early, before spending a model call on a bad file.
    MAX_UPLOAD_MB: int = 10
    MAX_PDF_PAGES: int = 20

    # Abuse protection for a public demo.
    RATE_LIMIT_EXTRACTIONS: int = 10
    RATE_LIMIT_WINDOW_S: int = 600
    MAX_CONCURRENT_EXTRACTIONS: int = 3
    RATE_LIMIT_PAGES: int = 600  # page image requests per client per window
    RATE_LIMIT_VALIDATIONS: int = 1200  # re-checks while a human edits fields

    CORS_ORIGINS: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]

    @property
    def extractor_mode(self) -> Literal["gemini", "demo"]:
        """The mode actually in effect, with "auto" resolved."""
        if self.EXTRACTOR == "auto":
            return "gemini" if self.GEMINI_API_KEY else "demo"
        return self.EXTRACTOR

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
