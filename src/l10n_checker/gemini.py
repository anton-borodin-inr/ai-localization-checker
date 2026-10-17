"""Gemini adapter. The only module that imports the Gemini SDK."""

import httpx
from google import genai
from google.genai import errors, types
from google.genai.version import __version__ as SDK_VERSION

from l10n_checker.vision import ModelOutput, ProviderError, ProviderResponse, redact

DEFAULT_MODEL = "gemini-3.8-flash"


class GeminiProvider:
    name = "gemini"
    sdk_version = SDK_VERSION

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        timeout_s: int = 60,
        client=None,
    ):
        self.model = model
        self._secrets = (api_key,)
        self._config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ModelOutput,
            temperature=0,
            max_output_tokens=8192,
        )
        # SDK retries are disabled so that the request cap counts real requests.
        http_options = types.HttpOptions(
            timeout=timeout_s * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        self._client = client or genai.Client(
            api_key=api_key, http_options=http_options
        )
        self.settings = {
            "temperature": 0,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
            "response_schema": "ModelOutput",
            "timeout_s": timeout_s,
            "sdk_retry_attempts": 1,
        }

    def generate(self, image: bytes, mime_type: str, prompt: str) -> ProviderResponse:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image, mime_type=mime_type),
                    prompt,
                ],
                config=self._config,
            )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderError("timeout", self._safe(exc)) from None
        except errors.APIError as exc:
            kind = "rate_limited" if exc.code == 429 else "api_error"
            raise ProviderError(kind, self._safe(exc)) from None
        except Exception as exc:  # noqa: BLE001 - any other failure is "not checked"
            raise ProviderError("api_error", self._safe(exc)) from None
        return self._parse(response)

    def _safe(self, exc: Exception) -> str:
        return redact(f"{type(exc).__name__}: {exc}", self._secrets)

    def _parse(self, response) -> ProviderResponse:
        raw = response.model_dump(mode="json", exclude={"sdk_http_response"})
        usage = (
            response.usage_metadata.model_dump(mode="json", exclude_none=True)
            if response.usage_metadata
            else None
        )
        feedback = response.prompt_feedback
        if feedback and feedback.block_reason:
            raise ProviderError(
                "empty_response", f"prompt blocked: {feedback.block_reason}", raw
            )
        if not response.candidates:
            raise ProviderError("empty_response", "no candidates", raw)
        finish = response.candidates[0].finish_reason
        if finish not in (None, types.FinishReason.STOP):
            raise ProviderError("incomplete_response", f"finish_reason={finish}", raw)
        if not (response.text or "").strip():
            raise ProviderError("empty_response", "the response has no text", raw)
        return ProviderResponse(
            text=response.text,
            raw=raw,
            model_version=response.model_version,
            usage=usage,
        )
