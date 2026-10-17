"""Probe whether the Gemini API answers at all, without an image.

Run by Anton with his key; it never prints the key:

    uv run --env-file .env python scripts/gemini_probe.py list
    uv run --env-file .env python scripts/gemini_probe.py text

`list` checks the key and whether the model id is available (no generation).
`text` sends one tiny text-only generation request (counts toward the budget).
"""

import os
import sys
import time

from google import genai
from google.genai import types

from l10n_checker.gemini import DEFAULT_MODEL
from l10n_checker.vision import redact


def main() -> int:
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
    key = os.environ.get("GEMINI_API_KEY", "")
    if step not in ("list", "text") or not key:
        print("usage: gemini_probe.py list|text [model]; GEMINI_API_KEY must be set")
        return 1
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1)
        ),
    )
    started = time.monotonic()
    try:
        if step == "list":
            names = sorted(m.name for m in client.models.list() if "flash" in m.name)
            print("flash models:", ", ".join(names))
            print(f"{model} available:", f"models/{model}" in names)
        else:
            response = client.models.generate_content(
                model=model, contents="Reply with the single word OK."
            )
            print("text:", repr(response.text))
            print("model_version:", response.model_version)
            print("usage:", response.usage_metadata)
    except Exception as exc:  # noqa: BLE001 - a probe reports every failure
        print("failed:", redact(f"{type(exc).__name__}: {exc}", (key,)))
    print(f"latency: {time.monotonic() - started:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
