from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Shop API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://shop:shop@localhost:5432/shop"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Auth
    secret_key: str = DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == DEFAULT_SECRET:
            raise ValueError("SECRET_KEY must be set in production")
        return self


settings = Settings()