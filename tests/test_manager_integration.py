"""Integration tests for manager + CLI behaviors."""

from pathlib import Path

import pytest

from comic_agent.agents.manager.agent import ManagerAgent
from comic_agent.core.errors import ValidationFailedError
from comic_agent.core.io_utils import write_manifest
from comic_agent.core.models import BubbleSpec, PanelArtifact, PanelSpec, RunConfig, Scene, SubPanelSpec


def test_manager_creates_manifest_and_panels(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Manager run should generate panel images and manifest data."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

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
    assert (output_dir / "panels.pdf").exists()
    assert len(manifest.panel_images) >= 1
    assert Path(manifest.panel_images[0]).exists()
    assert manifest.panel_pdf == str(output_dir / "panels.pdf")


class LLMStyleSceneAgent:
    """Test double that mimics inferred scene output from an LLM."""

    def run(self, story, target_panel_count=None):  # noqa: ANN001
        _ = (story, target_panel_count)
        return [
            Scene(
                scene_id="scene-1",
                summary="Crowded house tension rises",
                beats=[
                    "Neighbor explains the cramped family living conditions.",
                    "Nasruddin tells him to move chickens into the house.",
                ],
            ),
            Scene(
                scene_id="scene-2",
                summary="Relief after escalating discomfort",
                beats=[
                    "After adding more animals, chaos peaks and sleep becomes impossible.",
                    "Nasruddin tells him to move all animals out, restoring relief.",
                ],
            ),
        ]


def test_manager_consumes_llm_style_scene_output(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Manager should consume scene summaries/beats from LLM-style scene output."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    story_path = tmp_path / "story.txt"
    story_path.write_text("placeholder", encoding="utf-8")

    output_dir = tmp_path / "out"
    config = RunConfig(input_path=story_path, output_dir=output_dir, max_panels=10, verbose=False)

    manager = ManagerAgent()
    manager.scene_agent = LLMStyleSceneAgent()

    manifest = manager.run(config)

    assert manifest.validation.passed is True
    assert len(manifest.scenes) == 2
    assert len(manifest.panel_specs) == 2
    assert manifest.panel_specs[0].scene_id == "scene-1"
    assert len(manifest.panel_specs[0].subpanels) == 4
    assert "Neighbor explains" in manifest.panel_specs[0].subpanels[0].description
    assert Path(manifest.panel_images[0]).exists()
    assert manifest.panel_pdf == str(output_dir / "panels.pdf")
    assert Path(manifest.panel_pdf).exists()


def test_manager_can_skip_image_generation(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Manager run can skip image generation while still producing panel specs."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    story_path = tmp_path / "story.txt"
    story_path.write_text("Lina finds a map. She meets Omar.", encoding="utf-8")

    output_dir = tmp_path / "out"
    config = RunConfig(
        input_path=story_path,
        output_dir=output_dir,
        max_panels=4,
        skip_image_generation=True,
        verbose=False,
    )

    manifest = ManagerAgent().run(config)

    assert manifest.validation.passed is True
    assert len(manifest.panel_specs) >= 1
    assert manifest.panel_images == []
    assert manifest.panel_pdf is None
    assert not (output_dir / "panels.pdf").exists()


class RetryableFailurePanelAgent:
    """Panel agent double that starts with a placeholder image then succeeds on retry."""

    def __init__(self) -> None:
        self.retry_attempts = 0

    def run(  # noqa: ANN001
        self,
        scenes,
        characters,
        style,
        output_panels_dir,
        max_panels,
        skip_image_generation=False,
    ):
        _ = (scenes, characters, style, max_panels, skip_image_generation)
        output_panels_dir.mkdir(parents=True, exist_ok=True)
        panel_path = output_panels_dir / "panel-001.png"
        panel_path.write_bytes(b"x" * 68)
        spec = PanelSpec(
            panel_id="panel-001",
            scene_id="scene-1",
            subpanels=[
                SubPanelSpec(
                    sub_panel_id="panel-001-sub-01",
                    description="valid subpanel",
                    prompt="prompt",
                    characters_involved=["A"],
                    bubbles=[BubbleSpec(speaker="A", text="hello", position="top-right")],
                )
            ],
        )
        return [PanelArtifact(spec=spec, sub_panel_id="panel-001-sub-01", image_path=str(panel_path))]

    def retry_failed_panel_images(self, panel_specs, output_panels_dir, failed_panel_ids):  # noqa: ANN001
        _ = panel_specs
        self.retry_attempts += 1
        for panel_id in failed_panel_ids:
            path = output_panels_dir / f"{panel_id}.png"
            path.write_bytes(b"real-image-bytes" * 200)


class AlwaysPlaceholderPanelAgent(RetryableFailurePanelAgent):
    """Panel agent double that keeps returning placeholder output on every retry."""

    def retry_failed_panel_images(self, panel_specs, output_panels_dir, failed_panel_ids):  # noqa: ANN001
        _ = panel_specs
        self.retry_attempts += 1
        for panel_id in failed_panel_ids:
            path = output_panels_dir / f"{panel_id}.png"
            path.write_bytes(b"x" * 68)


def test_manager_retries_failed_panel_images_from_validation(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    """Manager should retry failed panel image artifacts and pass validation."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    story_path = tmp_path / "story.txt"
    story_path.write_text("A goes to town.", encoding="utf-8")

    manager = ManagerAgent()
    retry_agent = RetryableFailurePanelAgent()
    manager.panel_agent = retry_agent

    manifest = manager.run(RunConfig(input_path=story_path, output_dir=tmp_path / "out"))

    assert manifest.validation.passed is True
    assert retry_agent.retry_attempts == 1
    assert Path(manifest.panel_images[0]).stat().st_size > 68


def test_manager_stops_failed_image_retries_at_max_three(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    """Manager should cap image regeneration retries at three attempts."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    story_path = tmp_path / "story.txt"
    story_path.write_text("A goes to town.", encoding="utf-8")

    manager = ManagerAgent()
    retry_agent = AlwaysPlaceholderPanelAgent()
    manager.panel_agent = retry_agent

    with pytest.raises(ValidationFailedError):
        manager.run(RunConfig(input_path=story_path, output_dir=tmp_path / "out"))

    assert retry_agent.retry_attempts == 3
