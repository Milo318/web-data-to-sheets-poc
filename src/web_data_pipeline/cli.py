from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract supplier product cards into spreadsheet-ready files.")
    parser.add_argument("--input", type=Path, default=Path("data/mock"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--ai", action="store_true", help="Run optional AI enrichment after deterministic validation")
    args = parser.parse_args()
    summary = run_pipeline(args.input, args.output, with_ai=args.ai)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
