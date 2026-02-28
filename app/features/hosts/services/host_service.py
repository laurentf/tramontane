"""Host business logic -- orchestrates creation, enrichment, and preview."""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationError
from app.features.hosts.repositories.host_repository import HostRepository
from app.features.hosts.schemas.hosts import (
    EnrichmentResult,
    HostCreate,
    HostResponse,
    HostUpdate,
    TemplateSchema,
)
from app.features.hosts.services import avatar_service
from app.features.hosts.services.llm_enrichment import enrich_host
from app.features.hosts.templates import get_template

logger = structlog.get_logger(__name__)


def _resolve_voice_id(template: TemplateSchema, description: dict[str, Any]) -> str:
    """Pick a voice ID from the template's default_voices based on gender."""
    gender = description.get("gender", "female")
    voices = template.default_voices.get("elevenlabs", {})
    return voices.get(gender) or next(iter(voices.values()), "")


def _row_to_response(row: dict) -> HostResponse:
    """Convert an asyncpg row dict to a HostResponse model."""
    desc = row.get("description") or {}
    if isinstance(desc, str):
        desc = json.loads(desc)

    return HostResponse(
        id=str(row["id"]),
        name=row["name"],
        template_id=row["template_id"],
        short_summary=desc.get("short_summary"),
        self_description=desc.get("self_description"),
        avatar_url=row.get("avatar_url"),
        avatar_status=row.get("avatar_status", "pending"),
        voice_id=row.get("voice_id"),
        status=row.get("status", "draft"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


async def create_host(
    data: HostCreate,
    user_id: str,
    pool: asyncpg.Pool,
    settings: Settings,
) -> HostResponse:
    """Create a new host from template + user inputs."""
    template = get_template(data.template_id)
    if template is None:
        raise ValidationError(f"Unknown template: {data.template_id}")

    repo = HostRepository(pool)
    host_id = await repo.create(
        user_id=user_id,
        name=data.name,
        template_id=data.template_id,
        description=data.description,
        voice_id=_resolve_voice_id(template, data.description),
        status="active",
    )

    row = await repo.get_by_id(host_id, user_id)
    if row is None:
        raise NotFoundError("Host")

    logger.info("host_created", host_id=host_id, template=data.template_id)
    return _row_to_response(row)


async def enrich_host_profile(
    host_id: str,
    user_id: str,
    pool: asyncpg.Pool,
    settings: Settings,
    redis_pool: Any = None,  # arq.connections.ArqRedis (optional dependency)
    *,
    language: str = "fr",
) -> EnrichmentResult:
    """Run LLM enrichment on a host and optionally start avatar generation."""
    repo = HostRepository(pool)
    row = await repo.get_by_id(host_id, user_id)
    if row is None:
        raise NotFoundError("Host")

    template = get_template(row["template_id"])
    if template is None:
        raise ValidationError(f"Unknown template: {row['template_id']}")

    # Get form data from description JSONB.
    form_data = row.get("description") or {}
    if isinstance(form_data, str):
        form_data = json.loads(form_data)

    # Run LLM enrichment.
    result: EnrichmentResult = await enrich_host(
        template, row["name"], form_data, settings, language=language,
    )

    # Merge enrichment data into description JSONB.
    desc = dict(form_data)
    desc["short_summary"] = result.short_summary
    desc["self_description"] = result.self_description

    # Update host with enrichment data.
    await repo.update(
        host_id,
        user_id,
        description=desc,
        avatar_prompt=result.avatar_prompt,
        status="enriched",
    )

    # Enqueue avatar generation if Redis is available.
    if redis_pool is not None:
        try:
            await repo.update_avatar(
                host_id, avatar_url=None, avatar_status="generating",
            )
            await avatar_service.enqueue_avatar_generation(redis_pool, host_id)
        except Exception as exc:
            logger.warning("avatar_enqueue_failed", host_id=host_id, error=str(exc))

    logger.info("host_enriched", host_id=host_id)
    return result


async def get_host(
    host_id: str,
    user_id: str,
    pool: asyncpg.Pool,
) -> HostResponse | None:
    """Get a single host by ID."""
    repo = HostRepository(pool)
    row = await repo.get_by_id(host_id, user_id)
    return _row_to_response(row) if row else None


async def get_host_public(
    host_id: str,
    pool: asyncpg.Pool,
) -> HostResponse | None:
    """Get a single host by ID (no user scope — read-only for all)."""
    repo = HostRepository(pool)
    row = await repo.get_by_id_unscoped(host_id)
    return _row_to_response(row) if row else None


async def list_hosts(
    user_id: str,
    pool: asyncpg.Pool,
) -> list[HostResponse]:
    """List all hosts for a user."""
    repo = HostRepository(pool)
    rows = await repo.list_by_user(user_id)
    return [_row_to_response(r) for r in rows]


async def list_all_hosts(
    pool: asyncpg.Pool,
) -> list[HostResponse]:
    """List all hosts across users (read-only for all)."""
    repo = HostRepository(pool)
    rows = await repo.list_all()
    return [_row_to_response(r) for r in rows]


async def update_host(
    host_id: str,
    data: HostUpdate,
    user_id: str,
    pool: asyncpg.Pool,
) -> HostResponse | None:
    """Update a host's editable fields."""
    repo = HostRepository(pool)

    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        row = await repo.get_by_id(host_id, user_id)
        return _row_to_response(row) if row else None

    row = await repo.update(host_id, user_id, **update_fields)
    return _row_to_response(row) if row else None


async def delete_host(
    host_id: str,
    user_id: str,
    pool: asyncpg.Pool,
) -> bool:
    """Delete a host and cascade-delete its schedule blocks."""
    repo = HostRepository(pool)

    await repo.delete_schedule_blocks(host_id)
    return await repo.delete(host_id, user_id)
