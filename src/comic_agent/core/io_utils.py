"""File and serialization helpers."""

from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path

from comic_agent.core.models import RunManifest

_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+X4j8AAAAASUVORK5CYII="
)


def read_text_file(path: Path) -> str:
    """Read UTF-8 text from file."""

    return path.read_text(encoding="utf-8")


def write_manifest(output_dir: Path, manifest: RunManifest) -> Path:
    """Write run metadata as JSON."""

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return manifest_path


def new_run_id() -> str:
    """Create deterministic-enough run identifier."""

    return uuid.uuid4().hex[:12]


def ensure_panel_image(path: Path) -> None:
    """Write a tiny placeholder PNG for local/offline execution."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(_ONE_PIXEL_PNG))
