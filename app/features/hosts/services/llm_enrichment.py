"""LLM enrichment service for generating host personality profiles."""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.core.config import Settings
from app.features.hosts.schemas.hosts import EnrichmentResult, TemplateSchema
from app.providers.ai_exceptions import AIProviderError
from app.providers.ai_models import AIMessage
from app.providers.registry import llm_registry

logger = structlog.get_logger(__name__)


def _format_form_data(form_data: dict[str, Any], template: TemplateSchema) -> str:
    """Format JSONB form data as readable text for the LLM prompt."""
    lines: list[str] = []
    all_fields = template.general_fields + template.template_fields
    field_map = {f.field_key: f for f in all_fields}

    for key, value in form_data.items():
        if key in ("short_summary", "self_description"):
            continue
        label = key.replace("_", " ").title()
        field = field_map.get(key)
        if field:
            label = field.translations.get("en", {}).get("label", label)
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        lines.append(f"- {label}: {value}")

    return "\n".join(lines) if lines else "- No specific preferences provided"


async def enrich_host(
    template: TemplateSchema,
    name: str,
    form_data: dict[str, Any],
    settings: Settings,
    *,
    language: str = "fr",
) -> EnrichmentResult:
    """Generate a complete host profile from a template and user inputs.

    Raises:
        AIProviderError: If LLM API key is not configured or API call fails.
    """
    if settings.mistral_api_key is None:
        raise AIProviderError(
            "mistral", "Mistral API key not configured -- fill in fields manually"
        )

    adapter = llm_registry.create(
        settings.llm_provider,
        api_key=settings.mistral_api_key.get_secret_value(),
        default_model=settings.llm_model,
    )

    form_text = _format_form_data(form_data, template)

    enrichment_text = template.enrichment_prompt.format(
        name=name,
        form_data=form_text,
        avatar_style_hint=template.avatar_style_hint,
    )

    lang_names = {"en": "English", "fr": "French", "es": "Spanish"}
    lang_label = lang_names.get(language, "French")

    messages = [
        AIMessage(role="system", content=enrichment_text),
        AIMessage(
            role="user",
            content=(
                f"Create the personality profile for '{name}'. "
                f"IMPORTANT: Generate ALL text content (short_summary, "
                f"self_description) in {lang_label}. The host broadcasts in {lang_label}. "
                f"The avatar_prompt must always be in English."
            ),
        ),
    ]

    # First attempt with creative temperature.
    response = await adapter.generate(
        messages, response_format={"type": "json_object"}, max_tokens=1024, temperature=0.8,
    )

    try:
        data = json.loads(response.content)
        return _parse_enrichment(data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "enrichment_json_parse_failed",
            error=str(exc),
            content_preview=response.content[:200],
        )

    # Retry with lower temperature for more structured output.
    response = await adapter.generate(
        messages, response_format={"type": "json_object"}, max_tokens=1024, temperature=0.5,
    )
    try:
        data = json.loads(response.content)
        return _parse_enrichment(data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.error("enrichment_json_retry_failed", error=str(exc))
        raise AIProviderError(
            "mistral", f"Failed to parse LLM enrichment response: {exc}"
        ) from exc


def _parse_enrichment(data: dict[str, Any]) -> EnrichmentResult:
    """Parse raw LLM JSON into an EnrichmentResult."""
    return EnrichmentResult(
        short_summary=data["short_summary"],
        self_description=data["self_description"],
        avatar_prompt=data["avatar_prompt"],
    )
