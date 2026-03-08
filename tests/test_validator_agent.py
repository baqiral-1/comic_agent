"""Validator agent tests."""

from comic_agent.agents.validator_agent.agent import ValidatorAgent
from comic_agent.core.models import BubbleSpec, PanelSpec


def test_validator_flags_bubble_violations() -> None:
    """Validator should report long text and invalid position."""

    panel = PanelSpec(
        panel_id="panel-001",
        scene_id="scene-1",
        description="desc",
        prompt="prompt",
        bubbles=[
            BubbleSpec(
                speaker="Alice",
                text="x" * 250,
                position="invalid",
            )
        ],
    )

    result = ValidatorAgent().run([panel], continuity_issues=[])

    assert result.passed is False
    codes = {issue.code for issue in result.issues}
    assert "BUBBLE_TEXT_TOO_LONG" in codes
    assert "INVALID_BUBBLE_POSITION" in codes
