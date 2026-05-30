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
    
    # Legacy fallbacks
    SECRET_KEY: str = EXTERNAL_JWT_SECRET

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes
    ENVIRONMENT: str = "development"  # override to "production" in prod
    
    # DB
    DB_URL: str = "postgresql+asyncpg://lms_user:lms_pass@postgres/core_db"
    
    @property
    def ASYNC_DB_URL(self) -> str:
        if self.DB_URL.startswith("postgresql://"):
            return self.DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DB_URL
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CACHE_TTL_SHORT: int = 300    # 5 min  — most API responses
    CACHE_TTL_MEDIUM: int = 600   # 10 min — group/admin data
    CACHE_TTL_LONG: int = 1800    # 30 min — rarely-changing data
    
    # Service Authentication (Internal Validation)
    INTERNAL_API_KEY: str = "super-secret-internal-key"
    AUTH_SERVICE_URL: str = "http://auth-service:8000"

    # CORS — comma-separated list of allowed origins (no wildcard with credentials)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
