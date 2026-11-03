"""Synthetic end-to-end offline plans; no emulator, provider or defect labels."""

import importlib
import importlib.util
from pathlib import Path

import pytest
from test_mutation_recipes import document, recipe
from test_text_dump import dump_for, element, write_pair

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest, json_bytes
from l10n_checker.screen_split import load_split
from l10n_checker.text_dump import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/stage2/screens-v2.json"


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_plan") is not None, (
        "The offline mutation planner is missing"
    )
    return importlib.import_module("l10n_checker.mutation_plan")


def inputs(tmp_path, recipes=None, additions=None):
    manifest = json_bytes(MANIFEST.read_bytes())
    split = load_split(
        MANIFEST.with_name("split.json"), [s["id"] for s in manifest["screens"]]
    )
    refs = []
    for screen in manifest["screens"]:
        if screen["id"] not in split.dev:
            continue
        state = json_bytes((MANIFEST.parent / screen["state"]).read_bytes())
        for lang, game_lang in (("en", "English"), ("de", "German")):
            elements = []
            if screen["id"] == "tech-picker" and lang == "en":
                elements = [
                    element(
                        "Mining", "root/mining", input_text="Mining", source_key=None
                    )
                ]
            elements += (additions or {}).get((screen["id"], lang), [])
            dump = dump_for(
                screen=screen["id"], language=game_lang, state=state, elements=elements
            )
            dump["build_version_code"] = 1271048
            folder = tmp_path / f"{screen['id']}__{lang}"
            pair = write_pair(folder, dump)
            metadata = json_bytes(pair.read_bytes())
            metadata["build"] = manifest["build"]
            pair.write_bytes(canonical_bytes(metadata))
            refs.append(
                {
                    "screen": screen["id"],
                    "language": lang,
                    "path": str(pair.relative_to(tmp_path)),
                    "sha256": digest(pair.read_bytes()),
                }
            )
    inventory = tmp_path / "inventory.json"
    inventory.write_bytes(canonical_bytes({"schema_version": 1, "pairs": refs}))
    path = tmp_path / "recipes.json"
    path.write_bytes(canonical_bytes(document(*(recipes or [recipe()]))))
    return {
        "manifest": MANIFEST,
        "recipes": path,
        "inventory": inventory,
        "seed": 59,
        "split": "dev",
    }


def test_one_command_plan_contains_empty_builder_control_not_stock_control(tmp_path):
    kwargs = inputs(tmp_path)
    plan = api().create_plan(**kwargs)
    assert plan["manifest_version"] == 1
    assert plan["stage"] == "offline_plan"
    assert plan["production_ready"] is False
    assert plan["clean_build"]["patches"] == []
    assert plan["clean_build"]["builder"] == "same_as_mutated_batches"
    assert plan["calibration"]["status"] == "not_run"
    assert plan["calibration"]["required_before_production"] is True
    assert plan["batches"][0]["patches"][0]["key"] == "Mining"
    image = next(
        s
        for s in plan["batches"][0]["screenshots"]
        if s["screen"] == "tech-picker" and s["language"] == "en"
    )
    assert image["visible_occurrences"] == 1
    assert image["occurrences"][0]["logical_id"] == "root/mining"
    assert image["verification"]["dynamic"] == "not_run"
    assert len(plan["clean_build"]["screenshots"]) == 10
    assert canonical_bytes(api().create_plan(**kwargs)) == canonical_bytes(plan)


def registry():
    model = json_bytes(MANIFEST.read_bytes())
    return load_split(
        MANIFEST.with_name("split.json"), [s["id"] for s in model["screens"]]
    )


@pytest.mark.parametrize(
    "kind", ["excluded", "mixed", "owner_split", "missing", "both"]
)
def test_dev_guard_runs_before_recipe_or_inventory_payload_reads(
    tmp_path, monkeypatch, kind
):
    kwargs = inputs(tmp_path)
    selected = registry()
    choices = {
        "excluded": {"split": None, "screen_ids": [selected.holdout[0]]},
        "mixed": {"split": None, "screen_ids": [selected.dev[0], selected.holdout[0]]},
        "owner_split": {"split": "holdout"},
        "missing": {"split": None},
        "both": {"screen_ids": [selected.dev[0]]},
    }
    kwargs.update(choices[kind])
    original = Path.read_bytes

    def guarded(path):
        assert path not in (kwargs["recipes"], kwargs["inventory"]), (
            "Guard was too late"
        )
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    with pytest.raises(CaptureError, match="dev|Select"):
        api().create_plan(**kwargs)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "excluded", "wrong_source"])
