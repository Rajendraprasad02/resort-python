from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Purva Villa"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: str
    BYPASS_AUTH: bool = True
    GROQ_API_KEYS: str = ""
    GROQ_MODEL_NAME: str = "groq/compound-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"
    DEFAULT_AI_PROVIDER: str = "groq"
    
    # WhatsApp Meta Cloud API
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "elite_verify_token"
    WHATSAPP_API_VERSION: str = "v21.0"

    class Config:
        import os
        env_file = os.path.join(os.getcwd(), ".env")
        case_sensitive = True
        extra = "ignore"

settings = Settings()
