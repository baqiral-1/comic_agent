"""Panel planning and image generation agent."""

from __future__ import annotations

import base64
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from comic_agent.agents.style_agent.agent import StyleGuide
from comic_agent.core.io_utils import ensure_panel_image
from comic_agent.core.models import (
    BubbleSpec,
    CharacterProfile,
    PanelArtifact,
    PanelSpec,
    Scene,
    SubPanelSpec,
)
from comic_agent.core.rules import ALLOWED_BUBBLE_POSITIONS
from comic_agent.core.settings import PANEL_MODEL

LOGGER = logging.getLogger(__name__)

PANEL_INFERENCE_PROMPT_SAMPLE = """You are a comic storyboard planner.

Task:
- Infer comic panels from the story scenes and character profiles.
- Each panel MUST contain exactly 4 subpanels that progress the story.
- Keep all output grounded in provided story context.

Output schema (strict JSON only):
{
  "panels": [
    {
      "panel_id": "panel-001",
      "scene_id": "scene-1",
      "subpanels": [
        {
          "sub_panel_id": "panel-001-sub-01",
          "description": "...",
          "prompt": "...",
          "characters_involved": ["Character Name"],
          "bubbles": [
            {
              "speaker": "...",
              "text": "...",
              "position": "top-left|top-right|bottom-left|bottom-right|center"
            }
          ]
        }
      ]
    }
  ]
}

Rules:
- Exactly 4 subpanels per panel.
- Preserve chronological order of events.
- `description` must be concise and visually depictable.
- `prompt` should be image-generation ready and include composition/camera cues.
- Bubble text should be short and readable.
- No markdown, no commentary, no extra keys outside schema.
"""


