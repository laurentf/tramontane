"""Skill data models — SkillLevel enum and SkillManifest Pydantic model.

Core types of the skill system, imported by loader, registry, and downstream
consumers. They live in their own module to avoid circular imports.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SkillCapability(StrEnum):
    """App-level provider capability a skill may require.

    Skills declare ``uses: [search, weather, ...]`` so the loader can verify
    that the needed providers are configured before the skill is registered.
    """

    LLM = "llm"
    IMAGE = "image"
    SEARCH = "search"
    WEATHER = "weather"
    TTS = "tts"
    STT = "stt"


class SkillLevel(StrEnum):
    """Execution complexity tier for skills."""

    QUERY = "query"
    ACTION = "action"
    WORKFLOW = "workflow"


# Skill names must be lowercase snake_case (matches folder name convention)
_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


class SkillManifest(BaseModel):
    """Validated skill manifest loaded from a skill folder's skill.yaml.

    All fields are populated at load time. prompt_content is read from
    prompt.md if present — no file I/O happens at request time.
    """

    name: str

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        import re

        if not re.match(_NAME_PATTERN, v):
            msg = f"Skill name '{v}' must be lowercase snake_case (e.g. 'weather', 'web_search')"
            raise ValueError(msg)
        return v

    display_name: str
    description: str
    version: str = "1.0"
    author: str = "community"
    level: SkillLevel = SkillLevel.QUERY
    category: str = "general"
    uses: list[SkillCapability] = Field(default_factory=list)
    tool: dict[str, Any]
    prompt_content: str = ""
