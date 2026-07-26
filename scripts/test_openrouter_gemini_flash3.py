#!/usr/bin/env python3
"""Smoke-test Gemini 3 Flash through OpenRouter.

Usage:
  1. Fill OPENROUTER_API_KEY below, or set env var OPENROUTER_API_KEY.
  2. Run: python scripts/test_openrouter_gemini_flash3.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


OPENROUTER_API_KEY = ""
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")


def _api_key() -> str:
    return OPENROUTER_API_KEY.strip() or os.getenv("OPENROUTER_API_KEY", "").strip()


def main() -> int:
    api_key = _api_key()
    if not api_key:
        print(
            "Missing API key. Fill OPENROUTER_API_KEY in this script, "
            "or run with OPENROUTER_API_KEY=your_key.",
            file=sys.stderr,
        )
        return 2

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise API smoke-test assistant.",
            },
            {
                "role": "user",
                "content": "Reply with one short sentence confirming Gemini Flash 3 is reachable.",
            },
        ],
        "temperature": 0.2,
        "max_tokens": 80,
    }

    request = urllib.request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Math Book Translator OpenRouter Smoke Test",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"OpenRouter request failed: HTTP {exc.code}", file=sys.stderr)
        print(body, file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"OpenRouter request failed: {exc.reason}", file=sys.stderr)
        return 1

    message = data.get("choices", [{}])[0].get("message", {})
    content = (message.get("content") or "").strip()

    print(f"Model: {data.get('model', MODEL)}")
    print(f"Response: {content}")
    if data.get("usage"):
        print(f"Usage: {json.dumps(data['usage'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
