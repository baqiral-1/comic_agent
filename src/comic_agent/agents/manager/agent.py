"""Top-level manager orchestration agent."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from comic_agent.agents.character_agent.agent import CharacterAgent
from comic_agent.agents.continuity_agent.agent import ContinuityAgent
from comic_agent.agents.ingest_agent.agent import IngestAgent
from comic_agent.agents.panel_agent.agent import PanelAgent
from comic_agent.agents.scene_agent.agent import SceneAgent
from comic_agent.agents.style_agent.agent import StyleAgent
from comic_agent.agents.validator_agent.agent import ValidatorAgent
from comic_agent.core.errors import ValidationFailedError
from comic_agent.core.io_utils import new_run_id, write_panels_pdf
from comic_agent.core.models import PanelSpec, RunConfig, RunManifest, ValidationResult
from comic_agent.core.rules import DEFAULT_MANIFEST_VERSION, MAX_IMAGE_RETRY_COUNT

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
        scenes = self.scene_agent.run(story, target_panel_count=config.max_panels)
        characters = self.character_agent.run(story)
        style = self.style_agent.run(scenes)

        panels_dir = config.output_dir / "panels"
        artifacts = self.panel_agent.run(
            scenes=scenes,
            characters=characters,
            style=style,
            output_panels_dir=panels_dir,
            max_panels=config.max_panels,
            skip_image_generation=config.skip_image_generation,
        )
        panel_specs: list[PanelSpec] = []
        seen_panel_ids: set[str] = set()
        for artifact in artifacts:
            if artifact.spec.panel_id in seen_panel_ids:
                continue
            seen_panel_ids.add(artifact.spec.panel_id)
            panel_specs.append(artifact.spec)
        if config.skip_image_generation:
            panel_image_paths: list[str] = []
            panel_pdf_path = None
        else:
            panel_image_paths = [
                str(panels_dir / f"{panel_spec.panel_id}.png") for panel_spec in panel_specs
            ]
            panel_pdf_path = write_panels_pdf(panel_image_paths, config.output_dir / "panels.pdf")

        continuity_issues = self.continuity_agent.run(panel_specs)
        validation, panel_image_paths, panel_pdf_path = self._validate_with_image_retries(
            panel_specs=panel_specs,
            continuity_issues=continuity_issues,
            panel_image_paths=panel_image_paths,
            panel_pdf_path=panel_pdf_path,
            panels_dir=panels_dir,
            output_pdf_path=config.output_dir / "panels.pdf",
            skip_image_generation=config.skip_image_generation,
        )

        revisions_attempted = 0
        if not validation.passed and self._has_non_image_issues(validation):
            revisions_attempted = 1
            LOGGER.info("Validation failed; attempting one revision pass")
            self._revise_panel_specs(panel_specs, validation)
            continuity_issues = self.continuity_agent.run(panel_specs)
            validation, panel_image_paths, panel_pdf_path = self._validate_with_image_retries(
                panel_specs=panel_specs,
                continuity_issues=continuity_issues,
                panel_image_paths=panel_image_paths,
                panel_pdf_path=panel_pdf_path,
                panels_dir=panels_dir,
                output_pdf_path=config.output_dir / "panels.pdf",
                skip_image_generation=config.skip_image_generation,
            )

        manifest = RunManifest(
            manifest_version=DEFAULT_MANIFEST_VERSION,
            run_id=run_id,
            input_file=str(config.input_path),
            scenes=scenes,
            characters=characters,
            panel_specs=panel_specs,
            panel_images=panel_image_paths,
            panel_pdf=str(panel_pdf_path) if panel_pdf_path is not None else None,
            continuity_issues=continuity_issues,
            validation=validation,
            revisions_attempted=revisions_attempted,
        )

        if not validation.passed:
            raise ValidationFailedError("Panel validation failed after one revision.")

        return manifest

    def _validate_with_image_retries(
        self,
        panel_specs: list[PanelSpec],
        continuity_issues: list,
        panel_image_paths: list[str],
        panel_pdf_path: Path | None,
        panels_dir: Path,
        output_pdf_path: Path,
        skip_image_generation: bool,
    ) -> tuple[ValidationResult, list[str], Path | None]:
        """Run validation and regenerate failed panel images up to retry cap."""

        validation = self.validator_agent.run(
            panel_specs,
            continuity_issues,
            panel_images=(
                panel_image_paths
                if (not skip_image_generation and bool(os.getenv("OPENAI_API_KEY")))
                else None
            ),
        )
        image_validation_enabled = not skip_image_generation and bool(os.getenv("OPENAI_API_KEY"))
        if not image_validation_enabled:
            return validation, panel_image_paths, panel_pdf_path

        retries = 0
        failed_panel_ids = self._failed_image_panel_ids(validation)
        while failed_panel_ids and retries < MAX_IMAGE_RETRY_COUNT:
            retries += 1
            LOGGER.info(
                "Retrying %d failed panel image(s) (attempt %d/%d): %s",
                len(failed_panel_ids),
                retries,
                MAX_IMAGE_RETRY_COUNT,
                ", ".join(sorted(failed_panel_ids)),
            )
            if not hasattr(self.panel_agent, "retry_failed_panel_images"):
                LOGGER.warning("Panel agent does not support retry_failed_panel_images; skipping retries.")
                break
            self.panel_agent.retry_failed_panel_images(
                panel_specs=panel_specs,
                output_panels_dir=panels_dir,
                failed_panel_ids=failed_panel_ids,
            )
            panel_image_paths = [str(panels_dir / f"{panel.panel_id}.png") for panel in panel_specs]
            panel_pdf_path = write_panels_pdf(panel_image_paths, output_pdf_path)
            validation = self.validator_agent.run(
                panel_specs,
                continuity_issues,
                panel_images=panel_image_paths,
            )
            failed_panel_ids = self._failed_image_panel_ids(validation)

        return validation, panel_image_paths, panel_pdf_path

    def _failed_image_panel_ids(self, validation: ValidationResult) -> set[str]:
        """Extract failed panel IDs caused by missing/placeholder image validation."""

        failed: set[str] = set()
        for issue in validation.issues:
            if issue.code != "PANEL_IMAGE_MISSING_OR_PLACEHOLDER":
                continue
            if issue.panel_id is None:
                continue
            failed.add(issue.panel_id)
        return failed

    def _has_non_image_issues(self, validation: ValidationResult) -> bool:
        """Return True when validation has issues unrelated to image artifacts."""

        for issue in validation.issues:
            if issue.code != "PANEL_IMAGE_MISSING_OR_PLACEHOLDER":
                return True
        return False

    def _revise_panel_specs(
        self, panel_specs: list[PanelSpec], validation: ValidationResult
    ) -> None:
        """Apply one deterministic correction pass based on violations."""

        for issue in validation.issues:
            if issue.code == "BUBBLE_TEXT_TOO_LONG" and issue.panel_id is not None:
                for panel in panel_specs:
                    if panel.panel_id == issue.panel_id:
                        for subpanel in panel.subpanels:
                            for bubble in subpanel.bubbles:
                                bubble.text = bubble.text[:120]
