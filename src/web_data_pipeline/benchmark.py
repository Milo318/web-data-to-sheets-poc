from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from .scraper import parse_products


def benchmark(fixture: Path, repetitions: int = 250) -> dict[str, object]:
    html = fixture.read_text(encoding="utf-8")
    expected = len(parse_products(html, fixture.name))
    samples: list[float] = []
    for _ in range(repetitions):
        started = perf_counter()
        parsed = parse_products(html, fixture.name)
        samples.append((perf_counter() - started) * 1000)
        if len(parsed) != expected:
            raise AssertionError("Non-deterministic record count")
    elapsed = sum(samples)
    return {
        "fixture": fixture.name,
        "synthetic_data": True,
        "runs": repetitions,
        "records_per_run": expected,
        "records_processed": repetitions * expected,
        "median_latency_ms": round(median(samples), 3),
        "throughput_records_per_second": round((repetitions * expected) / (elapsed / 1000), 1),
        "record_count_consistency_percent": 100.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("data/mock/supplier-a.html"))
    parser.add_argument("--runs", type=int, default=250)
    parser.add_argument("--output", type=Path, default=Path("proof/benchmark.json"))
    args = parser.parse_args()
    result = benchmark(args.fixture, args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
