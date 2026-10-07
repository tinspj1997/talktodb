from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL_API_KEY: str
    LLM_MODEL_NAME: str


settings = Settings()
