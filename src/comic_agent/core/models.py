"""Core data models for the comic pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class StoryDocument:
    """Normalized storyline source content."""

    source_path: str
    raw_text: str
    normalized_text: str


@dataclass(slots=True)
class Scene:
    """A story scene with compact action beats."""

    scene_id: str
    summary: str
    beats: list[str]


@dataclass(slots=True)
class CharacterProfile:
    """Extracted character with traits used in image prompting."""

    name: str
    role: str
    description: str
    visual_traits: list[str]
    speech_style: str


@dataclass(slots=True)
class BubbleSpec:
    """Speech bubble details for a panel."""

    speaker: str
    text: str
    position: str


@dataclass(slots=True)
class SubPanelSpec:
    """Generated sub-panel intent and bubble composition."""

    sub_panel_id: str
    description: str
    prompt: str
    characters_involved: list[str]
    bubbles: list[BubbleSpec]
    background_context_prompt: str | None = None


@dataclass(slots=True)
class PanelSpec:
    """Generated panel containing a fixed set of sub-panels."""

    panel_id: str
    scene_id: str
    subpanels: list[SubPanelSpec]


@dataclass(slots=True)
class PanelArtifact:
    """Materialized sub-panel image file and corresponding parent panel spec."""

    spec: PanelSpec
    sub_panel_id: str
    image_path: str


@dataclass(slots=True)
class ValidationIssue:
    """Validation finding produced by validator/continuity checks."""

    code: str
    message: str
    panel_id: str | None = None


@dataclass(slots=True)
class ValidationResult:
    """Validation result for a single run."""

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass(slots=True)
class RunManifest:
    """Output bundle metadata for a full manager run."""

    manifest_version: str
    run_id: str
    input_file: str
    scenes: list[Scene]
    characters: list[CharacterProfile]
    panel_specs: list[PanelSpec]
    panel_images: list[str]
    panel_pdf: str | None
    continuity_issues: list[ValidationIssue]
    validation: ValidationResult
    revisions_attempted: int

    def to_dict(self) -> dict[str, Any]:
        """Convert dataclass graph into JSON-serializable dict."""

        return asdict(self)


@dataclass(slots=True)
class RunConfig:
    """Runtime configuration collected from CLI flags."""

    input_path: Path
    output_dir: Path
    max_panels: int = 12
    seed: int | None = None
    skip_image_generation: bool = False
    verbose: bool = False
