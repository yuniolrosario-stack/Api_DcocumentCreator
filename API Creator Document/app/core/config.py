from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "secret-key"

    # Seguridad & JWT
    JWT_SECRET_KEY: str = "super-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "firmagob-api"
    JWT_AUDIENCE: str = "firmagob-clients"
    JWT_EXPIRATION_MINUTES: int = 60

    # CORS & Forwarded Proxies
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000"
    TRUSTED_PROXIES: str = "127.0.0.1"

    # Rate Limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_GENERAL: str = "60/minute"
    RATE_LIMIT_VIAFIRMA: str = "30/minute"

    # Viafirma / Firma GOB Integration Security
    VIAFIRMA_CALLBACK_SECRET: str = "CALLBACK_INSTITUCIONAL_01"
    FIRMAGOB_BASE_URL: str = "http://localhost:8000/mock-ogtic"
    FIRMAGOB_USER: str = "api_user_ogtic"
    FIRMAGOB_PASSWORD: str = "api_password_ogtic"
    FIRMAGOB_CALLBACK_CODE: str = "CALLBACK_INSTITUCIONAL_01"

    # Webhook Callback URL
    CALLBACK_URL: str = "http://localhost:8000/api/v1/firmagob/callback"

    # Mock Server
    ENABLE_MOCK_OGTIC: bool = True
    MOCK_SIGN_DELAY_SECONDS: int = 2

    # Storage & DB
    STORAGE_DIR: str = "storage"
    DATABASE_URL: str = "sqlite:///./firmagob.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_proxies_list(self) -> list[str]:
        if not self.TRUSTED_PROXIES:
            return ["127.0.0.1"]
        return [proxy.strip() for proxy in self.TRUSTED_PROXIES.split(",") if proxy.strip()]


    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        (p / "original").mkdir(parents=True, exist_ok=True)
        (p / "signed").mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
