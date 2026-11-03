"""Offline mutation plans. No builds, device operations, detectors or labels."""

from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_recipes import Recipe, RecipeSet, load_recipes
from l10n_checker.screen_manifest import (
    FileRef,
    Hash,
    Manifest,
    Name,
    StrictModel,
    digest,
    json_bytes,
    referenced_file,
)
from l10n_checker.screen_split import load_split
from l10n_checker.text_dump import Rect, canonical_bytes
from l10n_checker.text_reference import child, load_pair

GENERATOR_VERSION = "mutation-planner-v1"
STATIC_MARGIN_PX = 8


class PairRef(FileRef):
    screen: Name
    language: Literal["en", "de"]


class Inventory(StrictModel):
    schema_version: Literal[1]
    pairs: Annotated[list[PairRef], Field(min_length=1)]


class Occurrence(StrictModel):
    screen: Name
    language: Literal["en", "de"]
    logical_id: Annotated[str, Field(min_length=1)]
    actor_path: Annotated[str, Field(min_length=1)]
    bounds: Rect
    glyph_bounds: Rect
    input_text: str | None
    display_text: str
    visibility: Literal["full"]
    element_ids: Annotated[list[str], Field(min_length=1)]
    source_key: str | None
    source_keys: list[str]
    ellipsis_applied: bool
    overflow_x: bool
    overflow_y: bool
    clip_cause: str


class InventoryEvidence(StrictModel):
    screen: Name
    language: Literal["en", "de"]
    dump_sha256: Hash
    png_sha256: Hash
    rgba_sha256: Hash
    state_sha256: Hash


class OfflinePlan(StrictModel):
    manifest_version: Literal[1]
    generator_version: Literal["mutation-planner-v1"]
    stage: Literal["offline_plan"]
    production_ready: Literal[False]
    seed: int
    recipe_version: Name
    fork_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    source_manifest_sha256: Hash
    split_sha256: Hash
    screen_ids: list[Name]
    inventory: list[InventoryEvidence]
    inventory_role: Literal["static_target_binding_not_production_clean_controls"]
    mutations: dict[str, dict]
    clean_build: dict
    batches: list[dict]
    calibration: dict
    policy: dict
    density: dict
    primary_balance: dict
    production_blockers: list[str]
    static_conflicts: list[dict]
    split_history: list[dict]
    planned_recipe_class_counts: dict[str, int]
    dynamic_split_rate: None


def _primary_balance(mutations):
    result = {}
    for language in ("en", "de"):
        counts = {
            kind: sum(
                len(m["occurrences"])
                for m in mutations.values()
                if m["recipe"]["language"] == language
                and m["recipe"]["intended_class"] == kind
            )
            for kind in ("overflow", "wrong_language", "truncated_text")
        }
        counts["balanced"] = len(set(counts.values())) == 1 and min(counts.values()) > 0
        result[language] = counts
    return result


def _recipe_counts(mutations):
    return dict(
        sorted(
            Counter(m["recipe"]["intended_class"] for m in mutations.values()).items()
        )
    )


def _static_conflicts(mutations):
    return [
        {"recipe_ids": [a, b], "reason": why}
        for a, b in combinations(sorted(mutations), 2)
        if (why := _conflict(mutations[a], mutations[b]))
    ]


def _policy():
    return {
        "max_visible_occurrences": 2,
        "minimum_single_occurrence_share": 0.5,
        "static_margin_px": STATIC_MARGIN_PX,
        "dynamic_gate_is_authoritative": True,
        "primary_class_balance": "target_not_cap",
    }


def _blockers():
    return [
        "runtime_qualification",
        "calibration",
        "frozen_builder_catalog",
        "device_verification",
    ]


def _calibration(mutations):
    candidates = [r for r, m in mutations.items() if len(m["occurrences"]) == 1]
    if not candidates:
        raise CaptureError("No single-occurrence mutation for calibration")
    identity = min(
        candidates,
        key=lambda r: (
            mutations[r]["recipe"]["intended_class"] != "overflow",
            len(mutations[r]["recipe"]["replacement"] or ""),
            r,
        ),
    )
    return {
        "status": "not_run",
        "required_before_production": True,
        "mutation_recipe_id": identity,
        "outside_mask_rgba_tolerance": 0,
        "on_outside_mask_difference": "stop_and_report_count_bbox_max_delta",
    }


