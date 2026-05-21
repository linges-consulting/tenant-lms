import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from fastapi import Query as QP

from app.core.config import settings
from app.db.session import get_db
from app.api import deps
from app.core.cache import invalidate_cache
from app.models.notification import Base, Notification
from app.worker.consumer import consume_events
from app.worker.scheduler import create_scheduler
from app.core.logging_config import setup_logging

# Initialize production-grade logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("LIFESPAN STARTING")
    consumer_task = None
    scheduler = None
    if settings.ENVIRONMENT != "test":
        # Start the consumer task in the background only outside of tests
        consumer_task = asyncio.create_task(consume_events())
        print("Background consumer task created.")
        logger.info("Background consumer task started.")
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Reminder scheduler started.")

    yield

    # Stop the consumer task on shutdown
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.info("Background consumer task stopped.")
    if scheduler:
        scheduler.shutdown()
        logger.info("Reminder scheduler stopped.")

_is_prod = settings.ENVIRONMENT == "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if not _is_prod else None,
    docs_url="/docs" if not _is_prod else None,
    redoc_url="/redoc" if not _is_prod else None,
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
async def health_check():
    return {"status": "ok", "service": "notification-service"}

def notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "event_id": n.event_id,
        "tenant_id": n.tenant_id,
        "user_id": n.user_id,
        "title": n.title,
        "message": n.message,
        "notification_type": n.notification_type,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "data": n.data,
    }


@app.get("/api/v1/notifications")
async def list_notifications(
    limit: int = QP(default=20, ge=1, le=100),
    offset: int = QP(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    count_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
        )
    )
    total = count_result.scalar()

    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
        ).order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    )
    items = result.scalars().all()
    return {"items": [notif_to_dict(n) for n in items], "total": total, "limit": limit, "offset": offset}


@app.get("/api/v1/notifications/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == tenant_id,
            Notification.is_read == False,
        )
    )
    return {"unread_count": result.scalar()}

@app.patch("/api/v1/notifications/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: str = Depends(deps.get_current_tenant_id)
):
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
        .where(Notification.tenant_id == tenant_id)
        .values(is_read=True)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    # Invalidate cache
    await invalidate_cache("notification_list", tenant_id, user_id=current_user.id)
    return {"status": "success"}

@app.patch("/api/v1/notifications/mark-all-read")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: str = Depends(deps.get_current_tenant_id)
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.tenant_id == tenant_id)
        .where(Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    # Invalidate cache
    await invalidate_cache("notification_list", tenant_id, user_id=current_user.id)
    return {"status": "success"}

@app.delete("/api/v1/notifications/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_user),
    tenant_id: str = Depends(deps.get_current_tenant_id)
):
    from sqlalchemy import delete
    result = await db.execute(
        delete(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.user_id == current_user.id)
        .where(Notification.tenant_id == tenant_id)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    # Invalidate cache
    await invalidate_cache("notification_list", tenant_id, user_id=current_user.id)
    return {"status": "success"}
