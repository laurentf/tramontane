"""Unit tests for the host skill system (manifest, loader, registry)."""

from pathlib import Path
from textwrap import dedent

import pytest

from app.features.hosts.skills._loader import SkillLoader
from app.features.hosts.skills._manifest import SkillLevel, SkillManifest
from app.features.hosts.skills._registry import SkillRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_TOOL = {"name": "t", "description": "d", "parameters": {"type": "object"}}


def _make_manifest(**overrides) -> SkillManifest:
    defaults = {
        "name": "test_skill",
        "display_name": "Test Skill",
        "description": "A test skill",
        "tool": _MINIMAL_TOOL,
    }
    return SkillManifest(**(defaults | overrides))


def _write_skill(
    skill_dir: Path,
    name: str,
    *,
    yaml_content: str | None = None,
    prompt: str | None = None,
) -> Path:
    """Create a skill folder with skill.yaml and optional prompt.md."""
    folder = skill_dir / name
    folder.mkdir(parents=True, exist_ok=True)

    if yaml_content is not None:
        (folder / "skill.yaml").write_text(yaml_content)

    if prompt is not None:
        (folder / "prompt.md").write_text(prompt)

    return folder


_VALID_YAML = dedent("""\
    name: test_skill
    display_name: Test Skill
    description: A test skill
    level: query
    category: utility
    uses:
      - weather
    tool:
      name: test_tool
      description: Test tool
      parameters:
        type: object
        properties:
          location:
            type: string
        required:
          - location
""")


# ---------------------------------------------------------------------------
# SkillManifest tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_manifest_valid_snake_case_name() -> None:
    m = _make_manifest(name="hello_world")
    assert m.name == "hello_world"


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_name",
    ["UpperCase", "has space", "has-hyphen", "9starts_with_digit"],
    ids=["uppercase", "space", "hyphen", "digit_start"],
)
def test_manifest_rejects_invalid_names(bad_name: str) -> None:
    with pytest.raises(ValueError, match="lowercase snake_case"):
        _make_manifest(name=bad_name)


@pytest.mark.unit
@pytest.mark.parametrize("level", ["query", "action", "workflow"])
def test_manifest_valid_levels(level: str) -> None:
    m = _make_manifest(level=level)
    assert m.level == SkillLevel(level)


@pytest.mark.unit
def test_manifest_tool_dict_required() -> None:
    with pytest.raises(ValueError):
        SkillManifest(
            name="no_tool",
            display_name="No Tool",
            description="Missing tool field",
        )


@pytest.mark.unit
def test_manifest_defaults() -> None:
    m = _make_manifest()
    assert m.version == "1.0"
    assert m.author == "community"
    assert m.level == SkillLevel.QUERY
    assert m.prompt_content == ""


# ---------------------------------------------------------------------------
# SkillLoader tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_loader_discovers_skill(tmp_path: Path) -> None:
    _write_skill(tmp_path, "test_skill", yaml_content=_VALID_YAML)
    manifests = SkillLoader(skills_dir=tmp_path).load_all()
    assert "test_skill" in manifests
    assert manifests["test_skill"].display_name == "Test Skill"


@pytest.mark.unit
def test_loader_folder_name_must_match_manifest(tmp_path: Path) -> None:
    _write_skill(tmp_path, "wrong_folder", yaml_content=_VALID_YAML)
    with pytest.raises(ValueError, match="must match folder"):
        SkillLoader(skills_dir=tmp_path).load_all()


@pytest.mark.unit
def test_loader_skips_folders_without_yaml(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    (tmp_path / "orphan_folder").mkdir()
    manifests = SkillLoader(skills_dir=tmp_path).load_all()
    assert manifests == {}
    assert "no skill.yaml" in caplog.text


@pytest.mark.unit
def test_loader_skips_underscore_folders(tmp_path: Path) -> None:
    _write_skill(tmp_path, "_hidden_skill", yaml_content=_VALID_YAML)
    manifests = SkillLoader(skills_dir=tmp_path).load_all()
    assert manifests == {}


@pytest.mark.unit
def test_loader_invalid_yaml_raises(tmp_path: Path) -> None:
    _write_skill(tmp_path, "bad_yaml", yaml_content="name: [unterminated")
    with pytest.raises(ValueError, match="Invalid skill manifest"):
        SkillLoader(skills_dir=tmp_path).load_all()


@pytest.mark.unit
def test_loader_reads_prompt_md(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "test_skill",
        yaml_content=_VALID_YAML,
        prompt="You are a helpful weather bot.",
    )
    manifests = SkillLoader(skills_dir=tmp_path).load_all()
    assert manifests["test_skill"].prompt_content == "You are a helpful weather bot."


@pytest.mark.unit
def test_loader_missing_prompt_md_gives_empty_string(tmp_path: Path) -> None:
    _write_skill(tmp_path, "test_skill", yaml_content=_VALID_YAML)
    manifests = SkillLoader(skills_dir=tmp_path).load_all()
    assert manifests["test_skill"].prompt_content == ""


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_registry_list_skill_names_sorted() -> None:
    manifests = {
        "zeta": _make_manifest(name="zeta"),
        "alpha": _make_manifest(name="alpha"),
    }
    reg = SkillRegistry(manifests)
    assert reg.list_skill_names() == ["alpha", "zeta"]


@pytest.mark.unit
def test_registry_get_manifest_existing() -> None:
    m = _make_manifest(name="weather_bot")
    reg = SkillRegistry({"weather_bot": m})
    assert reg.get_manifest("weather_bot") is m


@pytest.mark.unit
def test_registry_get_manifest_missing_returns_none() -> None:
    reg = SkillRegistry({})
    assert reg.get_manifest("nonexistent") is None


@pytest.mark.unit
def test_registry_get_skill_prompts_returns_content() -> None:
    m = _make_manifest(name="weather_bot")
    m = m.model_copy(update={"prompt_content": "Check the weather."})
    reg = SkillRegistry({"weather_bot": m})
    prompts = reg.get_skill_prompts(["weather_bot"])
    assert prompts == ["Check the weather."]


@pytest.mark.unit
def test_registry_get_skill_prompts_skips_empty() -> None:
    m_empty = _make_manifest(name="empty_skill")
    m_whitespace = _make_manifest(name="ws_skill")
    m_whitespace = m_whitespace.model_copy(update={"prompt_content": "   \n  "})
    reg = SkillRegistry({"empty_skill": m_empty, "ws_skill": m_whitespace})
    assert reg.get_skill_prompts(["empty_skill", "ws_skill"]) == []


@pytest.mark.unit
def test_registry_get_skill_prompts_skips_unknown() -> None:
    m = _make_manifest(name="real_skill")
    m = m.model_copy(update={"prompt_content": "I exist."})
    reg = SkillRegistry({"real_skill": m})
    prompts = reg.get_skill_prompts(["real_skill", "ghost_skill"])
    assert prompts == ["I exist."]


# ---------------------------------------------------------------------------
# Integration: real skills directory
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_real_skills_load_weather_and_web_search() -> None:
    manifests = SkillLoader().load_all()
    assert "weather" in manifests
    assert "web_search" in manifests


@pytest.mark.unit
def test_real_skills_have_prompt_content() -> None:
    manifests = SkillLoader().load_all()
    for name in ("weather", "web_search"):
        assert manifests[name].prompt_content, f"{name} should have non-empty prompt_content"
