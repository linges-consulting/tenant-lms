from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import users
from app.api.v1.endpoints import tenants
from app.api.v1.endpoints import groups
from app.api.v1.endpoints import media
from app.api.v1.endpoints import password_reset
from app.api.v1.endpoints import heartbeat

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(media.router, prefix="/auth", tags=["media"])
api_router.include_router(password_reset.router, prefix="/auth", tags=["password-reset"])
api_router.include_router(heartbeat.router, prefix="/auth", tags=["heartbeat"])
