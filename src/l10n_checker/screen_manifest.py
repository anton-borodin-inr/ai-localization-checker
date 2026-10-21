"""Validated, hash-pinned inputs for the D-038 capture protocol."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from l10n_checker.capture import CaptureError, filename

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Name = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class FileRef(StrictModel):
    path: str
    sha256: Hash


class Fixture(FileRef):
    name: Name


class Language(StrictModel):
    code: Name
    game_language: str
    settings: str
    sha256: Hash


class Build(StrictModel):
    version_code: Annotated[str, Field(pattern=r"^[0-9]+$")]
    apk_sha256: Hash
    fork_commit: str
    implementation_commit: str


class Screen(StrictModel):
    id: Name
    route: str
    state: str
    sha256: Hash
    # null inherits the configured language list, including future additions.
    languages: list[str] | None
    language_states: dict[str, FileRef]
    notes: list[str]


class Manifest(StrictModel):
    schema_version: Literal[1]
    protocol_version: Literal[1]
    build: Build
    resolution: Annotated[
        list[Annotated[int, Field(gt=0)]], Field(min_length=2, max_length=2)
    ]
    density_dpi: Annotated[int, Field(gt=0)]
    languages: Annotated[list[Language], Field(min_length=1)]
    fixtures: list[Fixture]
    screens: Annotated[list[Screen], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_names(self):
        for label, names in (
            ("language", [v.code for v in self.languages]),
            ("fixture", [v.name for v in self.fixtures]),
            ("screen", [v.id for v in self.screens]),
        ):
            if len(set(names)) != len(names):
                raise ValueError(f"Duplicate {label}")
        codes = {v.code for v in self.languages}
        for screen in self.screens:
            filename(screen.id, "pending", "pending", "clean", self.build.version_code)
            selected = codes if screen.languages is None else set(screen.languages)
            if not selected or not selected <= codes:
                raise ValueError(f"Unknown or empty languages for {screen.id}")
            if not set(screen.language_states) <= selected:
                raise ValueError(f"Unused language override for {screen.id}")
        return self


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def json_bytes(data: bytes):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid)


def referenced_file(root: Path, path: str, sha256: str) -> bytes:
    target = (root / path).resolve()
    if Path(path).is_absolute() or not target.is_relative_to(root.resolve()):
        raise CaptureError(f"Manifest input escapes its directory: {path}")
    data = target.read_bytes()
    if digest(data) != sha256:
        raise CaptureError(f"Manifest input SHA-256 mismatch: {path}")
    return data


STATE_FIELDS = {
    "schema_version",
    "save",
    "selection",
    "tab",
    "expanded_sections",
    "scroll",
    "scroll_to",
    "camera",
    "new_game",
}
SELECTIONS = {
    "options-gameplay": set(),
    "new-game": set(),
    "tech-picker": {"technology"},
    "city-production": {"city", "construction"},
    "empire-stats": set(),
    "policy-picker": set(),
    "victory-status": set(),
    "civilopedia": {"category", "article"},
    "world": {"unit"},
    "city-state-diplomacy": {"city_state"},
}
ANCHORS = {
    "technology",
    "construction",
    "branch",
    "entry",
    "category",
    "tab",
    "text",
    "edge",
}


def validate_state(state: object, screen: str, saves: set[str]):
    if not isinstance(state, dict) or set(state) != STATE_FIELDS:
        raise CaptureError(f"{screen}: D-038 requires exactly all ten state fields")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise CaptureError(f"{screen}: unsupported state schema")
    if screen not in SELECTIONS or not isinstance(state["selection"], dict):
        raise CaptureError(f"{screen}: unsupported screen or selection")
    if set(state["selection"]) != SELECTIONS[screen]:
        raise CaptureError(f"{screen}: incorrect selection fields")
    save = state["save"]
    if screen in {"options-gameplay", "new-game"}:
        if save is not None:
            raise CaptureError(f"{screen}: menu screen requires save=null")
    elif not isinstance(save, str) or save not in saves:
        raise CaptureError(f"{screen}: save is absent from fixture registry")
    if not isinstance(state["scroll"], dict) or not isinstance(
        state["scroll_to"], dict
    ):
        raise CaptureError(f"{screen}: scroll instructions must be objects")
    if set(state["scroll"]) & set(state["scroll_to"]):
        raise CaptureError(f"{screen}: a pane has two instructions")
    for pane, offset in state["scroll"].items():
        if not isinstance(offset, dict) or set(offset) != {"x", "y"}:
            raise CaptureError(f"{screen}/{pane}: offset requires x and y")
        if any(type(v) not in (float, int) or v < 0 for v in offset.values()):
            raise CaptureError(f"{screen}/{pane}: invalid offset")
    for pane, anchor in state["scroll_to"].items():
        if not isinstance(anchor, dict) or len(anchor) != 2:
            raise CaptureError(f"{screen}/{pane}: anchor requires one target and align")
        if len(set(anchor) & ANCHORS) != 1 or anchor.get("align") not in {
            "visible",
            "center",
            "start",
            "end",
        }:
            raise CaptureError(f"{screen}/{pane}: invalid anchor")
        if "edge" in anchor and anchor["edge"] not in {"start", "center", "end"}:
            raise CaptureError(f"{screen}/{pane}: invalid edge")
    if not isinstance(state["expanded_sections"], list) or any(
        not isinstance(v, str) for v in state["expanded_sections"]
    ):
        raise CaptureError(f"{screen}: expanded_sections must be source names")
    payload = json.dumps(state, ensure_ascii=False, allow_nan=False).encode()
    if len(payload) > 32768:
        raise CaptureError(f"{screen}: state exceeds D-038's 32 KiB limit")


class Inputs:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.root = self.path.parent
        try:
            data = self.path.read_bytes()
            self.sha256 = digest(data)
            self.manifest = Manifest.model_validate(json_bytes(data))
            self.settings = {}
            for language in self.manifest.languages:
                data = referenced_file(self.root, language.settings, language.sha256)
                settings = json_bytes(data)
                if (
                    not isinstance(settings, dict)
                    or settings.get("language") != language.game_language
                ):
                    raise CaptureError(
                        f"Settings language mismatch for {language.code}"
                    )
                self.settings[language.code] = data
            self.fixtures = {
                v.name: referenced_file(self.root, v.path, v.sha256)
                for v in self.manifest.fixtures
            }
            self.states = {}
            for screen in self.manifest.screens:
                codes = screen.languages or list(self.settings)
                for code in codes:
                    ref = screen.language_states.get(code)
                    data = referenced_file(
                        self.root,
                        ref.path if ref else screen.state,
                        ref.sha256 if ref else screen.sha256,
                    )
                    state = json_bytes(data)
                    validate_state(state, screen.id, set(self.fixtures))
                    self.states[screen.id, code] = state
        except (ValueError, OSError, TypeError, ValidationError) as exc:
            raise CaptureError(f"Invalid capture manifest/input: {exc}") from exc

    def languages(self, requested: list[str] | None) -> list[str]:
        codes = requested if requested is not None else list(self.settings)
        if (
            not codes
            or len(set(codes)) != len(codes)
            or not set(codes) <= self.settings.keys()
        ):
            raise CaptureError("Languages must be unique entries from the manifest")
        return codes

    def screens(self, language: str, reverse: bool = False) -> list[Screen]:
        screens = [v for v in self.manifest.screens if (v.id, language) in self.states]
        return list(reversed(screens)) if reverse else screens
