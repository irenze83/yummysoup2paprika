"""Command-line interface for yummysoup2paprika."""
from __future__ import annotations

import argparse
from pathlib import Path

from .converter import convert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yummysoup2paprika",
        description="Convert a YummySoup! library to a Paprika Recipe Manager 3 .paprikarecipes archive.",
    )
    parser.add_argument("input", type=Path, help="Extracted .library package or .library.zip archive")
    parser.add_argument("output", type=Path, help="Output .paprikarecipes file")
    parser.add_argument("--limit", type=int, default=None, help="Convert only the first N recipes; useful for testing")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = convert(args.input.expanduser(), args.output.expanduser(), args.limit)
    print("\nConversion complete")
    print(f"Recipes converted:        {report.recipes}")
    print(f"Primary photos included: {report.primary_images}")
    print(f"Secondary photos included: {report.secondary_images}")
    print(f"Missing primary photos:  {report.missing_primary_images}")
    print(f"Errors:                  {report.errors}")
    print(f"Archive created:         {args.output}")


if __name__ == "__main__":
    main()
