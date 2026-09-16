from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai import enrich_product
from .pipeline import load_products, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract supplier product cards into spreadsheet-ready files.")
    parser.add_argument("--input", type=Path, default=Path("data/mock"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--ai", action="store_true", help="Run optional AI enrichment after deterministic validation")
    args = parser.parse_args()
    summary = run_pipeline(args.input, args.output)
    if args.ai:
        products, _ = load_products(args.input.glob("*.html"))
        enriched = [{**product.row(), **enrich_product(product.row())} for product in products]
        (args.output / "ai_enrichment.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        summary["ai_enriched"] = len(enriched)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
