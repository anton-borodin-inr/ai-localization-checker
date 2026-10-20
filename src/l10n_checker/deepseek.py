"""DeepSeek adapter (D-034). The only module that talks to the DeepSeek API."""

import base64
import json
from decimal import Decimal

import httpx

from l10n_checker.vision import ModelOutput, ProviderError, ProviderResponse, redact

BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
MAX_TOKENS = 4096
DEFAULT_TIMEOUT_S = 120

# JSON object mode does not enforce a schema, so the schema goes into the prompt
# and the response is still validated strictly by ModelOutput. Bump the version
# whenever WRAPPER changes.
WRAPPER_VERSION = "deepseek-json-object-v1"
WRAPPER = (
    "\nReturn only a JSON object that conforms to this JSON Schema, "
    "with no other fields and no Markdown:\n"
)

# Snapshot of the published tariff, as recorded for #29 on the same date.
TARIFF = {
    "source": "https://api-docs.deepseek.com/quick_start/pricing/",
    "verified_date": "2026-10-20",
    "model": MODEL,
    "currency": "USD",
    "peak_per_million_tokens": {
        "input_cache_hit": "0.006",
        "input_cache_miss": "0.30",
        "output": "1.20",
    },
    "off_peak_multiplier": "0.5",
}


def schema_text() -> str:
    return json.dumps(
        ModelOutput.model_json_schema(), ensure_ascii=False, separators=(",", ":")
    )


def estimate_cost(usage: dict | None) -> dict | None:
    """Tariff-based estimate from returned usage; not a billing receipt."""
    if not isinstance(usage, dict):
        return None
    counts = {
        name: usage.get(name)
        for name in (
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "completion_tokens",
        )
    }
    if any(type(n) is not int or n < 0 for n in counts.values()):
        return None
    rates = {k: Decimal(v) for k, v in TARIFF["peak_per_million_tokens"].items()}
    peak = (
        counts["prompt_cache_hit_tokens"] * rates["input_cache_hit"]
        + counts["prompt_cache_miss_tokens"] * rates["input_cache_miss"]
        + counts["completion_tokens"] * rates["output"]
    ) / 1_000_000
    off_peak = peak * Decimal(TARIFF["off_peak_multiplier"])
    return {
        "peak_usd": str(peak),
        "off_peak_usd": str(off_peak),
        "tariff": TARIFF,
    }


class DeepSeekProvider:
    name = "deepseek"
    model = MODEL
    sdk_version = f"httpx-{httpx.__version__}"
    wrapper_version = WRAPPER_VERSION

    def __init__(
        self,
        api_key: str,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ):
        self._secrets = (api_key,)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        # No transport retries, no redirects, no proxies or .netrc from the
        # environment: the request cap counts real requests to one known host.
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_s,
            follow_redirects=False,
            trust_env=False,
            transport=transport or httpx.HTTPTransport(retries=0),
        )
        self._body = {
            "model": MODEL,
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
        self.settings = {
            "endpoint": BASE_URL + "/chat/completions",
            **{k: v for k, v in self._body.items() if k != "model"},
            "image_detail": "original",
            "timeout_s": timeout_s,
            "transport_retries": 0,
            "follow_redirects": False,
            "trust_env": False,
        }

    def wrap_prompt(self, prompt: str) -> str:
        return prompt + WRAPPER + schema_text()

    def estimate_cost(self, usage: dict | None) -> dict | None:
        return estimate_cost(usage)

    def generate(self, image: bytes, mime_type: str, prompt: str) -> ProviderResponse:
        data_url = f"data:{mime_type};base64," + base64.b64encode(image).decode()
        payload = {
            **self._body,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "original"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        try:
            response = self._client.post(
                "/chat/completions", json=payload, headers=self._headers
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", self._safe(exc)) from None
        except Exception as exc:  # noqa: BLE001 - any other failure is "not checked"
            raise ProviderError("api_error", self._safe(exc)) from None
        body = redact(response.text, self._secrets)
        if response.status_code != 200:
            kind = "rate_limited" if response.status_code == 429 else "api_error"
            raw = {"http_status": response.status_code, "body": body}
            raise ProviderError(kind, f"HTTP {response.status_code}", raw)
        try:
            raw = json.loads(body)
        except ValueError:
            raise ProviderError(
                "api_error", "the API response is not JSON", {"body": body}
            ) from None
        if not isinstance(raw, dict):
            raise ProviderError("api_error", "the API response is not an object", None)
        return self._parse(raw)

    def _safe(self, exc: Exception) -> str:
        return redact(f"{type(exc).__name__}: {exc}", self._secrets)

    @staticmethod
    def _parse(raw: dict) -> ProviderResponse:
        # Model and usage are kept even when the answer is rejected below, so
        # the run record still accounts for the tokens that were billed.
        response = ProviderResponse(
            text="",
            raw=raw,
            model_version=raw.get("model"),
            usage=raw.get("usage"),
            system_fingerprint=raw.get("system_fingerprint"),
        )

        def reject(kind, message):
            return ProviderError(kind, message, raw, response=response)

        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise reject("empty_response", "no choices")
        choice = choices[0] if isinstance(choices[0], dict) else {}
        finish = choice.get("finish_reason")
        if finish != "stop":
            raise reject("incomplete_response", f"finish_reason={finish}")
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise reject("empty_response", "the response has no text")
        response.text = content
        return response
