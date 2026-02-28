"""Central API router that mounts all feature routers."""

from fastapi import APIRouter

from app.features.auth.api.auth import router as auth_router
from app.features.ingest.api.ingest import router as ingest_router
from app.features.radio.api.radio import router as radio_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(radio_router)
router.include_router(ingest_router)