def test_requires_complete_unique_dev_inventory_and_matching_source_pin(tmp_path, kind):
    kwargs = inputs(tmp_path)
    index = json_bytes(kwargs["inventory"].read_bytes())
    if kind == "missing":
        index["pairs"].pop()
    elif kind == "duplicate":
        index["pairs"].append(index["pairs"][0])
    elif kind == "excluded":
        index["pairs"][0] = {
            **index["pairs"][0],
            "screen": registry().holdout[0],
            "path": "NEVER_READ",
        }
    else:
        value = document()
        value["fork_commit"] = "a" * 40
        kwargs["recipes"].write_bytes(canonical_bytes(value))
    kwargs["inventory"].write_bytes(canonical_bytes(index))
    with pytest.raises(CaptureError, match="inventory|Inventory|source|fork"):
        api().create_plan(**kwargs)


def test_recipe_cannot_target_an_excluded_screen(tmp_path):
    value = recipe(
        targets=[{"screen": registry().holdout[0], "text": "Mining", "match": "exact"}]
    )
    kwargs = inputs(tmp_path, [value])
    with pytest.raises(CaptureError, match="dev"):
        api().create_plan(**kwargs)


def positioned(text, identity, x, y=20, **changes):
    box = [x, y, x + 40, y + 20]
    fields = {
        "input_text": text,
        "source_key": None,
        "bounds": box,
        "glyph_bounds": box,
        "visible_bounds": box,
        "ellipsis_applied": False,
    }
    return element(text, identity, **(fields | changes))


def named_recipe(name, **changes):
    return recipe(
        id=name.lower(),
        key=name,
        replacement=f"{name} extended words",
        targets=[{"screen": "tech-picker", "text": name, "match": "exact"}],
        **changes,
    )


def test_one_global_key_with_three_occurrences_is_rejected_not_split(tmp_path):
    extras = [positioned("Mining", f"root/repeat-{i}", 300 + i * 100) for i in range(2)]
    kwargs = inputs(tmp_path, additions={("tech-picker", "en"): extras})
    with pytest.raises(CaptureError, match="occurrence cap"):
        api().create_plan(**kwargs)


@pytest.mark.parametrize(
    "changes",
    [
        {"actor_path": None},
        {"bounds": None, "warnings": ["unknown_owner"]},
        {"visibility": "partial"},
    ],
)
def test_unprovable_target_geometry_stops_planning(tmp_path, changes):
    kwargs = inputs(
        tmp_path,
        [named_recipe("Alpha")],
        {("tech-picker", "en"): [positioned("Alpha", "root/a", 300, **changes)]},
    )
    with pytest.raises(CaptureError, match="target|Target"):
        api().create_plan(**kwargs)


def test_known_key_on_undeclared_dev_screen_is_not_ignored(tmp_path):
    other = positioned("Mining elsewhere", "root/global", 300, source_keys=["Mining"])
    kwargs = inputs(tmp_path, additions={("options-gameplay", "en"): [other]})
    with pytest.raises(CaptureError, match="undeclared|scope"):
        api().create_plan(**kwargs)


def test_text_selector_cannot_override_contradictory_primary_source_key(tmp_path):
    value = recipe(
        language="de",
        original="Bergbau",
        targets=[{"screen": "options-gameplay", "text": "?", "match": "exact"}],
    )
    kwargs = inputs(
        tmp_path,
        [value],
        {
            ("options-gameplay", "de"): [
                positioned("?", "root/help", 300, source_key="?")
            ]
        },
    )
    with pytest.raises(CaptureError, match="Contradictory.*source"):
        api().create_plan(**kwargs)


def test_missing_source_key_keeps_english_text_selector_fallback(tmp_path):
    plan = api().create_plan(**inputs(tmp_path))
    occurrence = plan["mutations"]["mining-long-en"]["occurrences"][0]
    assert occurrence["source_key"] is None
    assert occurrence["input_text"] == "Mining"
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan


def test_explicit_component_key_allows_a_different_primary_source_key(tmp_path):
    kwargs = inputs(
        tmp_path,
        [named_recipe("Alpha")],
        {
            ("tech-picker", "en"): [
                positioned(
                    "Alpha", "root/a", 300, source_key="?", source_keys=["Alpha"]
                )
            ]
        },
    )
    plan = api().create_plan(**kwargs)
    assert len(plan["mutations"]["alpha"]["occurrences"]) == 1
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan


def test_explicit_source_key_discovers_occurrence_without_a_text_selector(tmp_path):
    kwargs = inputs(
        tmp_path,
        [named_recipe("Alpha"), named_recipe("Beta")],
        {
            ("tech-picker", "en"): [
                positioned("Alpha", "root/a", 300),
                positioned(
                    "composed alpha",
                    "root/composed",
                    450,
                    source_key="Template",
                    source_keys=["Alpha"],
                ),
                positioned("Beta", "root/b", 600),
            ]
        },
    )
    plan = api().create_plan(**kwargs)
    assert len(plan["mutations"]["alpha"]["occurrences"]) == 2
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan


