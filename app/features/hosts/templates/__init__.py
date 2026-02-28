"""Host personality template registry -- loads YAML templates."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.features.hosts.schemas.hosts import TemplateSchema

_TEMPLATES: dict[str, TemplateSchema] | None = None
_TEMPLATES_DIR = Path(__file__).parent


def _load_templates() -> dict[str, TemplateSchema]:
    """Glob *.yaml in templates dir, validate each with Pydantic."""
    templates: dict[str, TemplateSchema] = {}
    for path in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        tpl = TemplateSchema.model_validate(data)
        templates[tpl.template_id] = tpl
    return templates


def _get_cache() -> dict[str, TemplateSchema]:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _load_templates()
    return _TEMPLATES


def get_template(template_id: str) -> TemplateSchema | None:
    """Get a template by its ID, or None if not found."""
    return _get_cache().get(template_id)


def list_templates() -> list[TemplateSchema]:
    """Return all available templates."""
    return list(_get_cache().values())
