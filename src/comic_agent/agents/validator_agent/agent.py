"""Panel validator agent."""

from __future__ import annotations

from comic_agent.core.models import PanelSpec, ValidationIssue, ValidationResult
from comic_agent.core.rules import (
    ALLOWED_BUBBLE_POSITIONS,
    MAX_BUBBLE_TEXT_LENGTH,
    MAX_BUBBLES_PER_PANEL,
    MIN_PANELS,
)


class ValidatorAgent:
    """Enforces panel-level composition rules."""

    def run(
        self, panel_specs: list[PanelSpec], continuity_issues: list[ValidationIssue]
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

        return ValidationResult(passed=not issues, issues=issues)
