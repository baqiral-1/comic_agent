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


def write_panels_pdf(panel_images: list[str], output_pdf_path: Path) -> Path | None:
    """Combine panel images into a single PDF; return path on success."""

    if not panel_images:
        return None

    try:
        from PIL import Image
    except Exception:
        return None

    opened_images: list[Image.Image] = []
    converted_images: list[Image.Image] = []
    try:
        for image_path in panel_images:
            try:
                img = Image.open(image_path)
                opened_images.append(img)
                converted_images.append(img.convert("RGB"))
            except Exception:
                continue
        if not converted_images:
            return None
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        first, rest = converted_images[0], converted_images[1:]
        first.save(output_pdf_path, format="PDF", save_all=True, append_images=rest)
        return output_pdf_path
    finally:
        for img in converted_images:
            img.close()
        for img in opened_images:
            img.close()
