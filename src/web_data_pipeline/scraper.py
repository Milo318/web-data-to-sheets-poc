from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price_eur: Decimal
    in_stock: bool
    rating: float
    source: str

    def row(self) -> dict[str, str | float | bool]:
        row = asdict(self)
        row["price_eur"] = f"{self.price_eur:.2f}"
        return row


class ProductHTMLParser(HTMLParser):
    """Purpose-built parser for a stable supplier-card contract."""

    def __init__(self, source: str) -> None:
        super().__init__()
        self.source = source
        self.current: dict[str, str] | None = None
        self.field: str | None = None
        self.products: list[Product] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "article" and "product" in classes:
            self.current = {"sku": attributes.get("data-sku") or ""}
            return
        if self.current is None:
            return
        if tag == "h2":
            self.field = "name"
        elif tag == "span":
            for candidate in ("category", "price", "stock", "rating"):
                if candidate in classes:
                    self.field = candidate
                    break

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.field and data.strip():
            self.current[self.field] = self.current.get(self.field, "") + data.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "span"}:
            self.field = None
        if tag == "article" and self.current is not None:
            self.products.append(_to_product(self.current, self.source))
            self.current = None


def _to_product(raw: dict[str, str], source: str) -> Product:
    missing = [key for key in ("sku", "name", "category", "price", "stock", "rating") if not raw.get(key)]
    if missing:
        raise ValueError(f"Missing required fields {missing} in {source}")
    normalized_price = re.sub(r"[^0-9,.-]", "", raw["price"]).replace(",", "")
    try:
        price = Decimal(normalized_price)
        rating = float(raw["rating"])
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid numeric value in {source}: {raw}") from exc
    if price < 0 or not 0 <= rating <= 5:
        raise ValueError(f"Value outside accepted range in {source}: {raw}")
    stock_text = raw["stock"].strip().lower()
    if stock_text not in {"in stock", "out of stock"}:
        raise ValueError(f"Unexpected stock value {raw['stock']!r} in {source}")
    return Product(
        sku=raw["sku"].strip(),
        name=raw["name"].strip(),
        category=raw["category"].strip(),
        price_eur=price,
        in_stock=stock_text == "in stock",
        rating=rating,
        source=source,
    )


def parse_products(html: str, source: str = "memory") -> list[Product]:
    parser = ProductHTMLParser(source)
    parser.feed(html)
    return parser.products
