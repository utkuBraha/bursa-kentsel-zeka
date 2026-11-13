from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://urban:urban_local_dev@127.0.0.1:5433/urban"
    )
    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
