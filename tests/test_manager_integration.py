"""Integration tests for manager + CLI behaviors."""

from pathlib import Path

from comic_agent.agents.manager.agent import ManagerAgent
from comic_agent.core.io_utils import write_manifest
from comic_agent.core.models import RunConfig


def test_manager_creates_manifest_and_panels(tmp_path: Path) -> None:
    """Manager run should generate panel images and manifest data."""

    story_path = tmp_path / "story.txt"
    story_path.write_text(
        "Lina finds a map. She meets Omar. They enter a cave. They discover a relic.",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    config = RunConfig(input_path=story_path, output_dir=output_dir, max_panels=6, verbose=False)

    manifest = ManagerAgent().run(config)
    manifest_path = write_manifest(output_dir, manifest)

    assert manifest.validation.passed is True
    assert manifest_path.exists()
    assert (output_dir / "panels").exists()
    assert len(manifest.panel_images) >= 1
    assert Path(manifest.panel_images[0]).exists()