def test_every_declared_target_selector_must_match(tmp_path):
    value = recipe(
        targets=recipe()["targets"]
        + [{"screen": "civilopedia", "text": "Missing", "match": "exact"}]
    )
    kwargs = inputs(tmp_path, [value])
    with pytest.raises(CaptureError, match="selector|target"):
        api().create_plan(**kwargs)


def test_greedy_static_combination_preserves_single_occurrence_share(tmp_path):
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [positioned(n, f"root/{n}", 300 + i * 150) for i, n in enumerate(names)]
    kwargs = inputs(
        tmp_path, [named_recipe(n) for n in names], {("tech-picker", "en"): extras}
    )
    plan = api().create_plan(**kwargs)
    assert sorted(len(b["recipe_ids"]) for b in plan["batches"]) == [1, 1, 2]
    assert plan["policy"]["max_visible_occurrences"] == 2
    assert plan["policy"]["minimum_single_occurrence_share"] == 0.5
    assert plan["density"]["en"] == {
        "single_occurrence_screenshots": 2,
        "mutated_screenshots": 3,
        "share": 2 / 3,
    }
    assert plan["dynamic_split_rate"] is None
    assert plan["calibration"]["mutation_recipe_id"] in {n.lower() for n in names}


@pytest.mark.parametrize(
    "kind",
    ["same_translation_key", "same_owning_actor", "rectangles_with_margin_overlap"],
)
def test_static_conflicts_are_recorded_and_never_combined(tmp_path, kind):
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [positioned(n, f"root/{n}", 300 + i * 150) for i, n in enumerate(names)]
    values = [named_recipe(n) for n in names]
    if kind == "same_translation_key":
        values[1]["key"] = "Alpha"
    elif kind == "same_owning_actor":
        extras[1]["actor_path"] = extras[0]["actor_path"]
    else:
        extras[1] = positioned("Beta", "root/Beta", 347)
    kwargs = inputs(tmp_path, values, {("tech-picker", "en"): extras})
    plan = api().create_plan(**kwargs)
    assert {"recipe_ids": ["alpha", "beta"], "reason": kind} in plan["static_conflicts"]
    assert all(not {"alpha", "beta"} <= set(b["recipe_ids"]) for b in plan["batches"])
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan
    plan["static_conflicts"] = []
    with pytest.raises(CaptureError, match="static conflicts"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def test_inventory_and_recipe_enumeration_order_and_output_location_do_not_change_plan(
    tmp_path,
):
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [positioned(n, f"root/{n}", 300 + i * 150) for i, n in enumerate(names)]
    kwargs = inputs(
        tmp_path, [named_recipe(n) for n in names], {("tech-picker", "en"): extras}
    )
    first = canonical_bytes(api().create_plan(**kwargs))
    for name, field in (("inventory", "pairs"), ("recipes", "recipes")):
        value = json_bytes(kwargs[name].read_bytes())
        value[field].reverse()
        kwargs[name].write_bytes(canonical_bytes(value))
    assert canonical_bytes(api().create_plan(**kwargs)) == first


def test_interfering_pair_splits_deterministically_and_singleton_failure_stops(
    tmp_path,
):
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [positioned(n, f"root/{n}", 300 + i * 150) for i, n in enumerate(names)]
    kwargs = inputs(
        tmp_path, [named_recipe(n) for n in names], {("tech-picker", "en"): extras}
    )
    plan = api().create_plan(**kwargs)
    combined = next(b for b in plan["batches"] if len(b["recipe_ids"]) == 2)
    reason = {
        "kind": "outside_mask_pixels",
        "different_pixels": 1,
        "bounding_box": [0, 0, 1, 1],
        "max_channel_delta": 1,
    }
    assert hasattr(api(), "split_after_interference"), (
        "Deterministic split support is missing"
    )
    split = api().split_after_interference(plan, combined["id"], reason)
    assert len(split["batches"]) == 4
    assert len(plan["batches"]) == 3
    assert split["split_history"][0]["parent"] == combined
    assert split["split_history"][0]["reason"] == reason
    assert canonical_bytes(
        api().split_after_interference(plan, combined["id"], reason)
    ) == canonical_bytes(split)
    with pytest.raises(CaptureError, match="singleton"):
        api().split_after_interference(split, split["batches"][0]["id"], reason)
    with pytest.raises(CaptureError, match="operational|interference"):
        api().split_after_interference(plan, combined["id"], {"kind": "timeout"})


def test_balance_counts_logical_occurrences_per_language_not_recipe_count(tmp_path):
    kwargs = inputs(tmp_path)
    plan = api().create_plan(**kwargs)
    assert plan["primary_balance"]["en"] == {
        "overflow": 0,
        "wrong_language": 0,
        "truncated_text": 1,
        "balanced": False,
    }
    assert plan["primary_balance"]["de"]["balanced"] is False
    assert "runtime_qualification" in plan["production_blockers"]
    assert "primary_class_balance" in plan["production_blockers"]


def test_manifest_reader_rejects_patch_tampering_and_success_claims(tmp_path):
    from copy import deepcopy

    plan = api().create_plan(**inputs(tmp_path))
    assert hasattr(api(), "load_plan"), (
        "The versioned builder-facing manifest reader is missing"
    )
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan
    for change in ("patch", "status", "hash", "density", "unknown"):
        bad = deepcopy(plan)
        if change == "patch":
            bad["batches"][0]["patches"][0]["file"] = "elsewhere/English.properties"
        elif change == "status":
            bad["production_ready"] = True
        elif change == "hash":
            bad["batches"][0]["patch_set_sha256"] = "a" * 64
        elif change == "density":
            bad["density"]["en"]["share"] = 0.1
        else:
            bad["labels"] = []
        with pytest.raises(CaptureError, match="manifest|plan"):
            api().load_plan(canonical_bytes(bad), manifest=MANIFEST)


@pytest.mark.parametrize("field", ["planned_recipe_class_counts", "static_conflicts"])
def test_manifest_reader_checks_derived_recipe_metadata(tmp_path, field):
    plan = api().create_plan(**inputs(tmp_path))
    if field == "planned_recipe_class_counts":
        plan[field] = {"overflow": 999}
    else:
        plan[field] = [
            {"recipe_ids": ["fabricated", "mining-long-en"], "reason": "fake"}
        ]
    with pytest.raises(CaptureError, match="recipe counts|static conflicts"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def refresh_wire_derivatives(plan):
    """Regenerate dependent fields so corruption exercises relationship checks."""
    planner = api()
    observations = {(r["screen"], r["language"]): None for r in plan["inventory"]}
    plan["batches"] = [
        planner._batch(b["recipe_ids"], plan["mutations"], observations)
        for b in plan["batches"]
    ]
    plan["clean_build"] = planner._batch([], plan["mutations"], observations)
    plan["clean_build"]["builder"] = "same_as_mutated_batches"
    plan["density"] = planner._density(plan["batches"])
    plan["primary_balance"] = planner._primary_balance(plan["mutations"])
    plan["production_blockers"] = planner._blockers(plan["primary_balance"])
    plan["calibration"] = planner._calibration(plan["mutations"])
    plan["static_conflicts"] = planner._static_conflicts(plan["mutations"])
    plan["planned_recipe_class_counts"] = planner._recipe_counts(plan["mutations"])


@pytest.mark.parametrize(
    "change",
    [
        "empty_selection",
        "duplicate_selection",
        "unknown_selection",
        "empty_inventory",
        "duplicate_inventory",
        "missing_inventory_language",
    ],
)
def test_manifest_reader_requires_unique_nonempty_selection_and_inventory(
    tmp_path, change
):
    plan = api().create_plan(**inputs(tmp_path))
    if change == "empty_selection":
        plan["screen_ids"] = []
    elif change == "duplicate_selection":
        plan["screen_ids"].append(plan["screen_ids"][0])
    elif change == "unknown_selection":
        plan["screen_ids"].append("not-in-inventory")
    elif change == "empty_inventory":
        plan["inventory"] = []
    elif change == "duplicate_inventory":
        plan["inventory"].append(plan["inventory"][0])
    else:
        plan["inventory"].pop()
    refresh_wire_derivatives(plan)
    with pytest.raises(CaptureError, match="selection|inventory"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def combined_plan(tmp_path):
    names = ("Alpha", "Beta", "Gamma", "Delta")
    extras = [positioned(n, f"root/{n}", 300 + i * 150) for i, n in enumerate(names)]
    return api().create_plan(
        **inputs(
            tmp_path, [named_recipe(n) for n in names], {("tech-picker", "en"): extras}
        )
    )


def test_planner_rejects_semantic_recipe_aliases(tmp_path):
    kwargs = inputs(tmp_path, [recipe(), recipe(id="mining-alias-en")])
    with pytest.raises(CaptureError, match="Duplicate.*edit"):
        api().create_plan(**kwargs)


def test_manifest_reader_rejects_semantic_recipe_aliases(tmp_path):
    from copy import deepcopy

    plan = api().create_plan(**inputs(tmp_path))
    alias = deepcopy(plan["mutations"]["mining-long-en"])
    alias["recipe"]["id"] = "mining-alias-en"
    plan["mutations"]["mining-alias-en"] = alias
    observations = {(r["screen"], r["language"]): None for r in plan["inventory"]}
    plan["batches"] = api()._combine(plan["mutations"], observations, plan["seed"])
    refresh_wire_derivatives(plan)
    assert len({b["id"] for b in plan["batches"]}) < len(plan["batches"])
    with pytest.raises(CaptureError, match="Duplicate.*edit"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def test_manifest_reader_requires_unique_batch_identities(tmp_path):
    plan = api().create_plan(**inputs(tmp_path))
    # Empty batches do not duplicate recipe coverage or alter density.
    plan["batches"] += [{"recipe_ids": []}, {"recipe_ids": []}]
    refresh_wire_derivatives(plan)
    with pytest.raises(CaptureError, match="Duplicate batch identity"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


@pytest.mark.parametrize(
    "change, message",
    [
        ("unknown_screen", "Occurrence scope"),
        ("undeclared_screen", "Occurrence scope"),
        ("wrong_language", "Occurrence scope"),
        ("unselected_target", "Recipe target.*selection"),
        ("empty_occurrences", "No occurrences"),
        ("duplicate_logical", "Duplicate logical occurrence"),
        ("duplicate_draw", "Duplicate occurrence draw"),
        ("over_cap", "occurrence cap"),
        ("contradictory_key", "Contradictory.*source"),
        ("unbound_occurrence", "Unbound occurrence"),
        ("missing_target_selector", "Missing.*selector"),
    ],
)
def test_manifest_reader_checks_occurrence_relationships_after_regeneration(
    tmp_path, change, message
):
    from copy import deepcopy

    plan = combined_plan(tmp_path)
    mutation = plan["mutations"]["alpha"]
    occurrence = mutation["occurrences"][0]
    if change == "unknown_screen":
        occurrence["screen"] = "not-in-inventory"
    elif change == "undeclared_screen":
        occurrence["screen"] = "options-gameplay"
    elif change == "wrong_language":
        occurrence["language"] = "de"
    elif change == "unselected_target":
        plan["screen_ids"].remove("tech-picker")
    elif change == "empty_occurrences":
        mutation["occurrences"] = []
    elif change == "duplicate_logical":
        mutation["occurrences"].append(deepcopy(occurrence))
    elif change == "duplicate_draw":
        occurrence["element_ids"] *= 2
    elif change == "over_cap":
        for i in range(2):
            added = deepcopy(occurrence)
            added["logical_id"] = added["actor_path"] = f"root/additional-{i}"
            added["element_ids"] = [added["logical_id"]]
            mutation["occurrences"].append(added)
    elif change == "contradictory_key":
        occurrence["source_key"] = "?"
    elif change == "unbound_occurrence":
        occurrence["input_text"] = "not the selected text"
    else:
        mutation["recipe"]["targets"].append(
            {"screen": "options-gameplay", "text": "missing", "match": "exact"}
        )
    if change in {"duplicate_logical", "over_cap"}:
        plan["batches"] = [{"recipe_ids": [r]} for r in sorted(plan["mutations"])]
    refresh_wire_derivatives(plan)
    with pytest.raises(CaptureError, match=message):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def test_split_after_interference_manifest_roundtrips(tmp_path):
    plan = combined_plan(tmp_path)
    parent = next(b for b in plan["batches"] if len(b["recipe_ids"]) == 2)
    split = api().split_after_interference(
        plan,
        parent["id"],
        {"kind": "missing_mutation", "recipe_id": parent["recipe_ids"][0]},
    )
    assert api().load_plan(canonical_bytes(split), manifest=MANIFEST) == split


def test_multiple_split_generations_roundtrip_with_full_inventory(tmp_path):
    values, additions = [], {}
    for name, screen in zip(("Alpha", "Beta", "Gamma", "Delta"), registry().dev):
        values.append(
            {
                **named_recipe(name),
                "targets": [{"screen": screen, "text": name, "match": "exact"}],
            }
        )
        additions[screen, "en"] = [positioned(name, f"root/{name}", 300)]
    plan = api().create_plan(**inputs(tmp_path, values, additions))
    assert len(plan["batches"]) == 1
    for kind in (
        "outside_mask_pixels",
        "changed_unmutated_element",
        "missing_mutation",
    ):
        parent = next(b for b in plan["batches"] if len(b["recipe_ids"]) >= 2)
        plan = api().split_after_interference(plan, parent["id"], {"kind": kind})
        assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan


def test_selected_subset_roundtrips_with_complete_dev_inventory(tmp_path, monkeypatch):
    kwargs = inputs(tmp_path)
    kwargs.update(split=None, screen_ids=["tech-picker"])
    plan = api().create_plan(**kwargs)
    assert plan["screen_ids"] == ["tech-picker"]
    assert len(plan["inventory"]) == 10
    manifest = json_bytes(MANIFEST.read_bytes())
    expected = {
        (screen, language["code"])
        for screen in registry().dev
        for language in manifest["languages"]
    }
    assert {(row["screen"], row["language"]) for row in plan["inventory"]} == expected
    reads = []
    original = Path.read_bytes

    def metadata_only(path):
        assert path in {MANIFEST, MANIFEST.with_name("split.json")}, (
            "Loader attempted fixture/payload access"
        )
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", metadata_only)
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan
    assert reads == [MANIFEST, MANIFEST.with_name("split.json")]


def test_manifest_reader_rejects_whole_screen_removal_after_regeneration(tmp_path):
    kwargs = inputs(tmp_path)
    kwargs.update(split=None, screen_ids=["tech-picker"])
    plan = api().create_plan(**kwargs)
    source_hash, split_hash = plan["source_manifest_sha256"], plan["split_sha256"]
    plan["inventory"] = [
        row for row in plan["inventory"] if row["screen"] == "tech-picker"
    ]
    refresh_wire_derivatives(plan)
    assert len(plan["inventory"]) == 2
    assert (plan["source_manifest_sha256"], plan["split_sha256"]) == (
        source_hash,
        split_hash,
    )
    with pytest.raises(CaptureError, match="inventory coverage"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


@pytest.mark.parametrize("authority", ["manifest", "split"])
@pytest.mark.parametrize("change", ["plan_hash", "source_bytes"])
def test_manifest_reader_binds_exact_authoritative_bytes(
    tmp_path, monkeypatch, authority, change
):
    plan = api().create_plan(**inputs(tmp_path))
    manifest = tmp_path / "source-manifest.json"
    split = manifest.with_name("split.json")
    manifest.write_bytes(MANIFEST.read_bytes())
    split.write_bytes(MANIFEST.with_name("split.json").read_bytes())
    if change == "plan_hash":
        field = "source_manifest_sha256" if authority == "manifest" else "split_sha256"
        plan[field] = "a" * 64
    else:
        path = manifest if authority == "manifest" else split
        path.write_bytes(path.read_bytes() + b"\n")
    reads = []
    original = Path.read_bytes

    def metadata_only(path):
        assert path in {manifest, split}, "Loader attempted fixture/payload access"
        reads.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", metadata_only)
    with pytest.raises(CaptureError, match=f"{authority} SHA-256 mismatch"):
        api().load_plan(canonical_bytes(plan), manifest=manifest)
    assert reads == ([manifest] if authority == "manifest" else [manifest, split])


def test_manifest_reader_binds_builder_source_commit_to_authority(tmp_path):
    plan = api().create_plan(**inputs(tmp_path))
    plan["fork_commit"] = "a" * 40
    with pytest.raises(CaptureError, match="fork source"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


@pytest.mark.parametrize("change", ["static", "dynamic", "split_rate", "clean_builder"])
def test_manifest_reader_retains_pending_gates(tmp_path, change):
    plan = api().create_plan(**inputs(tmp_path))
    if change in {"static", "dynamic"}:
        plan["batches"][0]["screenshots"][0]["verification"][change] = "passed"
    elif change == "split_rate":
        plan["dynamic_split_rate"] = 0
    else:
        plan["clean_build"]["builder"] = "stock_apk"
    with pytest.raises(CaptureError, match="manifest"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


@pytest.mark.parametrize(
    "change",
    [
        "unrecorded_split",
        "fake_parent",
        "fake_children",
        "invalid_reason",
        "altered_parent",
        "replayed_event",
        "unsplit_batches",
        "nonobject_reason",
    ],
)
def test_manifest_reader_replays_split_lineage(tmp_path, change):
    from copy import deepcopy

    plan = combined_plan(tmp_path)
    parent = next(b for b in plan["batches"] if len(b["recipe_ids"]) == 2)
    split = api().split_after_interference(
        plan, parent["id"], {"kind": "missing_mutation"}
    )
    event = split["split_history"][0]
    if change == "unrecorded_split":
        split["split_history"] = []
    elif change == "fake_parent":
        event["parent"]["id"] = "batch-invented"
    elif change == "fake_children":
        event["children"] = ["batch-invented"]
    elif change == "invalid_reason":
        event["reason"] = {"kind": "timeout"}
    elif change == "altered_parent":
        event["parent"]["screenshots"][0]["verification"]["dynamic"] = "passed"
    elif change == "replayed_event":
        split["split_history"].append(deepcopy(event))
    elif change == "unsplit_batches":
        split["batches"] = plan["batches"]
        split["density"] = api()._density(split["batches"])
    else:
        event["reason"] = None
    with pytest.raises(CaptureError, match="lineage"):
        api().load_plan(canonical_bytes(split), manifest=MANIFEST)


@pytest.mark.parametrize(
    "change",
    ["omit", "duplicate", "policy", "calibration", "blockers", "occurrence_scope"],
)
def test_manifest_reader_validates_coverage_and_pending_gate_contract(tmp_path, change):
    plan = api().create_plan(**inputs(tmp_path))
    if change == "omit":
        plan["batches"] = []
        plan["density"] = api()._density([])
    elif change == "duplicate":
        plan["batches"] *= 2
        plan["density"] = api()._density(plan["batches"])
    elif change == "policy":
        plan["policy"]["max_visible_occurrences"] = 20
    elif change == "calibration":
        plan["calibration"]["status"] = "passed"
    elif change == "blockers":
        plan["production_blockers"] = ["anything"]
    else:
        plan["mutations"]["mining-long-en"]["occurrences"][0]["screen"] = (
            registry().holdout[0]
        )
    with pytest.raises(CaptureError, match="manifest"):
        api().load_plan(canonical_bytes(plan), manifest=MANIFEST)


def test_zero_or_multiple_draws_do_not_fake_an_occurrence(tmp_path):
    shadow = positioned(
        "Mining", "root/shadow", 300, logical_id="root/mining", decoration=True
    )
    kwargs = inputs(tmp_path, additions={("tech-picker", "en"): [shadow]})
    plan = api().create_plan(**kwargs)
    occurrence = plan["mutations"]["mining-long-en"]["occurrences"][0]
    assert occurrence["element_ids"] == ["root/mining", "root/shadow"]
    assert len(plan["mutations"]["mining-long-en"]["occurrences"]) == 1
    assert occurrence["ellipsis_applied"] is True


@pytest.mark.parametrize("seed", [True, "59", 1.5])
def test_seed_is_a_literal_integer(tmp_path, seed):
    kwargs = inputs(tmp_path)
    kwargs["seed"] = seed
    with pytest.raises(CaptureError, match="seed"):
        api().create_plan(**kwargs)


def test_same_version_code_does_not_hide_wrong_apk_source_provenance(tmp_path):
    kwargs = inputs(tmp_path)
    index = json_bytes(kwargs["inventory"].read_bytes())
    ref = index["pairs"][0]
    pair = tmp_path / ref["path"]
    metadata = json_bytes(pair.read_bytes())
    metadata["build"]["apk_sha256"] = "a" * 64
    pair.write_bytes(canonical_bytes(metadata))
    ref["sha256"] = digest(pair.read_bytes())
    kwargs["inventory"].write_bytes(canonical_bytes(index))
    with pytest.raises(CaptureError, match="provenance|identity"):
        api().create_plan(**kwargs)


@pytest.mark.parametrize(
    "change", ["screen", "language", "state", "build", "protocol", "pair_version"]
)
def test_pair_provenance_is_checked_before_png_or_dump_reads(
    tmp_path, monkeypatch, change
):
    kwargs = inputs(tmp_path)
    index = json_bytes(kwargs["inventory"].read_bytes())
    ref = index["pairs"][0]
    path = tmp_path / ref["path"]
    pair = json_bytes(path.read_bytes())
    payloads = {(path.parent / pair[k]).resolve() for k in ("png", "dump")}
    if change == "screen":
        # Synthetic excluded identity only; no excluded fixture or payload is read.
        pair["screen"] = registry().holdout[0]
        dump_path = path.parent / pair["dump"]
        dump = json_bytes(dump_path.read_bytes())
        dump["screen"] = pair["screen"]
        raw = canonical_bytes(dump)
        dump_path.write_bytes(raw)
        pair["dump_sha256"] = digest(raw)
    elif change == "language":
        pair["language"] = "German" if ref["language"] == "en" else "English"
    elif change == "state":
        pair["state_sha256"] = "a" * 64
    elif change == "build":
        pair["build"]["apk_sha256"] = "a" * 64
    else:
        pair[f"{change}_version" if change == "protocol" else change] = 99
    raw = canonical_bytes(pair)
    path.write_bytes(raw)
    ref["sha256"] = digest(raw)
    kwargs["inventory"].write_bytes(canonical_bytes(index))
    original = Path.read_bytes

    def guarded(candidate):
        assert candidate.resolve() not in payloads, (
            "Payload read before sidecar provenance validation"
        )
        return original(candidate)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    with pytest.raises(CaptureError, match="identity|provenance|protocol"):
        api().create_plan(**kwargs)


@pytest.mark.parametrize("mode", ["default", "explicit_none", "snapshot"])
def test_pair_loader_preserves_default_and_snapshot_readback(
    tmp_path, monkeypatch, mode
):
    from l10n_checker.text_reference import load_pair

    path = write_pair(tmp_path, dump_for())
    pair_raw = path.read_bytes()
    expected = load_pair(path)
    reads = []
    original = Path.read_bytes

    def guarded(candidate):
        reads.append(candidate)
        if mode == "snapshot":
            assert candidate != path, "Snapshot loader reread the sidecar"
        return original(candidate)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    options = {} if mode == "default" else {"pair_bytes": None}
    if mode == "snapshot":
        options["pair_bytes"] = pair_raw
    assert load_pair(path, **options) == expected
    assert reads == ([] if mode == "snapshot" else [path]) + [
        path.parent / expected[0][k] for k in ("png", "dump")
    ]


def test_pair_loader_rejects_empty_snapshot_without_reading_the_sidecar(
    tmp_path, monkeypatch
):
    from l10n_checker.text_reference import load_pair

    path = write_pair(tmp_path, dump_for())

    def forbidden(candidate):
        pytest.fail("Empty snapshot must not fall back to sidecar/payload reads")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    with pytest.raises(ValueError):
        load_pair(path, pair_bytes=b"")


def test_changing_sidecar_cannot_redirect_validated_dev_payloads(tmp_path, monkeypatch):
    kwargs = inputs(tmp_path)
    expected = api().create_plan(**kwargs)
    index = json_bytes(kwargs["inventory"].read_bytes())
    path = (tmp_path / index["pairs"][0]["path"]).resolve()
    pair_raw = path.read_bytes()
    changed = json_bytes(pair_raw)
    # Synthetic excluded metadata only; these payloads do not exist and must not open.
    changed["screen"] = registry().holdout[0]
    changed["png"] = "NEVER_READ_EXCLUDED.png"
    changed["dump"] = "NEVER_READ_EXCLUDED.json"
    foreign_payloads = {path.parent / changed[k] for k in ("png", "dump")}
    changed_raw = canonical_bytes(changed)
    sidecar_reads = payload_attempts = 0
    original = Path.read_bytes

    def changing(candidate):
        nonlocal sidecar_reads, payload_attempts
        if candidate.resolve() == path:
            sidecar_reads += 1
            return pair_raw if sidecar_reads == 1 else changed_raw
        if candidate.resolve() in foreign_payloads:
            payload_attempts += 1
            pytest.fail(
                f"Foreign payload read: sidecar_reads={sidecar_reads}, "
                f"payload_attempts={payload_attempts}"
            )
        return original(candidate)

    monkeypatch.setattr(Path, "read_bytes", changing)
    assert api().create_plan(**kwargs) == expected
    assert sidecar_reads == 1
    assert payload_attempts == 0


def real_inputs(tmp_path):
    """Read only named dev PNG/dump/pair members; no reference/label payloads."""
    import zipfile

    archive = (
        ROOT / "docs/evidence/47/reference-confirmation/confirmed-reference-set.zip"
    )
    prefix = "issue-47-confirmed-references-1271048-20261023"
    refs = []
    with zipfile.ZipFile(archive) as source:
        for screen in registry().dev:
            for lang in ("en", "de"):
                relative = f"{screen}__{lang}"
                folder = tmp_path / relative
                folder.mkdir(parents=True)
                member = f"{prefix}/{relative}"
                raw = source.read(f"{member}/capture.pair.json")
                pair = json_bytes(raw)
                for name in (pair["png"], pair["dump"]):
                    assert Path(name).name == name
                    (folder / name).write_bytes(source.read(f"{member}/{name}"))
                (folder / "capture.pair.json").write_bytes(raw)
                refs.append(
                    {
                        "screen": screen,
                        "language": lang,
                        "path": f"{relative}/capture.pair.json",
                        "sha256": digest(raw),
                    }
                )
    inventory = tmp_path / "inventory.json"
    inventory.write_bytes(canonical_bytes({"schema_version": 1, "pairs": refs}))
    return {
        "manifest": MANIFEST,
        "recipes": ROOT / "fixtures/stage3/recipes-v1.json",
        "inventory": inventory,
        "seed": 59,
        "split": "dev",
    }


def test_committed_dev_catalog_is_balanced_and_help_has_one_occurrence(tmp_path):
    plan = api().create_plan(**real_inputs(tmp_path))
    for language in ("en", "de"):
        assert plan["primary_balance"][language] == {
            "overflow": 2,
            "wrong_language": 2,
            "truncated_text": 2,
            "balanced": True,
        }
        assert plan["density"][language]["share"] >= 0.5
        assert len(plan["mutations"][f"help-overflow-{language}"]["occurrences"]) == 1
    assert len(plan["mutations"]["worker-foreign-en"]["occurrences"]) == 2
    assert "primary_class_balance" not in plan["production_blockers"]
    assert plan["calibration"]["mutation_recipe_id"] == "help-overflow-en"
    assert api().load_plan(canonical_bytes(plan), manifest=MANIFEST) == plan
