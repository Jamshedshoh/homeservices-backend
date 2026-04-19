from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # One SQLite file per domain — swap for separate DB servers in production
    auth_database_url: str = "sqlite:///./auth.db"
    jobs_database_url: str = "sqlite:///./jobs.db"
    messaging_database_url: str = "sqlite:///./messaging.db"
    finance_database_url: str = "sqlite:///./finance.db"

    secret_key: str = "change-me-in-production-use-strong-random-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Optional: bootstrap one admin on startup / `python seed_admin.py`
    admin_seed_email: str | None = None
    admin_seed_password: str | None = None

    class Config:
        env_file = (".env", ".env.local")  # .env.local takes precedence
        env_file_encoding = "utf-8"


settings = Settings()
