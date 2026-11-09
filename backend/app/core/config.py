import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sổ Điểm Danh API"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "super_secret_jwt_key_change_in_production_please_generate_random_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 365  # 1 year expiration for uninterrupted teacher access

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres123@localhost:5432/attendance_db"
    # SAFETY: never silently fall back to an empty SQLite DB in production.
    # Enable explicitly (USE_SQLITE_FALLBACK=true) only for local development.
    USE_SQLITE_FALLBACK: bool = False

    # When true, every /api/* request returns 503 (health endpoints stay up).
    MAINTENANCE_MODE: bool = False

    # Optional: if set, /health only includes row counts when header X-Health-Token matches.
    HEALTH_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
