"""Ingest API — scan music directory, read tags, write to database."""

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.deps.ingest import get_ingest_service
from app.core.exceptions import ValidationError
from app.core.security import require_admin
from app.features.ingest.schemas.ingest import ScanRequest, ScanResult
from app.features.ingest.services.ingest_service import IngestService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/scan", response_model=ScanResult)
async def scan(
    request: Request,
    body: ScanRequest,
    _user_id: str = Depends(require_admin),
    ingest_service: IngestService = Depends(get_ingest_service),
) -> ScanResult:
    """Scan a directory for audio files, read their tags, and store in the database."""
    music_root = Path(get_settings().music_dir).resolve()
    directory = Path(body.directory).resolve()
    if not directory.is_relative_to(music_root):
        raise ValidationError(f"Directory must be within {music_root}")
    if not directory.is_dir():
        logger.warning("scan_directory_not_found", directory=body.directory)
        return ScanResult(scanned=0, stored=0, tracks=[])

    result = await ingest_service.scan_and_store(directory)

    if result.stored > 0:
        arq_pool = getattr(request.app.state, "arq_pool", None)
        if arq_pool is not None:
            await arq_pool.enqueue_job("embed_tracks_task")
            logger.info("embed_job_enqueued", stored=result.stored)

    return result
