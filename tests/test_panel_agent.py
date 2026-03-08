"""Panel agent tests."""

from __future__ import annotations

from pathlib import Path

from comic_agent.agents.panel_agent.agent import PanelAgent
from comic_agent.agents.style_agent.agent import StyleGuide
from comic_agent.core.models import CharacterProfile, Scene


def test_panel_agent_uses_all_character_fields_in_prompt_and_speaker(  # noqa: ANN001
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Panel prompts should include complete character context and main speaker selection."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    scenes = [Scene(scene_id="scene-1", summary="A market confrontation", beats=["Beat event happens"])]
    characters = [
        CharacterProfile(
            name="Sidekick",
            role="supporting",
            description="Loyal friend observing events carefully.",
            visual_traits=["green scarf", "round glasses"],
            speech_style="measured",
        ),
        CharacterProfile(
            name="Hero",
            role="main",
            description="Determined lead confronting the antagonist in public.",
            visual_traits=["red coat", "confident stance"],
            speech_style="assertive",
        ),
    ]
    style = StyleGuide(
        palette="high-contrast ink with warm highlights",
        tone="adventure",
        camera_language="dynamic medium shots",
    )

    artifacts = PanelAgent().run(
        scenes=scenes,
        characters=characters,
        style=style,
        output_panels_dir=tmp_path / "panels",
        max_panels=5,
    )

    assert len(artifacts) == 1
    spec = artifacts[0].spec
    assert spec.bubbles[0].speaker == "Hero"
    assert "Character context:" in spec.prompt
    assert "Sidekick (supporting): Loyal friend observing events carefully." in spec.prompt
    assert "Visual traits: green scarf, round glasses." in spec.prompt
    assert "Speech style: measured." in spec.prompt
    assert "Hero (main): Determined lead confronting the antagonist in public." in spec.prompt
    assert "Visual traits: red coat, confident stance." in spec.prompt
    assert "Speech style: assertive." in spec.prompt
