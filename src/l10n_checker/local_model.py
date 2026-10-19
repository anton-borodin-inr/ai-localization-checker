"""Loopback-only HTTP vision adapter for the approved issue 10 experiment."""

import base64
import json
import platform
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from l10n_checker.vision import ProviderError, ProviderResponse

ENDPOINT = "http://127.0.0.1:1234"
MODEL = "qwen/qwen3-vl-8b"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirect refused", headers, fp)


class LocalVisionProvider:
    name = "lmstudio-local"
    sdk_version = "stdlib-urllib/python-" + platform.python_version()

    def __init__(self, schema, model_metadata, *, timeout_s=180, opener=None):
        if timeout_s not in (180, 400):
            raise ValueError("Only approved local timeouts are allowed")
        self._timeout_s = timeout_s
        self.model = MODEL
        self._opener = opener or build_opener(ProxyHandler({}), NoRedirect())
        self._parameters = {
            "model": MODEL,
            "temperature": 0,
            "max_tokens": 8192,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "issue_10_reading_v1",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        self.settings = {
            **self._parameters,
            "endpoint": ENDPOINT + "/v1/chat/completions",
            "timeout_s": timeout_s,
            "transport_retries": 0,
            "redirects": False,
            "proxies": False,
            "media_resolution": None,
            "model_metadata_before_run": model_metadata,
        }

    def generate(self, image: bytes, mime_type: str, prompt: str) -> ProviderResponse:
        payload = {
            **self._parameters,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,"
                                + base64.b64encode(image).decode("ascii")
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        request = Request(
            self.settings["endpoint"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._timeout_s) as response:
                raw_bytes = response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(
                "rate_limited" if exc.code == 429 else "api_error",
                f"HTTP {exc.code}: {body}",
                {"http_status": exc.code, "body": body},
            ) from None
        except (TimeoutError, URLError, OSError) as exc:
            timeout = isinstance(exc, TimeoutError) or isinstance(
                getattr(exc, "reason", None), TimeoutError
            )
            raise ProviderError(
                "timeout" if timeout else "api_error", f"{type(exc).__name__}: {exc}"
            ) from None
        try:
            raw = json.loads(raw_bytes)
        except (ValueError, UnicodeDecodeError):
            raise ProviderError(
                "api_error",
                "Server returned non-JSON HTTP response",
                {"body": raw_bytes.decode("utf-8", errors="replace")},
            ) from None
        if not isinstance(raw, dict):
            raise ProviderError("api_error", "Server response is not an object")
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("empty_response", "No choices", raw)
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise ProviderError(
                "incomplete_response", "Missing or non-stop finish_reason", raw
            )
        message = choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("empty_response", "No text content", raw)
        if raw.get("model") != self.model:
            raise ProviderError("api_error", "Response model differs from request", raw)
        return ProviderResponse(
            text=message["content"],
            raw=raw,
            # An alias is not an immutable model revision.
            model_version=None,
            usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else None,
        )
