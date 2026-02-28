"""Dependency injection for ingest feature."""

import asyncpg
from fastapi import Depends

from app.core.deps.db import get_db_pool
from app.features.ingest.repositories.tag_repository import TagRepository
from app.features.ingest.repositories.track_repository import TrackRepository
from app.features.ingest.services.ingest_service import IngestService


def get_ingest_service(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> IngestService:
    """Build IngestService with its repository dependencies."""
    track_repo = TrackRepository(pool)
    tag_repo = TagRepository(pool)
    return IngestService(track_repo=track_repo, tag_repo=tag_repo)
