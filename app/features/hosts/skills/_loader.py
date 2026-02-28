"""Skill auto-discovery, manifest validation, and loading.

Discovery pattern:
  1. yaml.safe_load (NEVER yaml.load — YAML RCE prevention)
  2. Pydantic typed model construction

Both steps happen at startup. Errors are fatal (ValueError) — an invalid
manifest must never be silently ignored.
"""

import logging
from pathlib import Path

import yaml

from app.features.hosts.skills._manifest import SkillManifest

logger = logging.getLogger(__name__)


class SkillLoader:
    """Discovers and validates skill folders in the skills directory.

    A skill folder is any non-hidden subdirectory of skills_dir that
    contains a skill.yaml file. Folders starting with '_' are skipped
    (e.g. __pycache__).

    Usage:
        loader = SkillLoader()
        manifests = loader.load_all()  # dict[skill_name, SkillManifest]
    """

    SKILLS_DIR: Path = Path(__file__).parent

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir if skills_dir is not None else self.SKILLS_DIR

    def load_all(self) -> dict[str, SkillManifest]:
        """Discover and load all valid skill manifests.

        Returns:
            dict mapping skill name -> SkillManifest.

        Raises:
            ValueError: If any manifest fails validation.
        """
        loaded: dict[str, SkillManifest] = {}

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue

            manifest_path = skill_dir / "skill.yaml"
            if not manifest_path.exists():
                logger.warning("Skill folder %s has no skill.yaml, skipping", skill_dir.name)
                continue

            try:
                # Step 1: yaml.safe_load — NEVER yaml.load (YAML RCE prevention)
                with open(manifest_path) as f:
                    raw = yaml.safe_load(f)

                # Step 2: Pydantic typed model
                manifest = SkillManifest(**raw)

                # Step 3: Enforce name == folder name
                if manifest.name != skill_dir.name:
                    raise ValueError(
                        f"Manifest name '{manifest.name}' must match folder "
                        f"name '{skill_dir.name}'"
                    )

                # Step 4: Read prompt.md at load time (no file I/O per request)
                prompt_path = skill_dir / "prompt.md"
                if prompt_path.exists():
                    manifest = manifest.model_copy(
                        update={"prompt_content": prompt_path.read_text().strip()}
                    )

                loaded[manifest.name] = manifest
                logger.info("Loaded skill: %s (level=%s)", manifest.name, manifest.level)

            except Exception as e:
                raise ValueError(f"Invalid skill manifest in {skill_dir.name}: {e}") from e

        logger.info("Skill discovery complete: %d skill(s) loaded", len(loaded))
        return loaded
