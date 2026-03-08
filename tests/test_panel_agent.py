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
    assert artifacts[0].image_path.endswith("panel-001.png")
    spec = artifacts[0].spec
    assert len(spec.subpanels) == 4
    first_subpanel = spec.subpanels[0]
    assert first_subpanel.bubbles[0].speaker == "Hero"
    assert first_subpanel.characters_involved == ["Hero"]
    assert "Character context:" in first_subpanel.prompt
    assert "Dialogue context:" in first_subpanel.prompt
    assert "Hero: Beat event happens" in first_subpanel.prompt
    assert "Sidekick (supporting): Loyal friend observing events carefully." in first_subpanel.prompt
    assert "Visual traits: green scarf, round glasses." in first_subpanel.prompt
    assert "Speech style: measured." in first_subpanel.prompt
    assert "Hero (main): Determined lead confronting the antagonist in public." in first_subpanel.prompt
    assert "Visual traits: red coat, confident stance." in first_subpanel.prompt
    assert "Speech style: assertive." in first_subpanel.prompt

    second_subpanel = spec.subpanels[1]
    assert second_subpanel.bubbles == []
    assert second_subpanel.background_context_prompt
    assert "Do not render speech bubbles in this subpanel." in second_subpanel.prompt
