"""Scene decomposition agent."""

from __future__ import annotations

from comic_agent.core.models import Scene, StoryDocument


class SceneAgent:
    """Transforms raw storyline text into scene beats."""

    def run(self, story: StoryDocument) -> list[Scene]:
        """Split storyline into compact scene chunks."""

        sentences = [s.strip() for s in story.raw_text.replace("\n", " ").split(".") if s.strip()]
        if not sentences:
            return [Scene(scene_id="scene-1", summary="Empty story", beats=["No beats found"])]

        scene_size = 3
        scenes: list[Scene] = []
        for idx in range(0, len(sentences), scene_size):
            chunk = sentences[idx : idx + scene_size]
            scene_id = f"scene-{(idx // scene_size) + 1}"
            summary = chunk[0][:120]
            beats = [f"Beat {i + 1}: {sentence}" for i, sentence in enumerate(chunk)]
            scenes.append(Scene(scene_id=scene_id, summary=summary, beats=beats))
        return scenes
