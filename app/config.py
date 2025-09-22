
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    DB_URL: str = "sqlite:///notes.db"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
