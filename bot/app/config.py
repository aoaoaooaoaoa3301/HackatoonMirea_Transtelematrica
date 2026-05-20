from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = ""
    BACKEND_URL: str = "http://backend:8000"
    TELEGRAM_INTERNAL_TOKEN: str = "change-me"


settings = Settings()
