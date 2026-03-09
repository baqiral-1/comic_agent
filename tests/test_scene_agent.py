"""Scene agent tests."""

from comic_agent.agents.scene_agent.agent import SCENE_CLASSIFICATION_PROMPT_SAMPLE, SceneAgent
from comic_agent.core.models import StoryDocument


def test_scene_agent_uses_fallback_chunking_without_api_key(monkeypatch) -> None:  # noqa: ANN001
    """Scene agent should fall back to deterministic chunking without API key."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    story = StoryDocument(
        source_path="story.txt",
        raw_text="A starts. B continues. C escalates. D resolves.",
        normalized_text="A starts. B continues. C escalates. D resolves.",
    )
    scenes = SceneAgent().run(story)

    assert len(scenes) == 2
    assert scenes[0].scene_id == "scene-1"
    assert len(scenes[0].beats) == 3
    assert scenes[1].scene_id == "scene-2"
    assert len(scenes[1].beats) == 1


def test_scene_prompt_sample_mentions_scene_boundaries() -> None:
    """Prompt sample should explicitly describe scene boundary criteria."""

    prompt = SCENE_CLASSIFICATION_PROMPT_SAMPLE.lower()
    assert "scene boundary" in prompt
    assert "location" in prompt
    assert "time" in prompt
    assert "soft pacing guideline" in prompt
    assert "speech dialogue or clear background context" in prompt


def test_scene_agent_fallback_respects_target_panel_count(monkeypatch) -> None:  # noqa: ANN001
    """Fallback chunking should align scene count with requested panel target."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    story = StoryDocument(
        source_path="story.txt",
        raw_text="A. B. C. D. E. F.",
        normalized_text="A. B. C. D. E. F.",
    )
    scenes = SceneAgent().run(story, target_panel_count=2)

    assert len(scenes) == 2


def test_scene_user_prompt_infers_when_target_not_supplied() -> None:
    """Scene prompt should request inference when no target panel count is provided."""

    prompt = SceneAgent()._scene_user_prompt(
        normalized_text="A short story.",
        target_panel_count=None,
    )
    assert "No target panel count was supplied" in prompt
    assert "TARGET_PANEL_COUNT" not in prompt


def test_scene_user_prompt_treats_target_as_guideline() -> None:
    """Prompt should frame target panel count as non-strict guidance."""

    prompt = SceneAgent()._scene_user_prompt(
        normalized_text="A short story.",
        target_panel_count=5,
    )
    assert "soft pacing guideline" in prompt
    assert "Keep scene quality over strict counting" in prompt
    assert "speech dialogue or clear background context" in prompt
