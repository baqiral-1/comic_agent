#!/usr/bin/env python3
"""Emit a commit message with one summary line and bullet points."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Format a commit message as one summary line plus bullet points."
    )
    parser.add_argument("--summary", required=True, help="Single-line commit summary")
    parser.add_argument(
        "--bullet",
        action="append",
        default=[],
        help="Bullet point text. Repeat up to 5 times.",
    )
    parser.add_argument(
        "--max-bullets",
        type=int,
        default=5,
        help="Maximum number of bullets to emit (default: 5).",
    )
    parser.add_argument(
        "--issue-url",
        default=None,
        help="Full GitHub issue URL to append as a closing line.",
    )
    return parser


def normalize_line(value: str) -> str:
    return " ".join(value.strip().split())


def main() -> int:
    args = build_parser().parse_args()
    summary = normalize_line(args.summary)
    if not summary:
        print("Summary cannot be empty.", file=sys.stderr)
        return 2

    bullets = [normalize_line(item) for item in args.bullet if normalize_line(item)]
    bullets = bullets[: max(0, args.max_bullets)]
    issue_url = normalize_line(args.issue_url) if args.issue_url else None

    print(summary)
    if bullets:
        print()
        for item in bullets:
            print(f"- {item}")
    if issue_url:
        print()
        print(f"Closes {issue_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
