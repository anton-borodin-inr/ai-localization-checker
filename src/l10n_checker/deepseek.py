"""Narrow paid vision adapter for the explicitly approved issue 10 experiment."""

import base64
import json
import platform
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from l10n_checker.local_model import NoRedirect
from l10n_checker.small_text import PROMPT
from l10n_checker.vision import ProviderError, ProviderResponse, redact

ENDPOINT = "https://api.deepseek.com"
MODEL = "deepseek-flash"
INPUT_BOUND = 32768
OUTPUT_BOUND = 8192
CAP = Decimal("0.25")
RESERVATION = (
    Decimal(INPUT_BOUND) * Decimal("0.30") + OUTPUT_BOUND * Decimal("1.20")
) / 1_000_000
SCHEMA_VERSION = "issue-10-deepseek-json-wrapper-v1"


def format_prompt(schema):
    return (
        PROMPT + "\nReturn only a JSON object conforming to this schema. "
        "Do not add fields or markdown. Synthetic format example only: "
        '{"findings": [], "readings": [{"text_seen": "Example", "region": "center"}]}. '
        "The example is not screenshot content. JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    )


def input_bound(prompt):
    # Official downloadable tokenizer: identity normalization, byte-level BPE,
    # no prefix insertion. Each UTF-8 byte needs at most one text token before
    # merges. Allow 8192 text bytes, 1024 documented image tokens and 23552
    # additional framing tokens. The live usage must also satisfy this bound.
    if len(prompt.encode("utf-8")) > 8192:
        raise ValueError("Prompt exceeds the approved conservative input bound")
    return INPUT_BOUND


def peak_cost(usage):
    """Conservative peak tariff estimate, not a provider billing receipt."""
    if not isinstance(usage, dict):
        return None
    names = ("prompt_tokens", "completion_tokens")
    if any(type(usage.get(n)) is not int or usage[n] < 0 for n in names):
        return None
    total, output = (usage[n] for n in names)
    hit = usage.get("prompt_cache_hit_tokens", 0)
    if type(hit) is not int or not 0 <= hit <= total:
        return None
    if total > INPUT_BOUND or output > OUTPUT_BOUND:
        raise ValueError("Returned usage exceeds the reserved token bound")
    miss = total - hit
    return (
        miss * Decimal("0.30") + hit * Decimal("0.006") + output * Decimal("1.20")
    ) / 1_000_000


class DeepSeekProvider:
    name = "deepseek"
    model = MODEL
    sdk_version = "stdlib-urllib/python-" + platform.python_version()

    def __init__(self, api_key, *, opener=None):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is missing; no network request sent")
        self._key = api_key
        self._opener = opener or build_opener(ProxyHandler({}), NoRedirect())
        self.settings = {
            "endpoint": ENDPOINT + "/chat/completions",
            "temperature": 0,
            "max_tokens": OUTPUT_BOUND,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "image_detail": "original",
            "timeout_s": 1800,
            "transport_retries": 0,
            "redirects": False,
            "proxies": False,
            "input_token_reservation": INPUT_BOUND,
            "peak_usd_reservation": str(RESERVATION),
        }

    def _request(self, path, payload=None):
        if path not in ("/chat/completions", "/models", "/user/balance"):
            raise ValueError("Unapproved DeepSeek endpoint")
        req = Request(
            ENDPOINT + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": "Bearer " + self._key,
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )
        try:
            with self._opener.open(
                req, timeout=1800 if payload is not None else 30
            ) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = redact(exc.read().decode("utf-8", errors="replace"), (self._key,))
            raise ProviderError(
                "rate_limited" if exc.code == 429 else "api_error",
                f"HTTP {exc.code}",
                {"http_status": exc.code, "body": body},
            ) from None
        except (TimeoutError, URLError, OSError, UnicodeDecodeError) as exc:
            timeout = isinstance(exc, TimeoutError) or isinstance(
                getattr(exc, "reason", None), TimeoutError
            )
            raise ProviderError(
                "timeout" if timeout else "api_error", type(exc).__name__
            ) from None
        body = redact(body, (self._key,))
        try:
            data = json.loads(body)
        except ValueError:
            raise ProviderError(
                "api_error", "Non-JSON API response", {"body": body}
            ) from None
        if not isinstance(data, dict):
            raise ProviderError("api_error", "API response is not an object")
        return data

    def models(self):
        data = self._request("/models")
        rows = data.get("data")
        if not isinstance(rows, list) or not any(
            m.get("id") == MODEL for m in rows if isinstance(m, dict)
        ):
            raise ValueError("Approved vision model absent from model discovery")
        return {
            "data": [
                {k: m[k] for k in ("id", "object", "owned_by") if k in m}
                for m in rows
                if isinstance(m, dict)
            ]
        }

    def balance(self):
        data = self._request("/user/balance")
        rows = data.get("balance_infos", [])
        usd = next((r for r in rows if r.get("currency") == "USD"), None)
        if not data.get("is_available") or usd is None:
            raise ValueError("Available USD balance cannot be established")
        amount = Decimal(usd["total_balance"])
        if not amount.is_finite() or amount < 0:
            raise ValueError("Invalid USD balance")
        return amount

    def generate(self, image, mime_type, prompt):
        input_bound(prompt)
        raw = self._request(
            "/chat/completions",
            {
                "model": MODEL,
                **{
                    k: self.settings[k]
                    for k in (
                        "temperature",
                        "max_tokens",
                        "stream",
                        "thinking",
                        "response_format",
                    )
                },
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,"
                                    + base64.b64encode(image).decode("ascii"),
                                    "detail": "original",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
        )
        if raw.get("model") not in (
            MODEL,
            "deepseek-v4.1-flash-1017",
            "DeepSeek-V4.1-Flash-1017",
        ):
            raise ProviderError("api_error", "Unexpected response model", raw)
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("empty_response", "No choices", raw)
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise ProviderError("incomplete_response", "Non-stop finish_reason", raw)
        message = choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("empty_response", "Missing content", raw)
        return ProviderResponse(
            message["content"], raw, raw.get("model"), raw.get("usage")
        )
