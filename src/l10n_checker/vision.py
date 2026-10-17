"""Provider-agnostic vision check: one screenshot in, findings or "not checked" out.

The finding schema here is a draft (v0). It is finalized in Stage 1.
"""

import hashlib
import json
import secrets as random_tokens
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from l10n_checker.capture import png_size

SCHEMA_VERSION = "v0-draft"

DefectType = Literal["truncated_text", "overlap", "untranslated", "other"]
Region = Literal[
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
]

PROMPT = """\
You are a localization QA engineer reviewing one screenshot of a mobile game UI.
Report localization defects that are visible in the screenshot:
- truncated_text: text cut off, clipped by its container or ending in an ellipsis \
because it does not fit;
- overlap: text overlapping other text, icons or the edge of its container;
- untranslated: text left in a different language than the rest of the UI;
- other: any other visible localization defect.
For each defect give the affected text exactly as you see it (text_seen), the \
coarse screen region on a 3x3 grid (top-left, top, top-right, left, center, \
right, bottom-left, bottom, bottom-right) and your confidence from 0 to 1.
Return an empty findings list only if you see no defects.
"""


class Finding(BaseModel):
    """Draft v0 finding; the schema is finalized in Stage 1."""

    model_config = ConfigDict(extra="forbid")

    defect_type: DefectType
    text_seen: str
    region: Region
    confidence: float = Field(ge=0, le=1)


class ModelOutput(BaseModel):
    """What the model must return, requested as structured output."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]


class CheckResult(BaseModel):
    status: Literal["checked", "not_checked"]
    findings: list[Finding]
    reason: str | None
    metadata: dict[str, Any]

    @model_validator(mode="after")
    def _status_is_consistent(self):
        if self.status == "not_checked" and (self.findings or not self.reason):
            raise ValueError("not_checked needs a reason and no findings")
        if self.status == "checked" and self.reason is not None:
            raise ValueError("checked must not carry a failure reason")
        return self


ErrorKind = Literal[
    "timeout", "rate_limited", "api_error", "empty_response", "incomplete_response"
]


class ProviderError(Exception):
    """A provider call that produced no usable response."""

    def __init__(self, kind: ErrorKind, message: str, raw: dict | None = None):
        super().__init__(f"{kind}: {message}")
        self.kind = kind
        self.message = message
        self.raw = raw


@dataclass
class ProviderResponse:
    text: str
    raw: dict
    model_version: str | None = None
    usage: dict | None = None


class VisionProvider(Protocol):
    name: str
    model: str
    settings: dict[str, Any]
    sdk_version: str

    def generate(
        self, image: bytes, mime_type: str, prompt: str
    ) -> ProviderResponse: ...


class BudgetExceeded(Exception):
    pass


@dataclass
class RequestBudget:
    """Refuses to send requests beyond the per-run cap."""

    max_requests: int
    used: int = field(default=0, init=False)

    def take(self) -> None:
        if self.used >= self.max_requests:
            raise BudgetExceeded(f"request cap of {self.max_requests} reached")
        self.used += 1


def redact(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{random_tokens.token_hex(3)}"


def _call(
    provider: VisionProvider,
    image: bytes,
    budget: RequestBudget,
    attempts: list[dict],
    retry_delay_s: float,
) -> ProviderResponse:
    """Send the request, with one simple retry on rate limiting."""
    while True:
        budget.take()
        started = time.monotonic()
        try:
            response = provider.generate(image, "image/png", PROMPT)
        except ProviderError as exc:
            attempts.append(_attempt(started, exc.kind))
            if exc.kind != "rate_limited" or len(attempts) > 1:
                raise
            if budget.used >= budget.max_requests:
                raise
            time.sleep(retry_delay_s)
            continue
        attempts.append(_attempt(started, "ok"))
        return response


def _attempt(started: float, outcome: str) -> dict:
    return {"outcome": outcome, "latency_s": round(time.monotonic() - started, 3)}


def run_check(
    provider: VisionProvider,
    image_path: Path,
    runs_dir: Path,
    budget: RequestBudget,
    secrets: tuple[str, ...] = (),
    retry_delay_s: float = 5.0,
) -> tuple[CheckResult, Path]:
    """Check one screenshot and record the run under runs_dir/<run_id>/."""
    image = image_path.read_bytes()
    width, height = png_size(image)
    run_id = new_run_id()
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)

    attempts: list[dict] = []
    response: ProviderResponse | None = None
    raw: dict | None = None
    findings: list[Finding] = []
    reason: str | None = None
    try:
        response = _call(provider, image, budget, attempts, retry_delay_s)
        raw = response.raw
        if not response.text.strip():
            raise ProviderError("empty_response", "the response has no text", raw)
        findings = ModelOutput.model_validate_json(response.text).findings
    except BudgetExceeded as exc:
        reason = f"request_cap_reached: {exc}"
    except ProviderError as exc:
        reason = f"{exc.kind}: {exc.message}"
        raw = exc.raw
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'response'}: {e['msg']}"
            for e in exc.errors()
        )
        reason = f"invalid_response: {errors}"

    metadata = {
        "run_id": run_id,
        "provider": provider.name,
        "model": provider.model,
        "model_version": response.model_version if response else None,
        "sdk_version": provider.sdk_version,
        "schema_version": SCHEMA_VERSION,
        "settings": provider.settings,
        "image": {
            "path": str(image_path),
            "sha256": hashlib.sha256(image).hexdigest(),
            "width": width,
            "height": height,
        },
        "max_requests": budget.max_requests,
        "requests_sent": budget.used,
        "attempts": attempts,
        "usage": response.usage if response else None,
    }
    if reason is None:
        result = CheckResult(
            status="checked", findings=findings, reason=None, metadata=metadata
        )
    else:
        result = CheckResult(
            status="not_checked",
            findings=[],
            reason=redact(reason, secrets),
            metadata=metadata,
        )

    def write(name: str, text: str) -> None:
        (run_dir / name).write_text(redact(text, secrets), encoding="utf-8")

    write("prompt.txt", PROMPT)
    write("run.json", json.dumps(metadata, indent=2, ensure_ascii=False))
    if raw is not None:
        write("response_raw.json", json.dumps(raw, indent=2, ensure_ascii=False))
    write("result.json", result.model_dump_json(indent=2))
    return result, run_dir
