from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
import urllib.request

from .autonomy import build_and_promote_adapter


@dataclass(frozen=True)
class LayoutCase:
    case_id: str
    sample_html: str
    canary_html: str
    truth: dict[str, str]


PREFIX_SETS = [
    ("product", "name", "price", "sku", "stock"),
    ("item", "title", "amount", "code", "availability"),
    ("listing", "headline", "cost", "identifier", "inventory"),
    ("offer", "label", "value", "reference", "state"),
    ("card", "name", "amount", "code", "stock"),
]


def _page(classes: tuple[str, ...], case_id: str, offset: int) -> str:
    container, name, price, sku, stock = classes
    rows = []
    for item in range(2):
        number = offset + item
        rows.append(
            f'<article class="{container}"><span class="{sku}">MOCK-{case_id}-{number}</span>'
            f'<h3 class="{name}">Synthetic Product {number}</h3><span class="{stock}">{"In stock" if number % 2 else "Out of stock"}</span>'
            f'<strong class="{price}">EUR {49 + number}.90</strong></article>'
        )
    return "<main>" + "".join(rows) + "</main>"


def generate_cases(count: int) -> list[LayoutCase]:
    cases: list[LayoutCase] = []
    for index in range(count):
        base = PREFIX_SETS[index % len(PREFIX_SETS)]
        suffix = f"-{index:03d}"
        classes = tuple(prefix + suffix for prefix in base)
        truth = dict(zip(("container", "name", "price", "sku", "stock"), (f".{name}" for name in classes)))
        case_id = f"LAYOUT-{index:03d}"
        cases.append(LayoutCase(case_id, _page(classes, case_id, index * 4), _page(classes, case_id, index * 4 + 2), truth))
    return cases


def ask_ollama(batch: list[LayoutCase], model: str, url: str) -> tuple[dict[str, dict[str, object]], dict[str, int]]:
    items = [{"case_id": case.case_id, "html": case.sample_html} for case in batch]
    prompt = (
        "For every HTML sample identify CSS class selectors for container, name, price, sku, and stock. "
        "Return JSON with a results array. Each item must contain case_id and mapping. mapping must contain exactly "
        "container, name, price, sku, stock and every selector must begin with a dot. Do not omit cases.\n\n" + json.dumps(items)
    )
    payload = {"model": model, "stream": False, "format": "json", "keep_alive": "10m", "options": {"temperature": 0, "num_predict": 2200}, "messages": [{"role": "system", "content": "You configure web extraction adapters. Output JSON only."}, {"role": "user", "content": prompt}]}
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = json.load(response)
    parsed = json.loads(raw["message"]["content"])
    results = parsed.get("results", parsed if isinstance(parsed, list) else [])
    return {str(item.get("case_id")): item.get("mapping", {}) for item in results if isinstance(item, dict)}, {"prompt_tokens": int(raw.get("prompt_eval_count", 0)), "completion_tokens": int(raw.get("eval_count", 0))}


def run(count: int, model: str, url: str, batch_size: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    cases = generate_cases(count)
    proposals: dict[str, dict[str, object]] = {}
    prompt_tokens = completion_tokens = 0
    started = time.perf_counter()
    for index in range(0, count, batch_size):
        result, usage = ask_ollama(cases[index:index + batch_size], model, url)
        proposals.update(result)
        prompt_tokens += usage["prompt_tokens"]
        completion_tokens += usage["completion_tokens"]
    rows: list[dict[str, object]] = []
    for case in cases:
        proposal = proposals.get(case.case_id)
        direct = proposal == case.truth
        outcome = build_and_promote_adapter(case.sample_html, case.canary_html, proposal)
        rows.append({"case_id": case.case_id, "ai_direct_pass": direct, "decision_source": outcome.source, "records_validated": outcome.records_parsed, "approved": outcome.approved, "final_mapping": outcome.mapping})
    elapsed = time.perf_counter() - started
    approved = sum(row["approved"] for row in rows)
    direct = sum(row["ai_direct_pass"] for row in rows)
    summary = {
        "benchmark": "autonomous_web_adapter_v1", "live_model": True, "model": model,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "synthetic_data": True,
        "benchmark_cases": count, "minimum_required_cases": 100,
        "ai_direct_passed": direct, "ai_direct_pass_rate_percent": round(direct / count * 100, 2),
        "final_approved": approved, "approval_rate_percent": round(approved / count * 100, 2),
        "required_approval_rate_percent": 95.0,
        "acceptance_gate_passed": count >= 100 and approved / count > 0.95,
        "manual_approvals_required": 0,
        "automatic_self_repairs": sum(row["decision_source"] == "deterministic_self_repair" for row in rows),
        "records_validated": sum(int(row["records_validated"]) for row in rows),
        "elapsed_seconds": round(elapsed, 3), "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "case_generator_sha256": sha256("".join(case.sample_html for case in cases).encode()).hexdigest(),
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=120)
    parser.add_argument("--model", default="granite4.1:3b")
    parser.add_argument("--url", default="http://localhost:11434/api/chat")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("proof/autonomous-benchmark.json"))
    parser.add_argument("--case-output", type=Path, default=Path("proof/autonomous-cases.jsonl"))
    args = parser.parse_args()
    if args.cases < 100:
        raise SystemExit("At least 100 cases are required")
    summary, rows = run(args.cases, args.model, args.url, args.batch_size)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    args.case_output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["acceptance_gate_passed"]:
        raise SystemExit("Acceptance gate failed")


if __name__ == "__main__":
    main()
