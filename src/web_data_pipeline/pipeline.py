from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .ai import enrich_product
from .scraper import Product, parse_products


FIELDS = ["sku", "name", "category", "price_eur", "in_stock", "rating", "source"]


def load_products(paths: Iterable[Path]) -> tuple[list[Product], int]:
    seen: dict[str, Product] = {}
    duplicates = 0
    for path in sorted(paths):
        for product in parse_products(path.read_text(encoding="utf-8"), path.name):
            if product.sku in seen:
                duplicates += 1
            seen[product.sku] = product
    return sorted(seen.values(), key=lambda item: item.sku), duplicates


def export_csv(products: list[Product], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(product.row() for product in products)


def export_xlsx(products: list[Product], destination: Path) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.worksheet.table import Table, TableStyleInfo
    except ImportError as exc:
        raise RuntimeError("Install the project dependencies to export XLSX files") from exc
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(FIELDS)
    for product in products:
        row = product.row()
        sheet.append([row[field] for field in FIELDS])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    widths = {"A": 14, "B": 34, "C": 20, "D": 14, "E": 12, "F": 10, "G": 18}
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width
    if products:
        table = Table(displayName="Products", ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)


def run_pipeline(input_dir: Path, output_dir: Path, with_ai: bool = False) -> dict[str, int | str]:
    paths = list(input_dir.glob("*.html"))
    products, duplicates = load_products(paths)
    export_csv(products, output_dir / "products.csv")
    export_xlsx(products, output_dir / "products.xlsx")
    summary: dict[str, int | str] = {
        "input_files": len(paths),
        "unique_products": len(products),
        "duplicates_resolved": duplicates,
        "invalid_rows": 0,
        "output": str(output_dir),
    }
    if with_ai:
        enriched = [{**product.row(), **enrich_product(product.row())} for product in products]
        (output_dir / "ai_enrichment.json").write_text(json.dumps(enriched, indent=2), encoding="utf-8")
        summary["ai_enriched"] = len(enriched)
    return summary
