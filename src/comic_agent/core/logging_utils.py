"""Logging helpers for console + file logs."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(output_dir: Path, verbose: bool) -> None:
    """Configure logging handlers for current run."""

    output_dir.mkdir(parents=True, exist_ok=True)
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(output_dir / "run.log", mode="w", encoding="utf-8"),
        ],
    )
