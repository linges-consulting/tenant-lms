import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.v1.api import api_router
from app.core.logging_config import setup_logging
from app.core.limiter import limiter
from app.core.config import settings

# Initialize production-grade logging
setup_logging()

logger = logging.getLogger(__name__)

_is_prod = settings.ENVIRONMENT == "production"

app = FastAPI(
    title="Auth Service",
    openapi_url=f"/api/v1/openapi.json" if not _is_prod else None,
    docs_url="/docs" if not _is_prod else None,
    redoc_url="/redoc" if not _is_prod else None,
)

# Application-layer rate limiter (defense in depth behind Nginx)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS setup — explicit origins only; wildcard + credentials is a security violation
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Internal-Api-Key"],
)

app.include_router(api_router, prefix="/api/v1")

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again or contact support."},
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "auth_service"}
