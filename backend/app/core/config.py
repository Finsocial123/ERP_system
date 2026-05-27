from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./erp_phase1.db"
    ASYNC_DATABASE_URL: str = "sqlite:///./erp_phase1.db"
    SECRET_KEY: str = "change-this-secret-key-before-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # AI / integrations. Keep real keys only in .env, never in committed code.
    OPENROUTER_API_KEY: str = ""
    MODEL: str = "anthropic/claude-sonnet-4.6"
    TRANSCRIPTION_MODEL: str = "openai/whisper-large-v3"
    EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    TAVILY_API_KEY: str = ""
    BBB_URL: str = "https://tensordock-bbb.freedynamicdns.net/bigbluebutton/"
    BBB_SECRET: str = ""

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    GOOGLE_CLIENT_ID: str = ""

    # Email OTP / password reset
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    EMAIL_OTP_DEBUG: bool = True
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "School ERP"
    SMTP_USE_TLS: bool = True

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def smtp_from_email(self) -> str:
        return self.SMTP_FROM_EMAIL or self.SMTP_USERNAME


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

MODEL = settings.MODEL
