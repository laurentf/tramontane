"""Central API router that mounts all feature routers."""

from fastapi import APIRouter

from app.features.auth.api.auth import router as auth_router
from app.features.hosts.api.hosts import router as hosts_router
from app.features.ingest.api.ingest import router as ingest_router
from app.features.radio.api.radio import router as radio_router
from app.features.schedule.api.schedule import router as schedule_router
from app.features.settings.api.settings import router as settings_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(radio_router)
router.include_router(ingest_router)
router.include_router(hosts_router)
router.include_router(schedule_router)
router.include_router(settings_router)
