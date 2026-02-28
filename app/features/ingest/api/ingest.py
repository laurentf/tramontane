"""Ingest API — scan music directory, read tags, write to database."""

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends

from app.core.deps.ingest import get_ingest_service
from app.core.exceptions import ValidationError
from app.core.security import require_admin
from app.features.ingest.schemas.ingest import ScanRequest, ScanResult
from app.features.ingest.services.ingest_service import IngestService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/scan", response_model=ScanResult)
async def scan(
    body: ScanRequest,
    _user_id: str = Depends(require_admin),
    ingest_service: IngestService = Depends(get_ingest_service),
) -> ScanResult:
    """Scan a directory for audio files, read their tags, and store in the database."""
    directory = Path(body.directory).resolve()
    if not directory.is_relative_to(Path("/music")):
        raise ValidationError("Directory must be within /music")
    if not directory.is_dir():
        logger.warning("scan_directory_not_found", directory=body.directory)
        return ScanResult(scanned=0, stored=0, tracks=[])

    return await ingest_service.scan_and_store(directory)
