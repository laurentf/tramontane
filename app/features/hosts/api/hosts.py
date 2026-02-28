"""Host CRUD API endpoints."""

from __future__ import annotations

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.core.config import Settings, get_settings
from app.core.deps.db import get_db_pool
from app.core.deps.storage import get_storage_service
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from app.core.security import get_current_user_id, require_admin
from app.features.hosts.schemas.hosts import (
    EnrichmentResult,
    HostCreate,
    HostResponse,
    HostUpdate,
    QuestionnaireField,
    QuestionnaireFieldOption,
    QuestionnaireResponse,
    TemplateResponse,
)
from app.features.hosts.services import host_service
from app.features.hosts.templates import get_template, list_templates
from app.features.settings.services import settings_service
from app.providers.ai_exceptions import AIProviderError
from app.providers.storage import StorageProvider

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/hosts", tags=["hosts"])


# ---------------------------------------------------------------------------
# Templates (public)
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[TemplateResponse])
async def get_templates(locale: str = "fr") -> list[TemplateResponse]:
    """List all available personality templates, localized."""
    templates = list_templates()
    return [
        TemplateResponse(
            template_id=t.template_id,
            name=t.name.get(locale, t.name.get("en", "")),
            description=t.description.get(locale, t.description.get("en", "")),
            icon=t.icon,
        )
        for t in templates
    ]


@router.get(
    "/templates/{template_id}/questionnaire",
    response_model=QuestionnaireResponse,
)
async def get_questionnaire(
    template_id: str,
    locale: str = "fr",
) -> QuestionnaireResponse:
    """Get the dynamic form fields for a template, localized."""
    template = get_template(template_id)
    if template is None:
        raise NotFoundError("Template")

    fields: list[QuestionnaireField] = []
    for f in template.general_fields + template.template_fields:
        trans = f.translations.get(locale, f.translations.get("en", {}))
        field = QuestionnaireField(
            field_key=f.field_key,
            field_type=f.field_type,
            required=f.required,
            label=trans.get("label", f.field_key),
            placeholder=trans.get("placeholder"),
            min_length=f.min_length,
            max_length=f.max_length,
            min_select=f.min_select,
            max_select=f.max_select,
            options=[
                QuestionnaireFieldOption(
                    value=opt.value,
                    label=opt.translations.get(locale, opt.translations.get("en", opt.value)),
                )
                for opt in f.options
            ] if f.options else None,
        )
        fields.append(field)

    return QuestionnaireResponse(template_id=template_id, fields=fields)


# ---------------------------------------------------------------------------
# Avatar (public — avatars are visible to all listeners)
# ---------------------------------------------------------------------------


@router.get("/{host_id}/avatar")
async def get_host_avatar(
    host_id: str,
    pool: asyncpg.Pool = Depends(get_db_pool),
    storage: StorageProvider = Depends(get_storage_service),
) -> Response:
    """Serve a host's avatar from private storage."""
    from app.features.hosts.repositories.host_repository import HostRepository

    repo = HostRepository(pool)
    row = await repo.get_by_id_unscoped(host_id)
    if row is None:
        raise NotFoundError("Host")

    avatar_path = row.get("avatar_url")
    if not avatar_path or avatar_path.startswith("http"):
        raise NotFoundError("Avatar")

    try:
        image_bytes = await storage.download_avatar(avatar_path)
    except Exception as exc:
        raise NotFoundError("Avatar") from exc

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Host CRUD (admin)
# ---------------------------------------------------------------------------


@router.post("", response_model=HostResponse, status_code=201)
async def create_host(
    body: HostCreate,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
    settings: Settings = Depends(get_settings),
) -> HostResponse:
    """Create a new host from a personality template."""
    return await host_service.create_host(body, user_id, pool, settings)


@router.get("", response_model=list[HostResponse])
async def list_hosts(
    _user_id: str = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[HostResponse]:
    """List all hosts (read-only for any authenticated user)."""
    return await host_service.list_all_hosts(pool)


@router.get("/{host_id}", response_model=HostResponse)
async def get_host(
    host_id: str,
    _user_id: str = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> HostResponse:
    """Get a single host by ID (read-only for any authenticated user)."""
    host = await host_service.get_host_public(host_id, pool)
    if host is None:
        raise NotFoundError("Host")
    return host


@router.patch("/{host_id}", response_model=HostResponse)
async def update_host(
    host_id: str,
    body: HostUpdate,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> HostResponse:
    """Update a host's editable fields."""
    host = await host_service.update_host(host_id, body, user_id, pool)
    if host is None:
        raise NotFoundError("Host")
    return host


@router.delete("/{host_id}", status_code=204)
async def delete_host(
    host_id: str,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Delete a host. Fails if host has schedule block assignments."""
    deleted = await host_service.delete_host(host_id, user_id, pool)
    if not deleted:
        raise NotFoundError("Host")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Enrichment (authenticated)
# ---------------------------------------------------------------------------


@router.post("/{host_id}/enrich", response_model=EnrichmentResult)
async def enrich_host(
    host_id: str,
    request: Request,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
    settings: Settings = Depends(get_settings),
) -> EnrichmentResult:
    """Trigger LLM enrichment for a host's personality profile."""
    radio_settings = await settings_service.get_settings(user_id, pool)
    language = radio_settings.language

    redis_pool = getattr(request.app.state, "arq_pool", None)

    try:
        return await host_service.enrich_host_profile(
            host_id, user_id, pool, settings, redis_pool=redis_pool,
            language=language,
        )
    except AIProviderError as exc:
        raise ServiceUnavailableError(str(exc)) from exc


@router.post("/{host_id}/regenerate-avatar")
async def regenerate_avatar(
    host_id: str,
    request: Request,
    user_id: str = Depends(require_admin),
    pool: asyncpg.Pool = Depends(get_db_pool),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Re-trigger avatar generation for a host."""
    from app.features.hosts.repositories.host_repository import HostRepository
    from app.features.hosts.services.avatar_service import enqueue_avatar_generation

    repo = HostRepository(pool)
    row = await repo.get_by_id(host_id, user_id)
    if row is None:
        raise NotFoundError("Host")

    if not row.get("avatar_prompt"):
        raise ValidationError("Host has no avatar prompt. Run enrichment first.")

    redis_pool = getattr(request.app.state, "arq_pool", None)
    if redis_pool is None:
        raise ServiceUnavailableError("Background job queue not available")

    await repo.update_avatar(
        host_id, avatar_url=None, avatar_status="generating",
    )
    await enqueue_avatar_generation(redis_pool, host_id)

    return {"status": "generating"}