def _target_binding(recipe, screen, element):
    selectors = [
        i
        for i, target in enumerate(recipe.targets)
        if target.screen == screen
        and (
            element.input_text == target.text
            if target.match == "exact"
            else target.text in (element.input_text or "")
        )
    ]
    known_key = recipe.key in [element.source_key, *element.source_keys]
    if selectors and element.source_key is not None and not known_key:
        raise CaptureError(f"Contradictory target source key for {recipe.id}")
    return selectors, known_key


def _validate_occurrences(recipe, occurrences, selected, observations):
    if not {t.screen for t in recipe.targets} <= set(selected):
        raise ValueError("Recipe target differs from screen selection")
    if not isinstance(occurrences, list) or not occurrences:
        raise ValueError(f"No occurrences for {recipe.id}")
    logical_ids, draw_ids, matched = set(), set(), set()
    counts = Counter()
    for raw in occurrences:
        occurrence = Occurrence.model_validate(raw)
        code = occurrence.screen, occurrence.language
        if (
            code not in observations
            or occurrence.language != recipe.language
            or occurrence.screen not in {t.screen for t in recipe.targets}
        ):
            raise ValueError(
                f"Occurrence scope differs from recipe/inventory: {recipe.id}"
            )
        identity = (*code, occurrence.logical_id)
        if identity in logical_ids:
            raise ValueError("Duplicate logical occurrence")
        logical_ids.add(identity)
        for draw in occurrence.element_ids:
            if (*code, draw) in draw_ids:
                raise ValueError("Duplicate occurrence draw")
            draw_ids.add((*code, draw))
        counts[code] += 1
        if counts[code] > 2:
            raise ValueError(f"Visible occurrence cap exceeded by {recipe.id}")
        selectors, known_key = _target_binding(recipe, occurrence.screen, occurrence)
        if not selectors and not known_key:
            raise ValueError(f"Unbound occurrence for {recipe.id}")
        matched.update(selectors)
    if matched != set(range(len(recipe.targets))):
        raise ValueError(f"Missing visible target selector for {recipe.id}")


def _validate_lineage(value, observations):
    replay = {
        "mutations": value["mutations"],
        "inventory": value["inventory"],
        "batches": _combine(value["mutations"], observations, value["seed"]),
        "split_history": [],
    }
    try:
        for event in value["split_history"]:
            if set(event) != {"parent", "children", "reason"} or not isinstance(
                event["reason"], dict
            ):
                raise ValueError("Invalid split event fields")
            replay = split_after_interference(
                replay, event["parent"]["id"], event["reason"]
            )
            if replay["split_history"][-1] != event:
                raise ValueError(
                    "Split parent/children differ from deterministic replay"
                )
        if replay["batches"] != value["batches"]:
            raise ValueError("Final batches differ from recorded splits")
    except (CaptureError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"Invalid split lineage: {exc}") from exc


def load_plan(raw: bytes, *, manifest: Path) -> dict:
    """Validate the offline wire contract, not device authorization or qualification."""
    try:
        value = OfflinePlan.model_validate(json_bytes(raw)).model_dump()
        manifest_raw = manifest.read_bytes()
        if digest(manifest_raw) != value["source_manifest_sha256"]:
            raise ValueError("Source manifest SHA-256 mismatch")
        model = Manifest.model_validate(json_bytes(manifest_raw))
        if value["fork_commit"] != model.build.fork_commit:
            raise ValueError("Plan fork source differs from the authoritative manifest")
        partition = load_split(
            manifest.with_name("split.json"), [s.id for s in model.screens]
        )
        if partition.sha256 != value["split_sha256"]:
            raise ValueError("Source split SHA-256 mismatch")
        inventory = [(r["screen"], r["language"]) for r in value["inventory"]]
        screens = set(partition.dev)
        expected = {(s, l.code) for s in partition.dev for l in model.languages}
        if (
            not inventory
            or len(set(inventory)) != len(inventory)
            or set(inventory) != expected
        ):
            raise ValueError("Incomplete or duplicate inventory coverage")
        selected = value["screen_ids"]
        if (
            not selected
            or len(set(selected)) != len(selected)
            or not set(selected) <= screens
        ):
            raise ValueError("Invalid screen selection against inventory")
        mutations = value["mutations"]
        observations = {code: None for code in inventory}
        for identity, item in mutations.items():
            if set(item) != {"recipe", "patch", "occurrences"}:
                raise ValueError("Unexpected mutation fields")
            recipe = Recipe.model_validate(item["recipe"])
            if recipe.id != identity or recipe.patch() != item["patch"]:
                raise ValueError("Mutation patch differs from its recipe")
            _validate_occurrences(recipe, item["occurrences"], selected, observations)
        RecipeSet.model_validate(
            {
                "schema_version": 1,
                "recipe_version": value["recipe_version"],
                "fork_commit": value["fork_commit"],
                "recipes": [m["recipe"] for m in mutations.values()],
            }
        )
        batch_ids = [b["id"] for b in value["batches"]]
        if len(set(batch_ids)) != len(batch_ids):
            raise ValueError("Duplicate batch identity")
        covered = [r for b in value["batches"] for r in b["recipe_ids"]]
        if sorted(covered) != sorted(mutations):
            raise ValueError("Every recipe must occur in exactly one batch")
        for batch in value["batches"]:
            if batch != _batch(batch["recipe_ids"], mutations, observations):
                raise ValueError("Inconsistent batch/hash/occurrence data")
            if any(
                _conflict(mutations[a], mutations[b])
                for a, b in combinations(batch["recipe_ids"], 2)
            ):
                raise ValueError("Batch fails the static prefilter")
        clean = _batch([], mutations, observations)
        clean["builder"] = "same_as_mutated_batches"
        if value["clean_build"] != clean or value["density"] != _density(
            value["batches"]
        ):
            raise ValueError("Inconsistent controls or density")
        if value["primary_balance"] != _primary_balance(mutations):
            raise ValueError("Inconsistent primary class balance")
        if value["planned_recipe_class_counts"] != _recipe_counts(mutations):
            raise ValueError("Inconsistent planned recipe counts")
        if value["static_conflicts"] != _static_conflicts(mutations):
            raise ValueError("Inconsistent static conflicts")
        if (
            value["policy"] != _policy()
            or value["calibration"] != _calibration(mutations)
            or value["production_blockers"] != _blockers()
        ):
            raise ValueError("The pending gate contract differs")
        if not _density_ok(value["batches"]):
            raise ValueError("Offline plan must retain density and production gates")
        _validate_lineage(value, observations)
        return value
    except (ValueError, TypeError, KeyError) as exc:
        raise CaptureError(f"Invalid mutation manifest: {exc}") from exc


