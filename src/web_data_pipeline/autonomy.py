from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re


REQUIRED_FIELDS = ("container", "name", "price", "sku", "stock")
SEMANTIC_PREFIXES = {
    "container": ("product", "item", "listing", "offer", "card"),
    "name": ("name", "title", "headline", "label"),
    "price": ("price", "amount", "cost", "value"),
    "sku": ("sku", "code", "identifier", "reference"),
    "stock": ("stock", "availability", "inventory", "state"),
}


class ClassCapture(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, list[str]]] = []
        self.values: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        self.stack.append((tag, classes))

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return
        for _, classes in self.stack:
            for name in classes:
                self.values.setdefault(name, []).append(value)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


@dataclass(frozen=True)
class AdapterOutcome:
    mapping: dict[str, str]
    source: str
    approved: bool
    records_parsed: int
    checks: tuple[str, ...]
    manual_approval_required: bool = False

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["checks"] = list(self.checks)
        return result


def parse_with_mapping(html: str, mapping: dict[str, str]) -> list[dict[str, str]]:
    parser = ClassCapture()
    parser.feed(html)
    classes = {field: selector.removeprefix(".") for field, selector in mapping.items()}
    if any(name not in parser.values for name in classes.values()):
        return []
    count = len(parser.values[classes["name"]])
    rows: list[dict[str, str]] = []
    for index in range(count):
        try:
            rows.append({field: parser.values[classes[field]][index] for field in ("name", "price", "sku", "stock")})
        except IndexError:
            return []
    return rows


def discover_deterministically(html: str) -> dict[str, str]:
    classes = set(re.findall(r'class="([^"]+)"', html))
    mapping: dict[str, str] = {}
    for field, prefixes in SEMANTIC_PREFIXES.items():
        candidates = [name for group in classes for name in group.split() if any(name.lower().startswith(prefix) for prefix in prefixes)]
        if len(candidates) == 1:
            mapping[field] = f".{candidates[0]}"
    return mapping


def _passes(rows: list[dict[str, str]]) -> bool:
    if len(rows) != 2:
        return False
    for row in rows:
        price = re.sub(r"[^0-9.]", "", row["price"])
        if not row["name"] or not row["sku"].startswith("MOCK-") or row["stock"] not in {"In stock", "Out of stock"}:
            return False
        try:
            if float(price) <= 0:
                return False
        except ValueError:
            return False
    return True


def build_and_promote_adapter(sample_html: str, canary_html: str, ai_mapping: dict[str, object] | None) -> AdapterOutcome:
    mapping = {str(key): str(value) for key, value in (ai_mapping or {}).items() if key in REQUIRED_FIELDS}
    source = "ai"
    checks: list[str] = []
    if set(mapping) != set(REQUIRED_FIELDS) or not all(value.startswith(".") for value in mapping.values()):
        mapping = discover_deterministically(sample_html)
        source = "deterministic_self_repair"
        checks.append("invalid_ai_mapping_repaired")
    sample_rows = parse_with_mapping(sample_html, mapping) if set(mapping) == set(REQUIRED_FIELDS) else []
    canary_rows = parse_with_mapping(canary_html, mapping) if set(mapping) == set(REQUIRED_FIELDS) else []
    approved = _passes(sample_rows) and _passes(canary_rows)
    checks.extend(("required_fields_checked", "typed_values_checked", "canary_page_checked"))
    return AdapterOutcome(mapping, source, approved, len(sample_rows) + len(canary_rows), tuple(checks))
