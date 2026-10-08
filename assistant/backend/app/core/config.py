from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "هم‌درس | دستیار یادگیری"
    APP_VERSION: str = "0.8.0"
    ECE_DOCS_PATH: str = ""
    DEBUG: bool = False
    DATABASE_SCHEMA: str = ""
    SITE_FILE_STORAGE: Literal["local", "supabase"] = "local"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "hamdars-files"
    CLOUD_DEPLOYMENT: bool = False
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'data' / 'learning.db'}"
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-6-astra"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    LLM_MODELS: str = ""
    LLM_API_FORMAT: Literal["responses", "chat_completions"] = "responses"
    LLM_TIMEOUT_SECONDS: int = 60

    @property
    def llm_key(self):
        return self.LLM_API_KEY or self.OPENAI_API_KEY

    @property
    def llm_base_url(self):
        return self.LLM_BASE_URL or self.OPENAI_BASE_URL

    @property
    def llm_model(self):
        return self.llm_models[0]

    @property
    def llm_models(self):
        models = list(dict.fromkeys(m.strip() for m in self.LLM_MODELS.split(",") if m.strip()))
        return models or [self.LLM_MODEL or self.OPENAI_MODEL]

    REPORT_LLM_TIMEOUT_SECONDS: int = 180
    REPORT_LLM_MODELS: str = ""
    REPORT_WORKER_ENABLED: bool = True
    REPORT_WORKER_CONCURRENCY: int = 1

    MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024
    MAX_RESOURCE_PAGES: int = 3000
    MAX_RESOURCE_CHARACTERS: int = 20_000_000

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR / ".env.local"),
        env_file_encoding="utf-8", extra="ignore",
    )


settings = Settings()
