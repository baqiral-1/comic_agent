"""Panel validator agent."""

from __future__ import annotations

from pathlib import Path

from comic_agent.core.models import PanelSpec, ValidationIssue, ValidationResult
from comic_agent.core.rules import (
    ALLOWED_BUBBLE_POSITIONS,
    PLACEHOLDER_PANEL_IMAGE_BYTES,
    MAX_BUBBLE_TEXT_LENGTH,
    MAX_BUBBLES_PER_PANEL,
    MIN_PANELS,
)


class ValidatorAgent:
    """Enforces panel-level composition rules."""

    def run(
        self,
        panel_specs: list[PanelSpec],
        continuity_issues: list[ValidationIssue],
        panel_images: list[str] | None = None,
    ) -> ValidationResult:
        """Validate generated panel specs against rule constants."""

        issues: list[ValidationIssue] = list(continuity_issues)
        if len(panel_specs) < MIN_PANELS:
            issues.append(
                ValidationIssue(
                    code="PANEL_COUNT_TOO_LOW",
                    message=f"At least {MIN_PANELS} panel is required.",
                )
            )

        for panel in panel_specs:
            for subpanel in panel.subpanels:
                if not subpanel.bubbles and not (subpanel.background_context_prompt or "").strip():
                    issues.append(
                        ValidationIssue(
                            code="SUBPANEL_MISSING_SPEECH_OR_CONTEXT",
                            message="Subpanel must include bubbles or background context prompt.",
                            panel_id=panel.panel_id,
                        )
                    )
                if len(subpanel.bubbles) > MAX_BUBBLES_PER_PANEL:
                    issues.append(
                        ValidationIssue(
                            code="TOO_MANY_BUBBLES",
                            message=f"Subpanel exceeds {MAX_BUBBLES_PER_PANEL} bubbles.",
                            panel_id=panel.panel_id,
                        )
                    )
                for bubble in subpanel.bubbles:
                    if len(bubble.text) > MAX_BUBBLE_TEXT_LENGTH:
                        issues.append(
                            ValidationIssue(
                                code="BUBBLE_TEXT_TOO_LONG",
                                message=f"Bubble text exceeds {MAX_BUBBLE_TEXT_LENGTH} characters.",
                                panel_id=panel.panel_id,
                            )
                        )
                    if bubble.position not in ALLOWED_BUBBLE_POSITIONS:
                        issues.append(
                            ValidationIssue(
                                code="INVALID_BUBBLE_POSITION",
                                message=f"Bubble position '{bubble.position}' is not allowed.",
                                panel_id=panel.panel_id,
                            )
                        )

        if panel_images is not None:
            panel_image_lookup: dict[str, str] = {}
            for image_path in panel_images:
                panel_id = Path(image_path).stem
                if panel_id.startswith("panel-"):
                    panel_image_lookup[panel_id] = image_path

            for panel in panel_specs:
                image_path = panel_image_lookup.get(panel.panel_id)
                if image_path is None:
                    issues.append(
                        ValidationIssue(
                            code="PANEL_IMAGE_MISSING_OR_PLACEHOLDER",
                            message=f"Panel image missing for {panel.panel_id}.",
                            panel_id=panel.panel_id,
                        )
                    )
                    continue

                path = Path(image_path)
                if not path.exists() or path.stat().st_size == PLACEHOLDER_PANEL_IMAGE_BYTES:
                    issues.append(
                        ValidationIssue(
                            code="PANEL_IMAGE_MISSING_OR_PLACEHOLDER",
                            message=f"Panel image missing or placeholder for {panel.panel_id}.",
                            panel_id=panel.panel_id,
                        )
                    )

        return ValidationResult(passed=not issues, issues=issues)
