from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "LegalMetrix AI"
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-me-in-production-legalmetrix-auth-secret-key-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEBUG: bool = True

    # Development Seed Users
    DEV_ADMIN_EMAIL: str = "admin@gmail.com"
    DEV_ADMIN_PASSWORD: str = "Admin123"
    DEV_ADMIN_NAME: str = "Dr. Rajesh Verma (Administrator)"

    DEV_INSPECTOR_EMAIL: str = "inspector@gmail.com"
    DEV_INSPECTOR_PASSWORD: str = "Inspector123"
    DEV_INSPECTOR_NAME: str = "Aditi Sharma (Inspector)"

    DEV_REVIEWER_EMAIL: str = "reviewer@gmail.com"
    DEV_REVIEWER_PASSWORD: str = "Reviewer123"
    DEV_REVIEWER_NAME: str = "Suresh Patel (Review Officer)"


    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:password@localhost:5432/legalmetrix"

    # Storage Configuration
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_IMAGES_PER_SCAN: int = 8

    # Day 4: Image Quality & OCR Engine Configuration
    OCR_ENGINE: str = "paddleocr"
    IMAGE_BLUR_THRESHOLD: float = 100.0
    IMAGE_GLARE_THRESHOLD: float = 0.05
    MIN_IMAGE_WIDTH: int = 400
    MIN_IMAGE_HEIGHT: int = 400
    OCR_LOW_CONFIDENCE_THRESHOLD: float = 0.60
    OCR_USE_ANGLE_CLS: bool = True
    OCR_LANG: str = "en"

    # AI Assistant & LLM Configuration
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PROVIDER: str = "auto"  # auto, gemini, openai, groq, ollama, mock
    LLM_MODEL: str = "gemini-3.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