def _bind(recipe, observations):
    occurrences = []
    matched = set()
    for (screen, language), dump in sorted(observations.items()):
        if language != recipe.language:
            continue
        matching = {}
        for e in dump.elements:
            if e.visibility == "hidden" or e.decoration:
                continue
            selectors, known_key = _target_binding(recipe, screen, e)
            if known_key and screen not in {t.screen for t in recipe.targets}:
                raise CaptureError(f"Undeclared key scope for {recipe.id}: {screen}")
            if selectors or known_key:
                matched.update(selectors)
                if e.visibility != "full" or not e.actor_path or e.bounds is None:
                    raise CaptureError(f"Unprovable target geometry for {recipe.id}")
                matching[e.logical_id] = e
        if len(matching) > 2:
            raise CaptureError(
                f"Visible occurrence cap exceeded by {recipe.id}: {screen}"
            )
        for logical_id, e in sorted(matching.items()):
            occurrences.append(
                {
                    "screen": screen,
                    "language": language,
                    "logical_id": logical_id,
                    "actor_path": e.actor_path,
                    "bounds": e.bounds,
                    "glyph_bounds": e.glyph_bounds,
                    "input_text": e.input_text,
                    "display_text": e.display_text,
                    "visibility": e.visibility,
                    "element_ids": [
                        v.id for v in dump.elements if v.logical_id == logical_id
                    ],
                    "source_key": e.source_key,
                    "source_keys": e.source_keys,
                    "ellipsis_applied": e.ellipsis_applied,
                    "overflow_x": e.overflow_x,
                    "overflow_y": e.overflow_y,
                    "clip_cause": e.clip_cause,
                }
            )
    if matched != set(range(len(recipe.targets))):
        raise CaptureError(f"Missing visible target selector for {recipe.id}")
    return occurrences


def _density(batches):
    result = {}
    for language in ("en", "de"):
        counts = [
            s["visible_occurrences"]
            for b in batches
            for s in b["screenshots"]
            if s["language"] == language and s["visible_occurrences"]
        ]
        single = counts.count(1)
        result[language] = {
            "single_occurrence_screenshots": single,
            "mutated_screenshots": len(counts),
            "share": single / len(counts) if counts else None,
        }
    return result


def _density_ok(batches):
    return all(
        d["single_occurrence_screenshots"] * 2 >= d["mutated_screenshots"]
        for d in _density(batches).values()
    ) and all(s["visible_occurrences"] <= 2 for b in batches for s in b["screenshots"])


