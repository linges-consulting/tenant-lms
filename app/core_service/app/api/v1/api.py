from fastapi import APIRouter

from app.api.v1.endpoints import trainings, users, certificates, progress, dashboards, categories, analytics

api_router = APIRouter()
api_router.include_router(trainings.router, prefix="/trainings", tags=["trainings"])
api_router.include_router(users.router, prefix="/user-report", tags=["user-report"])
api_router.include_router(certificates.router, prefix="/certificates", tags=["certificates"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(dashboards.router, prefix="/dashboards", tags=["dashboards"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