class PanelAgent:
    """Creates nested panel specs and materializes one image per panel."""

    def __init__(self) -> None:
        self._thread_local = threading.local()

    def run(
        self,
        scenes: list[Scene],
        characters: list[CharacterProfile],
        style: StyleGuide,
        output_panels_dir: Path,
        max_panels: int,
        skip_image_generation: bool = False,
    ) -> list[PanelArtifact]:
        """Generate panel specs (with subpanels) and render panel images."""

        panel_specs = self._infer_panels_with_llm(
            scenes=scenes,
            characters=characters,
            style=style,
            max_panels=max_panels,
        )
        if not panel_specs:
            panel_specs = self._fallback_panels(
                scenes=scenes,
                characters=characters,
                style=style,
                max_panels=max_panels,
            )

        planned: list[tuple[PanelSpec, Path, str]] = []
        for panel in panel_specs:
            image_path = output_panels_dir / f"{panel.panel_id}.png"
            panel_prompt = self._panel_composite_prompt(panel=panel)
            planned.append((panel, image_path, panel_prompt))

        if skip_image_generation:
            return [
                PanelArtifact(
                    spec=panel_spec,
                    sub_panel_id=panel_spec.panel_id,
                    image_path=str(image_path),
                )
                for panel_spec, image_path, _ in planned
            ]

        return self._render_artifacts(planned)

    def _infer_panels_with_llm(
        self,
        scenes: list[Scene],
        characters: list[CharacterProfile],
        style: StyleGuide,
        max_panels: int,
    ) -> list[PanelSpec] | None:
        """Infer panel/subpanel structure via LLM using scene+character context."""

        if not scenes or max_panels <= 0:
            return []

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        character_context = self._character_context(characters)
        scene_blob = self._scene_context(scenes, max_panels=max_panels)

        try:
            client = self._get_openai_client(api_key=api_key)
            response = client.chat.completions.create(
                model=os.getenv("COMIC_AGENT_PANEL_PLANNER_MODEL", "gpt-4.1-mini"),
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": PANEL_INFERENCE_PROMPT_SAMPLE},
                    {
                        "role": "user",
                        "content": (
                            "Generate storyboard panels as strict JSON only.\n\n"
                            f"STYLE:\n- Tone: {style.tone}\n"
                            f"- Palette: {style.palette}\n"
                            f"- Camera language: {style.camera_language}\n\n"
                            f"CHARACTERS:\n{character_context}\n\n"
                            f"SCENES:\n{scene_blob}\n"
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content
            if content is None:
                return None

            payload = json.loads(content)
            raw_panels = payload.get("panels")
            if not isinstance(raw_panels, list):
                return None

            normalized = self._normalize_llm_panels(
                raw_panels=raw_panels,
                scenes=scenes,
                style=style,
                characters=characters,
                max_panels=max_panels,
            )
            return normalized or None
        except Exception as exc:  # pragma: no cover - network/API dependent
            LOGGER.warning("Panel LLM inference failed; using deterministic fallback: %s", exc)
            return None

    def _normalize_llm_panels(
        self,
        raw_panels: list[object],
        scenes: list[Scene],
        style: StyleGuide,
        characters: list[CharacterProfile],
        max_panels: int,
    ) -> list[PanelSpec]:
        """Validate/normalize LLM payload into strongly-typed panel specs."""

        lead_speaker = self._select_lead_speaker(characters)
        character_context = self._character_context(characters)
        scene_lookup = {scene.scene_id: scene for scene in scenes}
        normalized: list[PanelSpec] = []

        for panel_idx, raw_panel in enumerate(raw_panels[:max_panels], start=1):
            if not isinstance(raw_panel, dict):
                continue

            panel_id = f"panel-{panel_idx:03d}"
            scene = scenes[min(panel_idx - 1, len(scenes) - 1)]
            raw_scene_id = raw_panel.get("scene_id")
            if isinstance(raw_scene_id, str) and raw_scene_id in scene_lookup:
                scene = scene_lookup[raw_scene_id]

            raw_subpanels = raw_panel.get("subpanels")
            clean_subpanels: list[SubPanelSpec] = []
            if isinstance(raw_subpanels, list):
                for sub_idx, raw_subpanel in enumerate(raw_subpanels[:4], start=1):
                    normalized_subpanel = self._normalize_llm_subpanel(
                        raw_subpanel=raw_subpanel,
                        panel_id=panel_id,
                        sub_idx=sub_idx,
                        scene=scene,
                        style=style,
                        characters=characters,
                        character_context=character_context,
                        lead_speaker=lead_speaker,
                    )
                    if normalized_subpanel is not None:
                        clean_subpanels.append(normalized_subpanel)

            while len(clean_subpanels) < 4:
                fallback_idx = len(clean_subpanels) + 1
                clean_subpanels.append(
                    self._fallback_subpanel(
                        panel_id=panel_id,
                        sub_idx=fallback_idx,
                        scene=scene,
                        style=style,
                        characters=characters,
                        character_context=character_context,
                        lead_speaker=lead_speaker,
                    )
                )

            normalized.append(
                PanelSpec(panel_id=panel_id, scene_id=scene.scene_id, subpanels=clean_subpanels)
            )

        return normalized

    def _normalize_llm_subpanel(
        self,
        raw_subpanel: object,
        panel_id: str,
        sub_idx: int,
        scene: Scene,
        style: StyleGuide,
        characters: list[CharacterProfile],
        character_context: str,
        lead_speaker: str,
    ) -> SubPanelSpec | None:
        """Normalize one LLM subpanel record."""

        if not isinstance(raw_subpanel, dict):
            return None

        sub_panel_id = f"{panel_id}-sub-{sub_idx:02d}"

        description = raw_subpanel.get("description")
        if not isinstance(description, str) or not description.strip():
            description = self._fallback_beat(scene=scene, sub_idx=sub_idx)
        else:
            description = description.strip()

        bubbles = self._normalize_bubbles(
            raw_bubbles=raw_subpanel.get("bubbles"),
            lead_speaker=lead_speaker,
            fallback_text=description,
        )
        characters_involved = self._normalize_characters_involved(
            raw_characters=raw_subpanel.get("characters_involved"),
            characters=characters,
            bubbles=bubbles,
            description=description,
            fallback_character=lead_speaker,
        )
        dialogue_context = self._dialogue_context(bubbles)

        prompt = raw_subpanel.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            prompt = self._build_prompt(
                style=style,
                scene_summary=scene.summary,
                character_context=character_context,
                beat=description,
                dialogue_context=dialogue_context,
            )
        else:
            prompt = self._append_dialogue_context(prompt.strip(), dialogue_context)

        return SubPanelSpec(
            sub_panel_id=sub_panel_id,
            description=description,
            prompt=prompt,
            characters_involved=characters_involved,
            bubbles=bubbles,
        )

    def _normalize_bubbles(
        self,
        raw_bubbles: object,
        lead_speaker: str,
        fallback_text: str,
    ) -> list[BubbleSpec]:
        """Normalize bubble payload into allowed bubble specs."""

        bubbles: list[BubbleSpec] = []
        if isinstance(raw_bubbles, list):
            for raw_bubble in raw_bubbles[:4]:
                if not isinstance(raw_bubble, dict):
                    continue
                speaker = raw_bubble.get("speaker")
                text = raw_bubble.get("text")
                position = raw_bubble.get("position")

                clean_speaker = speaker.strip() if isinstance(speaker, str) and speaker.strip() else lead_speaker
                clean_text = text.strip() if isinstance(text, str) and text.strip() else fallback_text[:120]
                clean_position = (
                    position.strip().lower()
                    if isinstance(position, str) and position.strip().lower() in ALLOWED_BUBBLE_POSITIONS
                    else "top-right"
                )
                bubbles.append(
                    BubbleSpec(
                        speaker=clean_speaker,
                        text=clean_text[:180],
                        position=clean_position,
                    )
                )

        if bubbles:
            return bubbles

        return [
            BubbleSpec(
                speaker=lead_speaker,
                text=fallback_text[:120],
                position="top-right",
            )
        ]

    def _fallback_panels(
        self,
        scenes: list[Scene],
        characters: list[CharacterProfile],
        style: StyleGuide,
        max_panels: int,
    ) -> list[PanelSpec]:
        """Deterministic panel fallback with 4 subpanels per panel."""

        if not scenes or max_panels <= 0:
            return []

        lead_speaker = self._select_lead_speaker(characters)
        character_context = self._character_context(characters)
        panels: list[PanelSpec] = []

        for panel_idx, scene in enumerate(scenes[:max_panels], start=1):
            panel_id = f"panel-{panel_idx:03d}"
            subpanels: list[SubPanelSpec] = []
            for sub_idx in range(1, 5):
                subpanels.append(
                    self._fallback_subpanel(
                        panel_id=panel_id,
                        sub_idx=sub_idx,
                        scene=scene,
                        style=style,
                        characters=characters,
                        character_context=character_context,
                        lead_speaker=lead_speaker,
                    )
                )
            panels.append(PanelSpec(panel_id=panel_id, scene_id=scene.scene_id, subpanels=subpanels))

        return panels

    def _fallback_subpanel(
        self,
        panel_id: str,
        sub_idx: int,
        scene: Scene,
        style: StyleGuide,
        characters: list[CharacterProfile],
        character_context: str,
        lead_speaker: str,
    ) -> SubPanelSpec:
        """Build one deterministic subpanel."""

        beat = self._fallback_beat(scene=scene, sub_idx=sub_idx)
        bubbles = [
            BubbleSpec(
                speaker=lead_speaker,
                text=beat[:120],
                position="bottom-left" if sub_idx % 2 == 0 else "top-right",
            )
        ]
        characters_involved = self._normalize_characters_involved(
            raw_characters=None,
            characters=characters,
            bubbles=bubbles,
            description=beat,
            fallback_character=lead_speaker,
        )
        dialogue_context = self._dialogue_context(bubbles)
        prompt = self._build_prompt(
            style=style,
            scene_summary=scene.summary,
            character_context=character_context,
            beat=beat,
            dialogue_context=dialogue_context,
        )
        return SubPanelSpec(
            sub_panel_id=f"{panel_id}-sub-{sub_idx:02d}",
            description=beat,
            prompt=prompt,
            characters_involved=characters_involved,
            bubbles=bubbles,
        )

    def _fallback_beat(self, scene: Scene, sub_idx: int) -> str:
        """Pick a scene beat for fallback subpanel construction."""

        if scene.beats:
            return scene.beats[min(sub_idx - 1, len(scene.beats) - 1)]
        return "No beats found"

    def _build_prompt(
        self,
        style: StyleGuide,
        scene_summary: str,
        character_context: str,
        beat: str,
        dialogue_context: str,
    ) -> str:
        """Build image prompt text from style + narrative context."""

        return (
            f"{style.tone} comic panel, {style.palette}, {style.camera_language}. "
            f"Scene context: {scene_summary}. "
            f"Character context: {character_context}. "
            f"Beat: {beat}. "
            f"Dialogue context: {dialogue_context}."
        )

    def _append_dialogue_context(self, prompt: str, dialogue_context: str) -> str:
        """Append dialogue context to prompt unless already present."""

        if "Dialogue context:" in prompt:
            return prompt
        return f"{prompt} Dialogue context: {dialogue_context}."

    def _dialogue_context(self, bubbles: list[BubbleSpec]) -> str:
        """Serialize bubble list into concise dialogue context for prompting."""

        if not bubbles:
            return "No dialogue."
        return " | ".join(f"{bubble.speaker}: {bubble.text}" for bubble in bubbles)

    def _normalize_characters_involved(
        self,
        raw_characters: object,
        characters: list[CharacterProfile],
        bubbles: list[BubbleSpec],
        description: str,
        fallback_character: str,
    ) -> list[str]:
        """Normalize subpanel characters list grounded to known character profiles."""

        known_names = [character.name for character in characters if character.name]
        known_lower = {name.lower(): name for name in known_names}

        ordered: list[str] = []
        if isinstance(raw_characters, list):
            for raw_name in raw_characters:
                if not isinstance(raw_name, str):
                    continue
                candidate = raw_name.strip()
                if not candidate:
                    continue
                canonical = known_lower.get(candidate.lower())
                if canonical and canonical not in ordered:
                    ordered.append(canonical)

        for bubble in bubbles:
            canonical = known_lower.get(bubble.speaker.lower())
            if canonical and canonical not in ordered:
                ordered.append(canonical)

        lowered_text = description.lower()
        for name in known_names:
            if name.lower() in lowered_text and name not in ordered:
                ordered.append(name)

        if ordered:
            return ordered

        fallback = known_lower.get(fallback_character.lower(), fallback_character)
        return [fallback]

    def _scene_context(self, scenes: list[Scene], max_panels: int) -> str:
        """Serialize scenes for panel planning prompt."""

        lines: list[str] = []
        for scene in scenes[:max_panels]:
            lines.append(f"- {scene.scene_id}: {scene.summary}")
            for beat in scene.beats:
                lines.append(f"  - {beat}")
        return "\n".join(lines)

    def _select_lead_speaker(self, characters: list[CharacterProfile]) -> str:
        """Pick a default bubble speaker, prioritizing main-role characters."""

        for character in characters:
            if character.role == "main":
                return character.name
        if characters:
            return characters[0].name
        return "Narrator"

    def _character_context(self, characters: list[CharacterProfile]) -> str:
        """Build concise context string from all character profile fields."""

        if not characters:
            return "No characters provided."

        parts: list[str] = []
        for character in characters:
            traits = ", ".join(character.visual_traits)
            parts.append(
                (
                    f"{character.name} ({character.role}): {character.description} "
                    f"Visual traits: {traits}. Speech style: {character.speech_style}."
                )
            )
        return " ".join(parts)

    def _render_artifacts(
        self,
        planned: list[tuple[PanelSpec, Path, str]],
    ) -> list[PanelArtifact]:
        """Render panel images and preserve artifact ordering."""

        artifacts: list[PanelArtifact] = []
        if not planned:
            return artifacts

        workers = self._image_workers()
        if workers == 1:
            for panel_spec, image_path, panel_prompt in planned:
                self._generate_image(prompt=panel_prompt, output_path=image_path)
                artifacts.append(
                    PanelArtifact(
                        spec=panel_spec,
                        sub_panel_id=panel_spec.panel_id,
                        image_path=str(image_path),
                    )
                )
            return artifacts

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self._generate_image, prompt=panel_prompt, output_path=image_path)
                for _, image_path, panel_prompt in planned
            ]
            for (panel_spec, image_path, _), future in zip(planned, futures, strict=True):
                future.result()
                artifacts.append(
                    PanelArtifact(
                        spec=panel_spec,
                        sub_panel_id=panel_spec.panel_id,
                        image_path=str(image_path),
                    )
                )
        return artifacts

    def _panel_composite_prompt(self, panel: PanelSpec) -> str:
        """Build one combined prompt that renders all four subpanels in a single image."""

        subpanel_sections: list[str] = []
        for idx, subpanel in enumerate(panel.subpanels, start=1):
            characters = ", ".join(subpanel.characters_involved) if subpanel.characters_involved else "None"
            dialogue = self._dialogue_context(subpanel.bubbles)
            subpanel_sections.append(
                (
                    f"Subpanel {idx}: Description: {subpanel.description}. "
                    f"Characters involved: {characters}. "
                    f"Dialogue: {dialogue}. "
                    f"Visual prompt: {subpanel.prompt}"
                )
            )

        return (
            "Create one comic image split into exactly 4 subpanels in a clear 2x2 grid, "
            "reading left-to-right, top-to-bottom. Keep character identity and style consistent across all subpanels. "
            + " ".join(subpanel_sections)
        )

    def _image_workers(self) -> int:
        """Get image worker count from env var."""

        configured = os.getenv("COMIC_AGENT_IMAGE_WORKERS", "1")
        try:
            return max(1, int(configured))
        except ValueError:
            LOGGER.warning("Invalid COMIC_AGENT_IMAGE_WORKERS=%s; using 1", configured)
            return 1

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        """Generate image from prompt; offline fallback writes placeholder PNG."""

        if output_path.exists() and output_path.stat().st_size > 0:
            LOGGER.debug("Reusing existing panel image at %s", output_path)
            return

        LOGGER.debug("Generating panel image for prompt: %s", prompt)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                client = self._get_openai_client(api_key=api_key)
                response = client.images.generate(
                    model=PANEL_MODEL,
                    prompt=prompt,
                    size=os.getenv("COMIC_AGENT_IMAGE_SIZE", "1024x1024"),
                )
                if not response.data:
                    raise ValueError("Image API returned no image data.")
                image_base64 = response.data[0].b64_json
                if image_base64 is None:
                    raise ValueError("Image API did not return base64 content.")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(base64.b64decode(image_base64))
                return
            except Exception as exc:  # pragma: no cover - network/API dependent
                LOGGER.warning("Image generation API failed; using placeholder PNG: %s", exc)

        # Deterministic local execution and tests.
        ensure_panel_image(output_path)

    def _get_openai_client(self, api_key: str):  # noqa: ANN201
        """Get thread-local API client to avoid per-request construction overhead."""

        client = getattr(self._thread_local, "openai_client", None)
        client_api_key = getattr(self._thread_local, "openai_api_key", None)
        if client is not None and client_api_key == api_key:
            return client

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        self._thread_local.openai_client = client
        self._thread_local.openai_api_key = api_key
        return client
