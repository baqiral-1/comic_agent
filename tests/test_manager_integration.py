"""Integration tests for manager + CLI behaviors."""

from pathlib import Path

from comic_agent.agents.manager.agent import ManagerAgent
from comic_agent.core.io_utils import write_manifest
from comic_agent.core.models import RunConfig, Scene


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

    def run(self, story):  # noqa: ANN001
        _ = story
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
