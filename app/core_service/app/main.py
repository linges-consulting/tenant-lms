import uuid
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt, JWTError

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.logging_config import setup_logging

# Initialize production-grade logging
logger = setup_logging()

from app.core.event_handler import consume_events

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks
    task = asyncio.create_task(consume_events())
    yield
    # Cleanup
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

_is_prod = settings.ENVIRONMENT == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if not _is_prod else None,
    docs_url="/docs" if not _is_prod else None,
    redoc_url="/redoc" if not _is_prod else None,
    description="CustomLMS API - Multi-Tenant Learning Management System",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS — explicit origins only; wildcard + credentials is a security violation
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Internal-Api-Key"],
)

# Middleware for Structured Logging & Request ID
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # In microservices, we might extract user_id from headers passed by API Gateway
    # or validated tokens. For now, basic logging.
    user_id = "unknown"
            
    # Get dedicated request/response logger
    req_resp_logger = logging.getLogger("request_response")
    
    # Pre-request logging
    ip = request.client.host if request.client else "unknown"
    req_resp_logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "ip": ip,
            "method": request.method,
            "path": request.url.path,
            "user_id": user_id
        }
    )
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    # Post-request logging
    req_resp_logger.info(
        f"Completed request: {request.method} {request.url.path} with status {response.status_code}",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user_id
        }
    )
    
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(api_router, prefix=settings.API_V1_STR)

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
    return {"status": "ok", "service": "core-training-service"}

