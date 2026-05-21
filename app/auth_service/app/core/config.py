from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "CustomLMS"
    API_V1_STR: str = "/api/v1"
    # C-105 Secret Hierarchy
    JWT_ROOT_SECRET: str = "root-secret-key-change-this"
    EXTERNAL_JWT_SECRET: str = "external-secret-key-change-this"
    INTERNAL_JWT_SECRET: str = "internal-secret-key-change-this"
    INTERNAL_SERVICE_SECRET: str = "service-secret-key-change-this"
    
    # Legacy fallbacks (to be removed once fully migrated)
    SECRET_KEY: str = EXTERNAL_JWT_SECRET
    
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes
    ENVIRONMENT: str = "development"  # override to "production" in prod
    
    # Mailgun
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAILGUN_BASE_URL: str = "https://api.mailgun.net"
    MAILGUN_AUTHORIZED_RECIPIENT: str = "admin@example.com"
    
    # DB
    DB_URL: str = "postgresql+asyncpg://lms_user:lms_pass@postgres/auth_db"
    
    @property
    def ASYNC_DB_URL(self) -> str:
        if self.DB_URL.startswith("postgresql://"):
            return self.DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DB_URL

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Service Authentication (Internal Validation)
    INTERNAL_API_KEY: str = "super-secret-internal-key"
    
    # Internal service URLs (used for inter-service calls)
    CORE_SERVICE_URL: str = "http://core-service:8001"

    # Auth
    SESSION_TOKEN_EXPIRE_MINUTES: int = 30

    # Login lockout
    LOGIN_MAX_ATTEMPTS: int = 5           # temp lockout after this many failures
    LOGIN_LOCKOUT_MINUTES: int = 15       # how long temp lockout lasts
    LOGIN_FORCE_RESET_ATTEMPTS: int = 10  # force password reset after this many failures
    
    # Frontend URL for magic links and redirects
    FRONTEND_URL: str = "http://localhost"
    
    # CORS — comma-separated list of allowed origins (no wildcard with credentials)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
