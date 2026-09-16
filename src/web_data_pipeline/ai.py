from __future__ import annotations

import json
import os
import urllib.request


SYSTEM_PROMPT = """You enrich already validated product data. Return JSON only with keys
normalized_category and merchandising_note. Do not change factual fields. The note must be
one short sentence and may only use the supplied product data."""


def enrich_product(product: dict[str, object]) -> dict[str, str]:
    """Stage 2: optional live LLM enrichment through an OpenAI-compatible endpoint."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set LLM_API_KEY before using --ai")
    base_url = os.environ.get("LLM_API_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(product, sort_keys=True)},
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        body = json.load(response)
    result = json.loads(body["choices"][0]["message"]["content"])
    if set(result) != {"normalized_category", "merchandising_note"}:
        raise ValueError(f"Unexpected AI response shape: {result}")
    return result
