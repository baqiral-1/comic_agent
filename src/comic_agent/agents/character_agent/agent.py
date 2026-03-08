"""Character extraction agent."""

from __future__ import annotations

import re
from collections import Counter

from comic_agent.core.models import CharacterProfile, StoryDocument


class CharacterAgent:
    """Finds likely main characters with simple heuristics."""

    _name_pattern = re.compile(r"\b[A-Z][a-z]{2,}\b")

    def run(self, story: StoryDocument) -> list[CharacterProfile]:
        """Extract frequently occurring capitalized names."""

        candidates = self._name_pattern.findall(story.raw_text)
        filtered = [name for name in candidates if name.lower() not in {"the", "and", "but"}]
        counter = Counter(filtered)

        if not counter:
            return [
                CharacterProfile(
                    name="Narrator",
                    role="observer",
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
                    role="protagonist" if not profiles else "supporting",
                    visual_traits=["distinct silhouette", "expressive face"],
                    speech_style="concise",
                )
            )
        return profiles
