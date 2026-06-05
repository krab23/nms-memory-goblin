"""Command-line entrypoint for nms-memory-goblin."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nms-memory-goblin",
        description="Future No Man's Sky memory utility. Memory scanning is not implemented yet.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="nms-memory-goblin 0.1.0",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
