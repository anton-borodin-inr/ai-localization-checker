"""Claude Messages API adapter. The only module that talks to the Anthropic API."""

import base64
from decimal import Decimal

import httpx

from l10n_checker.deepseek import make_http_client, post_json
from l10n_checker.vision import ModelOutput, ProviderError, ProviderResponse

BASE_URL = "https://api.anthropic.com"
API_VERSION = "2026-10-21"
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 4096
EFFORT = "high"
DEFAULT_TIMEOUT_S = 120
# Claude 4.7+/5.x image ceiling (4,784) + prompt/schema/framing bound (8,192).
MAX_IMAGE_TOKENS = 4784
MAX_PROMPT_AND_SCHEMA_TOKENS = 8192
CONSERVATIVE_INPUT_TOKENS = MAX_IMAGE_TOKENS + MAX_PROMPT_AND_SCHEMA_TOKENS

TARIFF = {
    "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    "verified_date": "2026-11-26",
    "model": MODEL,
    "currency": "USD",
    "per_million_tokens": {
        "input": "2.00",
        "output": "10.00",
        "cache_write_5m": "2.50",
        "cache_write_1h": "4.00",
        "cache_read": "0.10",
    },
}


def claude_schema() -> dict:
    """ModelOutput schema with $defs inlined and unsupported numeric bounds dropped."""
    raw = ModelOutput.model_json_schema()
    defs = raw.pop("$defs", {})

    def clean(node):
        if isinstance(node, list):
            return [clean(x) for x in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return clean(defs[node["$ref"].removeprefix("#/$defs/")])
        return {k: clean(v) for k, v in node.items() if k not in ("minimum", "maximum")}

    return clean(raw)


def estimate_cost(usage: dict | None) -> dict | None:
    """Tariff-based estimate from returned usage; not a billing receipt."""
    if not isinstance(usage, dict):
        return None
    inp, out = usage.get("input_tokens"), usage.get("output_tokens")
    cw = usage.get("cache_creation_input_tokens", 0)
    cr = usage.get("cache_read_input_tokens", 0)
    if any(type(n) is not int or n < 0 for n in (inp, out, cw, cr)):
        return None
    r = {k: Decimal(v) for k, v in TARIFF["per_million_tokens"].items()}
    usd = (
        inp * r["input"]
        + out * r["output"]
        + cw * r["cache_write_5m"]
        + cr * r["cache_read"]
    ) / 1_000_000
    return {"usd": str(usd), "peak_usd": str(usd), "tariff": TARIFF}


class ClaudeProvider:
    name = "claude"
    model = MODEL
    sdk_version = f"httpx-{httpx.__version__}"
    wrapper_version = None
    tariff = TARIFF
    estimate_cost = staticmethod(estimate_cost)

    def __init__(
        self,
        api_key: str,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ):
        self._secrets = (api_key,)
        self._headers = {"x-api-key": api_key, "anthropic-version": API_VERSION}
        self._client = make_http_client(BASE_URL, timeout_s, transport)
        # No sampling params (removed in API 2026-10-21 / Sonnet 5.5); between_tools
        # suppresses up-front thinking; effort is pinned explicitly.
        self._body = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "stream": False,
            "thinking": {"type": "between_tools"},
            "output_config": {
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": claude_schema()},
            },
        }
        self.settings = {
            "endpoint": BASE_URL + "/v1/messages",
            "anthropic_version": API_VERSION,
            **{k: v for k, v in self._body.items() if k != "model"},
            "timeout_s": timeout_s,
            "transport_retries": 0,
            "follow_redirects": False,
            "trust_env": False,
        }

    def wrap_prompt(self, prompt: str) -> str:
        return prompt

    def worst_case_reserve_usd(self) -> Decimal:
        usage = {"input_tokens": CONSERVATIVE_INPUT_TOKENS, "output_tokens": MAX_TOKENS}
        return Decimal(estimate_cost(usage)["usd"])  # type: ignore[index]

    def generate(self, image: bytes, mime_type: str, prompt: str) -> ProviderResponse:
        src = {
            "type": "base64",
            "media_type": mime_type,
            "data": base64.b64encode(image).decode(),
        }
        content = [{"type": "image", "source": src}, {"type": "text", "text": prompt}]
        payload = {**self._body, "messages": [{"role": "user", "content": content}]}
        raw = post_json(
            self._client, "/v1/messages", payload, self._headers, self._secrets
        )
        return self._parse(raw)

    @staticmethod
    def _parse(raw: dict) -> ProviderResponse:
        model = raw.get("model")
        res = ProviderResponse(
            "", raw, model if isinstance(model, str) else None, raw.get("usage")
        )

        def err(kind, msg):
            return ProviderError(kind, msg, raw, response=res)

        stop = raw.get("stop_reason")
        if stop != "end_turn":
            kind = "refusal" if stop == "refusal" else "incomplete_response"
            raise err(kind, f"stop_reason={stop}")
        content = raw.get("content")
        if not isinstance(content, list) or not content:
            raise err("empty_response", "no content blocks")
        texts = [
            b.get("text")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        if len(texts) > 1:
            raise err("incomplete_response", f"expected 1 text block, got {len(texts)}")
        if not texts or not isinstance(texts[0], str) or not texts[0].strip():
            raise err("empty_response", "the response has no text")
        res.text = texts[0]
        return res
