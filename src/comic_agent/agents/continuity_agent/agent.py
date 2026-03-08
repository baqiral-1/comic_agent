"""Cross-panel continuity checker."""

from __future__ import annotations

from comic_agent.core.models import PanelSpec, ValidationIssue


class ContinuityAgent:
    """Checks lightweight continuity assumptions across adjacent panels."""

    def run(self, panel_specs: list[PanelSpec]) -> list[ValidationIssue]:
        """Return continuity findings."""

        issues: list[ValidationIssue] = []
        for previous, current in zip(panel_specs, panel_specs[1:], strict=False):
            if previous.scene_id == current.scene_id:
                continue
            if "No beats found" in current.description:
                issues.append(
                    ValidationIssue(
                        code="CONTINUITY_EMPTY_SCENE",
                        message="Scene transition introduces empty beat.",
                        panel_id=current.panel_id,
                    )
                )
        return issues
