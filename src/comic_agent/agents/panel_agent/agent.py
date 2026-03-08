"""Panel planning and image generation agent."""

from __future__ import annotations

import base64
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from comic_agent.agents.style_agent.agent import StyleGuide
from comic_agent.core.io_utils import ensure_panel_image
from comic_agent.core.models import BubbleSpec, CharacterProfile, PanelArtifact, PanelSpec, Scene
from comic_agent.core.settings import PANEL_MODEL

LOGGER = logging.getLogger(__name__)


class PanelAgent:
    """Creates panel specs and materializes panel image files."""

    def __init__(self) -> None:
        self._thread_local = threading.local()

    def run(
        self,
        scenes: list[Scene],
        characters: list[CharacterProfile],
        style: StyleGuide,
        output_panels_dir: Path,
        max_panels: int,
    ) -> list[PanelArtifact]:
        """Generate panel prompts and image placeholders."""

        planned: list[tuple[PanelSpec, Path]] = []
        panel_index = 1

        lead_speaker = characters[0].name if characters else "Narrator"
        for scene in scenes:
            for beat in scene.beats:
                if panel_index > max_panels:
                    return self._render_artifacts(planned)

                panel_id = f"panel-{panel_index:03d}"
                prompt = (
                    f"{style.tone} comic panel, {style.palette}, {style.camera_language}. "
                    f"Scene context: {scene.summary}. Beat: {beat}."
                )
                bubbles = [
                    BubbleSpec(
                        speaker=lead_speaker,
                        text=beat[:120],
                        position="bottom-left" if panel_index % 2 == 0 else "top-right",
                    )
                ]
                spec = PanelSpec(
                    panel_id=panel_id,
                    scene_id=scene.scene_id,
                    description=beat,
                    prompt=prompt,
                    bubbles=bubbles,
                )

                image_path = output_panels_dir / f"{panel_id}.png"
                planned.append((spec, image_path))
                panel_index += 1

        return self._render_artifacts(planned)

    def _render_artifacts(self, planned: list[tuple[PanelSpec, Path]]) -> list[PanelArtifact]:
        """Render panel images and preserve artifact ordering."""

        artifacts: list[PanelArtifact] = []
        if not planned:
            return artifacts

        workers = self._image_workers()
        if workers == 1:
            for spec, image_path in planned:
                self._generate_image(prompt=spec.prompt, output_path=image_path)
                artifacts.append(PanelArtifact(spec=spec, image_path=str(image_path)))
            return artifacts

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self._generate_image, prompt=spec.prompt, output_path=image_path)
                for spec, image_path in planned
            ]
            for (spec, image_path), future in zip(planned, futures, strict=True):
                future.result()
                artifacts.append(PanelArtifact(spec=spec, image_path=str(image_path)))
        return artifacts

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
