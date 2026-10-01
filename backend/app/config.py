from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://healtrip:healtrip@db:5432/healtrip"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"
    cors_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value):
        if isinstance(value, str) and value.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        return value

settings = Settings()
