"""Scene agent tests."""

from comic_agent.agents.scene_agent.agent import SceneAgent
from comic_agent.core.models import StoryDocument


def test_scene_agent_splits_sentences_into_scenes() -> None:
    """Scene agent should chunk sentences into scene groups."""

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
