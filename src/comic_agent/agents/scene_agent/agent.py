"""Scene decomposition agent."""

from __future__ import annotations

import json
import logging
import os

from comic_agent.core.models import Scene, StoryDocument
from comic_agent.core.settings import SCENE_MODEL

LOGGER = logging.getLogger(__name__)

# Sample prompt template for scene classification quality.
# Feel free to tune this wording/rules for your narrative style.
SCENE_CLASSIFICATION_PROMPT_SAMPLE = """You are a story editor creating comic-ready scenes.

Task:
- Infer scene boundaries from the full story.
- Do NOT split purely by punctuation or sentence count.
- Group lines into coherent dramatic units for visual storytelling.

A scene boundary usually happens when one or more of these change:
1) Place/location
2) Time
3) Main objective
4) Primary conflict or stakes
5) Dominant participants

Output rules:
- Return strict JSON only with this schema:
  {"scenes":[{"summary":"...", "beats":["...", "..."]}]}
- 1-3 concise beats per scene.
- Keep each beat concrete and visually depictable.
- Keep summaries as descriptive as possible wihtout exceeding 150 words. The summary should capture the essence of the scene and would be used to generate the panel.
- Preserve story order exactly.
- No markdown, no commentary, no extra keys.
"""


class SceneAgent:
    """Transforms raw storyline text into scene beats."""

    def run(self, story: StoryDocument) -> list[Scene]:
        """Infer compact scenes with an LLM, then fallback deterministically."""

        normalized_text = story.normalized_text.strip()
        if not normalized_text:
            return [Scene(scene_id="scene-1", summary="Empty story", beats=["No beats found"])]

        inferred = self._infer_scenes_with_llm(normalized_text)
        if inferred:
            return inferred

        return self._fallback_sentence_chunks(normalized_text)

    def _infer_scenes_with_llm(self, normalized_text: str) -> list[Scene] | None:
        """Use an LLM to infer scene boundaries and beats."""

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, max_retries=0, timeout=20.0)
            response = client.chat.completions.create(
                model=SCENE_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SCENE_CLASSIFICATION_PROMPT_SAMPLE},
                    {
                        "role": "user",
                        "content": (
                            "Infer scenes from this story and return JSON only.\n\n"
                            f"STORY:\n{normalized_text}"
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content
            if content is None:
                return None
            payload = json.loads(content)
            scenes_payload = payload.get("scenes")
            if not isinstance(scenes_payload, list):
                return None

            scenes: list[Scene] = []
            for idx, raw_scene in enumerate(scenes_payload, start=1):
                if not isinstance(raw_scene, dict):
                    continue
                summary = raw_scene.get("summary")
                beats = raw_scene.get("beats")
                if not isinstance(summary, str) or not isinstance(beats, list):
                    continue
                beat_lines = [beat.strip() for beat in beats if isinstance(beat, str) and beat.strip()]
                if not beat_lines:
                    continue
                scenes.append(
                    Scene(
                        scene_id=f"scene-{idx}",
                        summary=summary.strip() or beat_lines[0],
                        beats=[f"Beat {i + 1}: {beat}" for i, beat in enumerate(beat_lines)],
                    )
                )

            return scenes or None
        except Exception as exc:  # pragma: no cover - network/API dependent
            LOGGER.warning("Scene LLM inference failed; using deterministic fallback: %s", exc)
            return None

    def _fallback_sentence_chunks(self, normalized_text: str) -> list[Scene]:
        """Fallback chunker when LLM inference is unavailable."""

        sentences = [s.strip() for s in normalized_text.replace("\n", " ").split(".") if s.strip()]
        if not sentences:
            return [Scene(scene_id="scene-1", summary="Empty story", beats=["No beats found"])]

        scene_size = 3
        scenes: list[Scene] = []
        for idx in range(0, len(sentences), scene_size):
            chunk = sentences[idx : idx + scene_size]
            scene_id = f"scene-{(idx // scene_size) + 1}"
            summary = chunk[0]
            beats = [f"Beat {i + 1}: {sentence}" for i, sentence in enumerate(chunk)]
            scenes.append(Scene(scene_id=scene_id, summary=summary, beats=beats))
        return scenes
