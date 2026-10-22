from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수(.env)에서 읽는 설정 (기술 명세서 §1-5)."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    gemini_api_key: str = ""


def get_settings() -> Settings:
    return Settings()