def _conflict(first, second):
    a, b = first["recipe"], second["recipe"]
    if a["language"] == b["language"] and a["key"] == b["key"]:
        return "same_translation_key"
    for x in first["occurrences"]:
        for y in second["occurrences"]:
            if (x["screen"], x["language"]) != (y["screen"], y["language"]):
                continue
            if x["actor_path"] == y["actor_path"]:
                return "same_owning_actor"

            def extent(o):
                a, b = o["bounds"], o["glyph_bounds"]
                return [
                    min(a[0], b[0]),
                    min(a[1], b[1]),
                    max(a[2], b[2]),
                    max(a[3], b[3]),
                ]

            a, b = extent(x), extent(y)
            gap = STATIC_MARGIN_PX
            if not (
                a[2] + gap <= b[0]
                or b[2] + gap <= a[0]
                or a[3] + gap <= b[1]
                or b[3] + gap <= a[1]
            ):
                return "rectangles_with_margin_overlap"
    return None


def _combine(mutations, observations, seed):
    order = sorted(mutations, key=lambda r: (digest(f"{seed}\0{r}".encode()), r))
    groups = [[r] for r in order]
    if not _density_ok([_batch(g, mutations, observations) for g in groups]):
        raise CaptureError(
            "Recipe cohort cannot provide 50% single-occurrence screenshots"
        )
    changed = True
    while changed:
        changed = False
        for i, j in combinations(range(len(groups)), 2):
            combined = groups[i] + groups[j]
            if any(
                _conflict(mutations[a], mutations[b])
                for a, b in combinations(combined, 2)
            ):
                continue
            proposed = [g for k, g in enumerate(groups) if k not in (i, j)] + [combined]
            if _density_ok([_batch(g, mutations, observations) for g in proposed]):
                groups = proposed
                changed = True
                break
    return sorted(
        [_batch(g, mutations, observations) for g in groups], key=lambda b: b["id"]
    )


def _batch(ids, mutations, observations):
    patches = [mutations[r]["patch"] for r in sorted(ids)]
    patch_hash = digest(canonical_bytes(patches))
    screenshots = []
    for screen, language in sorted(observations):
        occurrences = [
            {**o, "recipe_id": r}
            for r in sorted(ids)
            for o in mutations[r]["occurrences"]
            if (o["screen"], o["language"]) == (screen, language)
        ]
        screenshots.append(
            {
                "screen": screen,
                "language": language,
                "recipe_ids": sorted({o["recipe_id"] for o in occurrences}),
                "visible_occurrences": len(occurrences),
                "occurrences": occurrences,
                "verification": {"static": "prefilter_only", "dynamic": "not_run"},
            }
        )
    return {
        "id": f"batch-{patch_hash[:16]}",
        "recipe_ids": sorted(ids),
        "patch_set_sha256": patch_hash,
        "patches": patches,
        "screenshots": screenshots,
    }


def split_after_interference(plan: dict, batch_id: str, reason: dict) -> dict:
    """Pure partition update; the device verifier supplies real interference evidence."""
    if reason.get("kind") not in {
        "outside_mask_pixels",
        "changed_unmutated_element",
        "missing_mutation",
    }:
        raise CaptureError("An operational failure is not mutation interference")
    result = deepcopy(plan)
    parent = next((b for b in result["batches"] if b["id"] == batch_id), None)
    if parent is None:
        raise CaptureError("Unknown batch to split")
    ids = parent["recipe_ids"]
    if len(ids) < 2:
        raise CaptureError("A failing singleton stops qualification; cannot split")
    midpoint = len(ids) // 2
    observations = {(v["screen"], v["language"]): None for v in result["inventory"]}
    children = [
        _batch(part, result["mutations"], observations)
        for part in (ids[:midpoint], ids[midpoint:])
    ]
    result["batches"] = sorted(
        [b for b in result["batches"] if b["id"] != batch_id] + children,
        key=lambda b: b["id"],
    )
    result["split_history"].append(
        {
            "parent": parent,
            "children": [b["id"] for b in children],
            "reason": deepcopy(reason),
        }
    )
    result["density"] = _density(result["batches"])
    return result


