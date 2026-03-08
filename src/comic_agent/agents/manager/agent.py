"""Top-level manager orchestration agent."""

from __future__ import annotations

import logging

from comic_agent.agents.character_agent.agent import CharacterAgent
from comic_agent.agents.continuity_agent.agent import ContinuityAgent
from comic_agent.agents.ingest_agent.agent import IngestAgent
from comic_agent.agents.panel_agent.agent import PanelAgent
from comic_agent.agents.scene_agent.agent import SceneAgent
from comic_agent.agents.style_agent.agent import StyleAgent
from comic_agent.agents.validator_agent.agent import ValidatorAgent
from comic_agent.core.errors import ValidationFailedError
from comic_agent.core.io_utils import new_run_id
from comic_agent.core.models import PanelSpec, RunConfig, RunManifest, ValidationResult
from comic_agent.core.rules import DEFAULT_MANIFEST_VERSION

LOGGER = logging.getLogger(__name__)


class ManagerAgent:
    """Orchestrates the multi-agent comic generation workflow."""

    def __init__(self) -> None:
        self.ingest_agent = IngestAgent()
        self.scene_agent = SceneAgent()
        self.character_agent = CharacterAgent()
        self.style_agent = StyleAgent()
        self.panel_agent = PanelAgent()
        self.continuity_agent = ContinuityAgent()
        self.validator_agent = ValidatorAgent()

    def run(self, config: RunConfig) -> RunManifest:
        """Execute pipeline and return run manifest."""

        LOGGER.info("Starting run for input %s", config.input_path)
        run_id = new_run_id()

        story = self.ingest_agent.run(config.input_path)
        scenes = self.scene_agent.run(story)
        characters = self.character_agent.run(story)
        style = self.style_agent.run(scenes)

        panels_dir = config.output_dir / "panels"
        artifacts = self.panel_agent.run(
            scenes=scenes,
            characters=characters,
            style=style,
            output_panels_dir=panels_dir,
            max_panels=config.max_panels,
        )
        panel_specs = [artifact.spec for artifact in artifacts]

        continuity_issues = self.continuity_agent.run(panel_specs)
        validation = self.validator_agent.run(panel_specs, continuity_issues)

        revisions_attempted = 0
        if not validation.passed:
            revisions_attempted = 1
            LOGGER.info("Validation failed; attempting one revision pass")
            self._revise_panel_specs(panel_specs, validation)
            continuity_issues = self.continuity_agent.run(panel_specs)
            validation = self.validator_agent.run(panel_specs, continuity_issues)

        manifest = RunManifest(
            manifest_version=DEFAULT_MANIFEST_VERSION,
            run_id=run_id,
            input_file=str(config.input_path),
            scenes=scenes,
            characters=characters,
            panel_specs=panel_specs,
            panel_images=[artifact.image_path for artifact in artifacts],
            continuity_issues=continuity_issues,
            validation=validation,
            revisions_attempted=revisions_attempted,
        )

        if not validation.passed:
            raise ValidationFailedError("Panel validation failed after one revision.")

        return manifest

    def _revise_panel_specs(
        self, panel_specs: list[PanelSpec], validation: ValidationResult
    ) -> None:
        """Apply one deterministic correction pass based on violations."""

        for issue in validation.issues:
            if issue.code == "BUBBLE_TEXT_TOO_LONG" and issue.panel_id is not None:
                for panel in panel_specs:
                    if panel.panel_id == issue.panel_id:
                        for bubble in panel.bubbles:
                            bubble.text = bubble.text[:120]
