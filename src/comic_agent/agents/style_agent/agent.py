"""Style synthesis agent."""

from __future__ import annotations

from dataclasses import dataclass

from comic_agent.core.models import Scene


@dataclass(slots=True)
class StyleGuide:
    """Global style directions for panel generation."""

    palette: str
    tone: str
    camera_language: str


class StyleAgent:
    """Builds consistent visual direction for all panels."""

    def run(self, scenes: list[Scene]) -> StyleGuide:
        """Infer a style profile from overall scene mood."""

        dramatic = any(
            "fight" in beat.lower() or "danger" in beat.lower() for s in scenes for beat in s.beats
        )
        tone = "dramatic" if dramatic else "adventure"
        return StyleGuide(
            palette="high-contrast ink with warm highlights",
            tone=tone,
            camera_language="dynamic medium shots with occasional close-ups",
        )