def create_plan(
    *,
    manifest: Path,
    recipes: Path,
    inventory: Path,
    seed: int,
    split: str | None = None,
    screen_ids: list[str] | None = None,
) -> dict:
    """Bind versioned recipes to a complete dev clean inventory, without writing."""
    if type(seed) is not int:
        raise CaptureError("The seed must be a literal integer")
    manifest_raw = manifest.read_bytes()
    model = Manifest.model_validate(json_bytes(manifest_raw))
    partition = load_split(
        manifest.with_name("split.json"), [s.id for s in model.screens]
    )
    if (split is None) == (screen_ids is None):
        raise CaptureError("Select exactly one of --split dev or --screen-id")
    selected = list(partition.dev) if split == "dev" else screen_ids
    if (
        split not in (None, "dev")
        or not selected
        or len(set(selected)) != len(selected)
        or not set(selected) <= set(partition.dev)
    ):
        raise CaptureError("Mutation planning accepts dev screen IDs only")
    recipe_set = load_recipes(recipes.read_bytes())
    if recipe_set.fork_commit != model.build.fork_commit:
        raise CaptureError("Recipe fork source differs from the manifest pin")
    if any(t.screen not in selected for r in recipe_set.recipes for t in r.targets):
        raise CaptureError(
            "Every recipe target must belong to the selected dev screens"
        )
    index = Inventory.model_validate(json_bytes(inventory.read_bytes()))
    expected = {(s, l.code) for s in partition.dev for l in model.languages}
    supplied = [(r.screen, r.language) for r in index.pairs]
    if len(set(supplied)) != len(supplied) or set(supplied) != expected:
        raise CaptureError(
            "Inventory must cover every dev screen/language exactly once"
        )
    observations = {}
    sources = []
    states = {}
    for screen in model.screens:
        if screen.id not in partition.dev:
            continue
        for language in model.languages:
            ref = screen.language_states.get(language.code)
            raw = referenced_file(
                manifest.parent,
                ref.path if ref else screen.state,
                ref.sha256 if ref else screen.sha256,
            )
            states[screen.id, language.code] = digest(canonical_bytes(json_bytes(raw)))
    for ref in index.pairs:
        path = child(inventory.parent, ref.path)
        pair_raw = path.read_bytes()
        if digest(pair_raw) != ref.sha256:
            raise CaptureError("Inventory pair SHA-256 mismatch")
        pair = json_bytes(pair_raw)
        code = ref.screen, ref.language
        language = next(
            l.game_language for l in model.languages if l.code == ref.language
        )
        # The index label cannot authorize payloads of a different actual pair.
        if (
            pair.get("pair_version") != 1
            or pair.get("protocol_version") != 2
            or pair.get("protocol_version") != model.protocol_version
            or pair.get("screen") != ref.screen
            or pair.get("language") != language
            or pair.get("state_sha256") != states[code]
            or pair.get("build") != model.build.model_dump()
        ):
            raise CaptureError("Inventory sidecar provenance differs from the manifest")
        pair, _, raw, dump = load_pair(path, pair_bytes=pair_raw)
        if (
            dump.screen != ref.screen
            or dump.language != language
            or dump.state_sha256 != states[code]
            or dump.build_version_code != int(model.build.version_code)
            or dump.image_size != model.resolution
            or pair["build"] != model.build.model_dump()
        ):
            raise CaptureError("Inventory identity differs from the source manifest")
        observations[code] = dump
        sources.append(
            {
                "screen": ref.screen,
                "language": ref.language,
                "dump_sha256": digest(raw),
                "png_sha256": pair["png_sha256"],
                "rgba_sha256": pair["rgba_sha256"],
                "state_sha256": dump.state_sha256,
            }
        )
    mutations = {}
    for recipe in sorted(recipe_set.recipes, key=lambda r: r.id):
        occurrences = _bind(recipe, observations)
        mutations[recipe.id] = {
            "recipe": recipe.model_dump(),
            "patch": recipe.patch(),
            "occurrences": occurrences,
        }
    batches = _combine(mutations, observations, seed)
    clean = _batch([], mutations, observations)
    clean["builder"] = "same_as_mutated_batches"
    balance = _primary_balance(mutations)
    return {
        "manifest_version": 1,
        "generator_version": GENERATOR_VERSION,
        "stage": "offline_plan",
        "production_ready": False,
        "seed": seed,
        "recipe_version": recipe_set.recipe_version,
        "fork_commit": recipe_set.fork_commit,
        "source_manifest_sha256": digest(manifest_raw),
        "split_sha256": partition.sha256,
        "screen_ids": [s.id for s in model.screens if s.id in selected],
        "inventory": sorted(sources, key=lambda s: (s["screen"], s["language"])),
        "inventory_role": "static_target_binding_not_production_clean_controls",
        "mutations": mutations,
        "clean_build": clean,
        "batches": batches,
        "calibration": _calibration(mutations),
        "policy": _policy(),
        "density": _density(batches),
        "primary_balance": balance,
        "production_blockers": _blockers(),
        "static_conflicts": _static_conflicts(mutations),
        "split_history": [],
        "planned_recipe_class_counts": _recipe_counts(mutations),
        "dynamic_split_rate": None,
    }
