"""Validator agent tests."""

from pathlib import Path

from comic_agent.agents.validator_agent.agent import ValidatorAgent
from comic_agent.core.models import BubbleSpec, PanelSpec, SubPanelSpec


def test_validator_flags_bubble_violations() -> None:
    """Validator should report long text and invalid position."""

    panel = PanelSpec(
        panel_id="panel-001",
        scene_id="scene-1",
        subpanels=[
            SubPanelSpec(
                sub_panel_id="panel-001-sub-01",
                description="desc",
                prompt="prompt",
                characters_involved=["Alice"],
                bubbles=[
                    BubbleSpec(
                        speaker="Alice",
                        text="x" * 250,
                        position="invalid",
                    )
                ],
            )
        ],
    )

    result = ValidatorAgent().run([panel], continuity_issues=[])

    assert result.passed is False
    codes = {issue.code for issue in result.issues}
    assert "BUBBLE_TEXT_TOO_LONG" in codes
    assert "INVALID_BUBBLE_POSITION" in codes


def test_validator_flags_subpanel_without_speech_or_context() -> None:
    """Validator should fail subpanels that provide neither bubbles nor context."""

    panel = PanelSpec(
        panel_id="panel-001",
        scene_id="scene-1",
        subpanels=[
            SubPanelSpec(
                sub_panel_id="panel-001-sub-01",
                description="silent subpanel without context",
                prompt="prompt",
                characters_involved=["Alice"],
                bubbles=[],
            )
        ],
    )

    result = ValidatorAgent().run([panel], continuity_issues=[])
    codes = {issue.code for issue in result.issues}
    assert "SUBPANEL_MISSING_SPEECH_OR_CONTEXT" in codes


def test_validator_flags_placeholder_panel_images(tmp_path: Path) -> None:
    """Validator should report placeholder/missing panel image artifacts."""

    panel = PanelSpec(
        panel_id="panel-001",
        scene_id="scene-1",
        subpanels=[
            SubPanelSpec(
                sub_panel_id="panel-001-sub-01",
                description="desc",
                prompt="prompt",
                characters_involved=["Alice"],
                bubbles=[BubbleSpec(speaker="Alice", text="ok", position="top-right")],
            )
        ],
    )
    panel_image = tmp_path / "panel-001.png"
    panel_image.write_bytes(b"x" * 68)

    result = ValidatorAgent().run(
        [panel],
        continuity_issues=[],
        panel_images=[str(panel_image)],
    )
    codes = {issue.code for issue in result.issues}
    assert "PANEL_IMAGE_MISSING_OR_PLACEHOLDER" in codes
