from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://ttm:ttm@db:5432/ttm"
    JWT_SECRET: str = "change-me-in-prod-32-chars-minimum"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    OLLAMA_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "ai/gemma4:E4B"
    LLM_PROVIDER: str = "docker_model"
    DOCKER_MODEL_URL: str = "http://model-runner.docker.internal"
    OLLAMA_TIMEOUT: int = 30
    OPENAI_COMPATIBLE_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_COMPATIBLE_API_KEY: str = ""
    OPENAI_COMPATIBLE_MODEL: str = "qwen/qwen-2.5-7b-instruct"
    OPENAI_COMPATIBLE_TIMEOUT: int = 60
    OPENAI_COMPATIBLE_REFERER: str = "http://localhost"
    OPENAI_COMPATIBLE_APP_TITLE: str = "TTM Task Assistant"
    OPENAI_COMPATIBLE_PROVIDER_ORDER: str = ""
    TELEGRAM_INTERNAL_TOKEN: str = "change-me"
    TELEGRAM_LINK_CODE_TTL_MINUTES: int = 15
    # Bot @username (without @) — used to build t.me deep links / QR codes.
    TELEGRAM_BOT_USERNAME: str = ""
    # Public base URL of the web app — used to turn task IDs into clickable
    # links inside Telegram messages (e.g. http://localhost/tasks/<id>).
    APP_PUBLIC_URL: str = "http://localhost"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
