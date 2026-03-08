"""Ingest agent implementation."""

from __future__ import annotations

from pathlib import Path

from comic_agent.core.io_utils import read_text_file
from comic_agent.core.models import StoryDocument


class IngestAgent:
    """Reads and normalizes storyline content."""

    def run(self, input_path: Path) -> StoryDocument:
        """Load the storyline file and normalize whitespace."""

        raw_text = read_text_file(input_path)
        normalized = " ".join(raw_text.split())
        return StoryDocument(
            source_path=str(input_path),
            raw_text=raw_text,
            normalized_text=normalized,
        )
