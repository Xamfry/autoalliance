from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/app.db"

    autoalliance_api_key: str | None = None
    autoalliance_base_url: str = "https://beta.autoopt.ru"
    autoalliance_timeout: int = 60
    web_secret_key: str = "change-this-super-secret-key"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()