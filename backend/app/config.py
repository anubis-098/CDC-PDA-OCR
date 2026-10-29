from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pda:change-me-local-only@db:5432/pda_ocr"
    upload_dir: Path = Path("/data/uploads")
    # PP-OCRv5 Thai recognizer supports Thai, English, and digits in one fast pass.
    ocr_lang: str = "th"
    min_confidence: float = Field(default=0.85, ge=0, le=1)
    max_file_bytes: int = 10 * 1024 * 1024
    max_pages: int = 5
    max_pixels: int = 25_000_000
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def settings() -> Settings:
    return Settings()
