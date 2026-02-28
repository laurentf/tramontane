"""Central API router that mounts all feature routers."""

from fastapi import APIRouter

from app.features.auth.api.auth import router as auth_router

router = APIRouter()

router.include_router(auth_router)
