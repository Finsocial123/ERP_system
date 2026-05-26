from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str # = "sqlite:///./erp_phase1.db"
    ASYNC_DATABASE_URL: str # = "sqlite:///./erp_phase1.db"
    SECRET_KEY: str = "change-this-secret-key-before-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

        

    OPENROUTER_API_KEY: str = "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"

    #Model used in AI
    MODEL: str ="anthropic/claude-sonnet-4.6"
    TRANSCRIPTION_MODEL: str="openai/whisper-large-v3"
    EMBEDDING_MODEL: str="openai/text-embedding-3-small"

    TAVILY_API_KEY: str ="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"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str="dqbxkhtfu"
    CLOUDINARY_API_KEY: str="755599935885622"
    CLOUDINARY_API_SECRET: str="74v-jyTeZpTHUkpvHmuq7d_eltQ"

    
    GOOGLE_CLIENT_ID:str="1075378499088-rgclceatafhnjtr4ali3kjfa5hfp8mhb.apps.googleusercontent.com"

    OTP_EXPIRE_MINUTES:int=10
    OTP_MAX_ATTEMPTS:int=5
    EMAIL_OTP_DEBUG:bool=True

    SMTP_HOST:str="smtp.gmail.com"
    SMTP_PORT:int=587
    SMTP_USERNAME: str="aashishmaurya959@gmail.com"
    SMTP_PASSWORD: str="lrpvexbbzjfrdizt"
    SMTP_FROM_EMAIL: str="aashishmaurya959@gmail.com"
    SMTP_FROM_NAME:str="LMS"
    SMTP_USE_TLS:bool=True

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

MODEL = settings.MODEL