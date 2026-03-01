"""Host schemas: Pydantic models for the host feature."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class HostStatus(StrEnum):
    """Valid states for a host record."""

    DRAFT = "draft"
    ACTIVE = "active"
    ENRICHED = "enriched"
    ARCHIVED = "archived"


class AvatarStatus(StrEnum):
    """Valid states for avatar generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"

# ---------------------------------------------------------------------------
# Template field schemas (YAML-loaded)
# ---------------------------------------------------------------------------


class FieldType(StrEnum):
    """Valid form field types for template YAML."""

    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTI_SELECT = "multi_select"


class FieldOption(BaseModel):
    """Option for a select / multi_select field."""

    value: str
    translations: dict[str, str]


class TemplateField(BaseModel):
    """Dynamic form field definition in a template YAML."""

    field_key: str
    field_type: FieldType
    required: bool = False
    min_length: int | None = None
    max_length: int | None = None
    min_select: int | None = None
    max_select: int | None = None
    translations: dict[str, dict[str, str]]  # {locale: {label, placeholder?}}
    options: list[FieldOption] | None = None


class PromptTemplates(BaseModel):
    """Structured prompt templates for radio host LLM generation."""

    core_identity_template: str
    output_format_text: str
    output_format_voice: str
    greeting_prompt: str | None = None
    show_intro_template: str | None = None
    track_intro_template: str | None = None
    fallback_identity: str | None = None


class TemplateSchema(BaseModel):
    """Radio host personality template loaded from YAML."""

    template_id: str
    name: dict[str, str]
    description: dict[str, str]
    icon: str
    general_fields: list[TemplateField]
    template_fields: list[TemplateField]
    default_voices: dict[str, dict[str, str]]
    avatar_generation_params: dict[str, Any]
    avatar_style_hint: str
    enrichment_prompt: str
    prompt_templates: PromptTemplates | None = None


# ---------------------------------------------------------------------------
# Questionnaire API response (locale-resolved)
# ---------------------------------------------------------------------------


class QuestionnaireFieldOption(BaseModel):
    """Locale-resolved option for a questionnaire field."""

    value: str
    label: str


class QuestionnaireField(BaseModel):
    """Locale-resolved form field returned by the questionnaire endpoint."""

    field_key: str
    field_type: str
    required: bool
    label: str
    placeholder: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_select: int | None = None
    max_select: int | None = None
    options: list[QuestionnaireFieldOption] | None = None


class QuestionnaireResponse(BaseModel):
    """Response model for template questionnaire."""

    template_id: str
    fields: list[QuestionnaireField]


# ---------------------------------------------------------------------------
# Template list response
# ---------------------------------------------------------------------------


class TemplateResponse(BaseModel):
    """Response model for a personality template."""

    template_id: str
    name: str
    description: str
    icon: str


# ---------------------------------------------------------------------------
# Host CRUD
# ---------------------------------------------------------------------------


class HostCreate(BaseModel):
    """Request body for creating a host."""

    name: str = Field(..., min_length=1, max_length=50)
    template_id: str
    description: dict[str, Any] = Field(default_factory=dict)


class HostUpdate(BaseModel):
    """Request body for updating a host."""

    name: str | None = Field(None, min_length=1, max_length=50)
    voice_provider: str | None = None
    status: HostStatus | None = None


class HostResponse(BaseModel):
    """Response model for a host record."""

    id: str
    name: str
    template_id: str
    short_summary: str | None = None
    self_description: str | None = None
    avatar_url: str | None
    avatar_status: AvatarStatus
    voice_id: str | None
    voice_provider: str
    status: HostStatus
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


class EnrichmentResult(BaseModel):
    """Result from LLM host profile enrichment."""

    short_summary: str
    self_description: str
    avatar_prompt: str
