from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user@localhost:5432/homeservices"

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
