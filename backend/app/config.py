from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://healtrip:healtrip@db:5432/healtrip"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"
    cors_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
