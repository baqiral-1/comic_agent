"""CLI for comic-agent pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from comic_agent.agents.manager.agent import ManagerAgent
from comic_agent.core.errors import ValidationFailedError
from comic_agent.core.io_utils import write_manifest
from comic_agent.core.logging_utils import configure_logging
from comic_agent.core.models import RunConfig

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(prog="comic-agent", description="Storyline to comic generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the comic generation pipeline")
    run_parser.add_argument("--input", required=True, help="Path to storyline text file")
    run_parser.add_argument("--output", required=True, help="Output directory")
    run_parser.add_argument("--max-panels", type=int, default=12, help="Maximum panel count")
    run_parser.add_argument("--seed", type=int, default=None, help="Optional random seed")
    run_parser.add_argument(
        "--skip-image-generation",
        action="store_true",
        help="Skip panel image generation and produce specs/manifest only",
    )
    run_parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def run_command(args: argparse.Namespace) -> int:
    """Execute the `run` subcommand."""

    output_dir = Path(args.output)
    configure_logging(output_dir=output_dir, verbose=bool(args.verbose))

    config = RunConfig(
        input_path=Path(args.input),
        output_dir=output_dir,
        max_panels=int(args.max_panels),
        seed=args.seed,
        skip_image_generation=bool(args.skip_image_generation),
        verbose=bool(args.verbose),
    )

    manager = ManagerAgent()
    try:
        manifest = manager.run(config)
    except ValidationFailedError as exc:
        LOGGER.error("Run failed validation: %s", exc)
        return 2

    manifest_path = write_manifest(output_dir=output_dir, manifest=manifest)
    LOGGER.info("Run complete. Manifest written to %s", manifest_path)
    return 0


def main() -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        return run_command(args)
    parser.error(f"Unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
