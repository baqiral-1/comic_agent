"""Validation failure behavior tests."""

from pathlib import Path

import pytest

from comic_agent.agents.manager.agent import ManagerAgent
from comic_agent.core.errors import ValidationFailedError
from comic_agent.core.models import BubbleSpec, PanelArtifact, PanelSpec, RunConfig


class InvalidPanelAgent:
    """Panel agent test double that returns invalid bubble position."""

    def run(self, scenes, characters, style, output_panels_dir, max_panels):  # noqa: ANN001
        panel_path = output_panels_dir / "panel-001.png"
        output_panels_dir.mkdir(parents=True, exist_ok=True)
        panel_path.write_bytes(b"invalid")
        spec = PanelSpec(
            panel_id="panel-001",
            scene_id="scene-1",
            description="invalid panel",
            prompt="prompt",
            bubbles=[BubbleSpec(speaker="A", text="hello", position="unknown")],
        )
        return [PanelArtifact(spec=spec, image_path=str(panel_path))]


def test_manager_raises_when_validation_still_fails(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Manager should raise after one revision if issues remain."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    story_path = tmp_path / "story.txt"
    story_path.write_text("A goes to town.", encoding="utf-8")

    manager = ManagerAgent()
    manager.panel_agent = InvalidPanelAgent()

    config = RunConfig(input_path=story_path, output_dir=tmp_path / "out")

    with pytest.raises(ValidationFailedError):
        manager.run(config)
