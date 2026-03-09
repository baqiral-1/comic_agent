"""Character extraction agent."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter

from comic_agent.core.models import CharacterProfile, StoryDocument
from comic_agent.core.settings import CHARACTER_MODEL

LOGGER = logging.getLogger(__name__)

CHARACTER_INFERENCE_PROMPT_SAMPLE = """You are a narrative analyst extracting comic-relevant characters from a story.

Task:
- Identify characters that are explicitly named in the storyline.
- Classify each as one of: main, supporting, background.
- Include unnamed characters only if they have a clear, consistent presence and role (e.g., "the guard" who appears in multiple scenes with described traits).

Classification guidance:
- main: central to the story arc, repeatedly drives decisions/conflict.
- supporting: materially affects plot but is not the central driver.
- background: minor presence, limited impact on plot progression.

For each character, provide:
- name: exact name as written in the story.
- role: main | supporting | background.
- description: short character description, max 20 words.
- visual_traits: 2-4 concise visualizable traits useful for comic rendering.
- speech_style: short style descriptor (e.g., concise, formal, emotional, sarcastic).

Output requirements:
- Return strict JSON only.
- Use this exact schema:
  {
    "characters": [
      {
        "name": "string",
        "role": "main|supporting|background",
        "description": "string (max 20 words)",
        "visual_traits": ["string", "..."],
        "speech_style": "string"
      }
    ]
  }
- Preserve story-grounded facts only; do not hallucinate relationships or traits not inferable from text.
- No markdown, no commentary, no extra keys.
"""


class CharacterAgent:
    """Finds likely story characters with LLM inference and deterministic fallback."""

    _name_pattern = re.compile(r"\b[A-Z][a-z]{2,}\b")
    _roles = {"main", "supporting", "background"}
    _default_traits = ["distinct silhouette", "expressive face"]
    _default_timeout_seconds = 60.0

    def run(self, story: StoryDocument) -> list[CharacterProfile]:
        """Infer character profiles via LLM, fallback to heuristic extraction."""

        inferred = self._infer_characters_with_llm(story.normalized_text)
        if inferred is not None:
            return inferred
        return self._fallback_extract_characters(story.raw_text)

    def _infer_characters_with_llm(self, normalized_text: str) -> list[CharacterProfile] | None:
        """Infer character profiles from narrative text using LLM."""

        text = normalized_text.strip()
        if not text:
            return None

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            client = self._get_openai_client(api_key=api_key)
            response = client.chat.completions.create(
                model=CHARACTER_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": CHARACTER_INFERENCE_PROMPT_SAMPLE},
                    {"role": "user", "content": f"Infer characters from this story.\n\nSTORY:\n{text}"},
                ],
            )
            content = response.choices[0].message.content
            if content is None:
                return None
            payload = json.loads(content)
            raw_characters = payload.get("characters")
            if not isinstance(raw_characters, list):
                return None

            profiles: list[CharacterProfile] = []
            for raw_character in raw_characters:
                profile = self._normalize_character(raw_character)
                if profile is not None:
                    profiles.append(profile)
            if profiles:
                return profiles
            return None
        except Exception as exc:  # pragma: no cover - network/API dependent
            LOGGER.warning("Character LLM inference failed; using deterministic fallback: %s", exc)
            return None

    def _normalize_character(self, raw_character: object) -> CharacterProfile | None:
        """Validate and normalize one raw character payload object."""

        if not isinstance(raw_character, dict):
            return None

        name = raw_character.get("name")
        role = raw_character.get("role")
        description = raw_character.get("description")
        visual_traits = raw_character.get("visual_traits")
        speech_style = raw_character.get("speech_style")
        if not isinstance(name, str) or not name.strip():
            return None
        clean_name = name.strip()

        if not isinstance(role, str):
            return None
        clean_role = role.strip().lower()
        if clean_role not in self._roles:
            return None

        if isinstance(description, str) and description.strip():
            clean_description = self._truncate_words(description.strip(), 20)
        else:
            clean_description = self._default_description(clean_name, clean_role)

        if isinstance(visual_traits, list):
            clean_traits = [trait.strip() for trait in visual_traits if isinstance(trait, str) and trait.strip()]
        else:
            clean_traits = []
        if not clean_traits:
            clean_traits = self._default_traits
        if len(clean_traits) > 4:
            clean_traits = clean_traits[:4]

        if isinstance(speech_style, str) and speech_style.strip():
            clean_speech_style = speech_style.strip()
        else:
            clean_speech_style = "concise"

        return CharacterProfile(
            name=clean_name,
            role=clean_role,
            description=clean_description,
            visual_traits=clean_traits,
            speech_style=clean_speech_style,
        )

    def _fallback_extract_characters(self, raw_text: str) -> list[CharacterProfile]:
        """Extract frequently occurring capitalized names using regex fallback."""

        candidates = self._name_pattern.findall(raw_text)
        filtered = [name for name in candidates if name.lower() not in {"the", "and", "but"}]
        counter = Counter(filtered)

        if not counter:
            return [
                CharacterProfile(
                    name="Narrator",
                    role="background",
                    description="Neutral observer describing events and transitions.",
                    visual_traits=["neutral clothing", "subtle expression"],
                    speech_style="descriptive",
                )
            ]

        top = counter.most_common(4)
        profiles: list[CharacterProfile] = []
        for name, _ in top:
            profiles.append(
                CharacterProfile(
                    name=name,
                    role="main" if not profiles else "supporting",
                    description=self._default_description(name, "main" if not profiles else "supporting"),
                    visual_traits=["distinct silhouette", "expressive face"],
                    speech_style="concise",
                )
            )
        return profiles

    def _default_description(self, name: str, role: str) -> str:
        """Create a concise default description capped at 20 words."""

        template = f"{name} is a {role} character in the storyline."
        return self._truncate_words(template, 20)

    def _truncate_words(self, text: str, max_words: int) -> str:
        """Trim text to at most `max_words` words."""

        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words])

    def _get_openai_client(self, api_key: str):  # noqa: ANN201
        """Build OpenAI API client."""

        from openai import OpenAI

        return OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=self._character_timeout_seconds(),
        )

    def _character_timeout_seconds(self) -> float:
        """Resolve character inference timeout from env with safe fallback."""

        configured = os.getenv("COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS")
        if not configured:
            return self._default_timeout_seconds
        try:
            parsed = float(configured)
            if parsed <= 0:
                raise ValueError
            return parsed
        except ValueError:
            LOGGER.warning(
                "Invalid COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS=%s; using %.1f",
                configured,
                self._default_timeout_seconds,
            )
            return self._default_timeout_seconds
