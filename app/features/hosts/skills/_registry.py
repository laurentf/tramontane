"""SkillRegistry — manifest store and prompt retrieval."""

from app.features.hosts.skills._manifest import SkillManifest


class SkillRegistry:
    """Stores loaded skill manifests and provides prompt retrieval.

    Constructed once at startup from SkillLoader.load_all() output.
    Shared as a singleton on app.state.
    """

    def __init__(self, manifests: dict[str, SkillManifest]) -> None:
        self._manifests = manifests

    @property
    def manifests(self) -> dict[str, SkillManifest]:
        return self._manifests

    def get_skill_prompts(self, skill_names: list[str]) -> list[str]:
        """Return prompt.md contents for skills with non-empty content."""
        return [
            self._manifests[name].prompt_content
            for name in skill_names
            if name in self._manifests
            and self._manifests[name].prompt_content.strip()
        ]

    def get_manifest(self, name: str) -> SkillManifest | None:
        return self._manifests.get(name)

    def list_skill_names(self) -> list[str]:
        return sorted(self._manifests.keys())
