"""Optional narrative-only local Ollama adapter; all quantities remain computed in Python."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def check_ollama(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=2.0) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"connected": True, "models": [item.get("name") for item in data.get("models", [])]}
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return {"connected": False, "models": [], "message": str(exc)[:180]}


def explain_with_ollama(base_url: str, model: str, facts: dict) -> str | None:
    prompt = (
        "Summarize this fictional hospital supply-chain scenario in two concise sentences. "
        "Use only the supplied facts and say it is simulated. Do not change or calculate quantities. Facts: "
        + json.dumps(facts, ensure_ascii=False)
    )
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=6.0) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = str(result.get("response", "")).strip()
        return text[:700] if text else None
    except (OSError, urllib.error.URLError, ValueError, TimeoutError):
        return None
