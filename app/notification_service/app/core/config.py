from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LMS Notification Service"
    API_V1_STR: str = "/api/v1"
    
    # C-105 Secret Hierarchy
    JWT_ROOT_SECRET: str = "root-secret-key-change-this"
    EXTERNAL_JWT_SECRET: str = "external-secret-key-change-this"
    INTERNAL_JWT_SECRET: str = "internal-secret-key-change-this"
    INTERNAL_SERVICE_SECRET: str = "service-secret-key-change-this"
    
    # Legacy fallbacks
    SECRET_KEY: str = EXTERNAL_JWT_SECRET
    ALGORITHM: str = "HS256"
    
    DB_URL: str = "postgresql+asyncpg://lms_user:lms_pass@postgres/notification_db"
    REDIS_URL: str
    CACHE_TTL_SHORT: int = 300    # 5 min  — most API responses
    CACHE_TTL_MEDIUM: int = 600   # 10 min — group/admin data
    CACHE_TTL_LONG: int = 1800    # 30 min — rarely-changing data
    INTERNAL_API_KEY: str
    AUTH_SERVICE_URL: str = "http://auth-service:8000"
    ENVIRONMENT: str = "development"  # override to "production" in prod

    # Mailgun / Email settings
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAILGUN_BASE_URL: str = "https://api.mailgun.net"
    FROM_EMAIL: str = "noreply@example.com"
    USE_MAILGUN: bool = False
    MAILGUN_AUTHORIZED_RECIPIENT: str = ""
    FRONTEND_URL: str = "http://localhost"
    CORE_SERVICE_URL: str = "http://core-service:8000"

    # CORS — comma-separated list of allowed origins (no wildcard with credentials)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def ASYNC_DB_URL(self) -> str:
        if self.DB_URL.startswith("postgresql://"):
            return self.DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DB_URL

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
