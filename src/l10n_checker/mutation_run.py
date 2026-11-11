"""Dev-only mutation run, strict gates, immutable handoffs and offline replay."""

import fcntl
import io
import math
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from PIL import Image

from l10n_checker.app_data import (
    DATA_ROOTS,
    cleanup_policy,
    hook_paths,
    unlink_command,
    validate_tar,
)
from l10n_checker.capture import (
    REPO_ROOT,
    SETTINGS_PATH,
    CaptureError,
    Device,
    preserve_cleanup,
    retain_cleanup,
)
from l10n_checker.mutation_catalog import ApkTools, no_symlinks, read_catalog, require
from l10n_checker.mutation_cli import build_requests
from l10n_checker.mutation_device import (
    assert_idle,
    data_inventory,
    environment_check,
    execute_stages,
    failure_details,
    install_verified,
    installed_identity,
    inventory_changes,
    preservation_policy,
    preservation_report,
    read_app_data,
    save_backup,
)
from l10n_checker.mutation_outside_rule import (
    assess_outside_rule,
    outside_rule_policy,
    verify_outside_repeat,
)
from l10n_checker.mutation_plan import load_plan, split_after_interference
from l10n_checker.mutation_verify import (
    compare_rgba,
    intended_occurrences_passed,
    occurrence_matrix,
    semantic_side_effects,
    side_effect_policy,
    split_rate,
    verify_screen,
)
from l10n_checker.screen_capture import (
    HOOK_DIRECTORY_OPERATION,
    capture_manifest,
    manifest_output_directory,
    planned_hook_outputs,
    planned_operations,
    prepare_device,
    save_inventory,
    write_json,
)
from l10n_checker.screen_manifest import Inputs, digest, json_bytes
from l10n_checker.text_dump import canonical_bytes, load_dump, rgba_digest
from l10n_checker.text_reference import load_pair


def contained(root, relative):
    require(
        type(relative) is str
        and relative
        and not Path(relative).is_absolute()
        and ".." not in Path(relative).parts,
        "Unsafe run artifact path",
    )
    path = no_symlinks(root / relative)
    require(path.is_relative_to(root), "Run artifact escapes output")
    return path


def retained_files(folder):
    """Exact regular-file membership, rejecting symlinks even in unused outputs."""
    files = {}
    for path in sorted(folder.rglob("*")):
        no_symlinks(path)
        require(path.is_file() or path.is_dir(), "Unsupported run evidence entry")
        name = str(path.relative_to(folder))
        if path.is_file() and name != "evidence-index.json":
            files[name] = digest(path.read_bytes())
    return files


def capture_directory(folder, batch_id, role):
    require(role in {"clean", "calibration", "mutation"}, "Unknown capture role")
    return contained(folder, f"artifacts/{role}/{batch_id}")


def expected_capture_keys(catalog, *, measurement_only=False):
    roles = [
        (catalog.control["request"]["id"], "clean"),
        (catalog.calibration["request"]["id"], "calibration"),
    ]
    if not measurement_only:
        roles += [(batch["id"], "mutation") for batch in catalog.plan["batches"]]
    return {
        (identity, role, screen, language, n)
        for identity, role in roles
        for screen in catalog.plan["screen_ids"]
        for language in ("en", "de")
        for n in (1, 2)
    }


def verified_pair(inputs, folder, record, *, evidence=None):
    require(
        record["screen"] in {s.id for s in inputs.screens()}
        and record["language"] in {"en", "de"}
        and type(record["pass"]) is int
        and record["pass"] in {1, 2},
        "Pair selection outside approved dev scope",
    )
    path = contained(folder, record["pair"])
    raw = (
        path.read_bytes() if evidence is None else evidence.read(folder, record["pair"])
    )
    if "pair_sha256" in record:
        require(digest(raw) == record["pair_sha256"], "Pair sidecar hash mismatch")
    pair = json_bytes(raw)
    state = inputs.states[record["screen"], record["language"]]
    language = {"en": "English", "de": "German"}[record["language"]]
    require(
        pair.get("pair_version") == 1
        and pair.get("protocol_version") == 2
        and pair.get("screen") == record["screen"]
        and pair.get("language") == language
        and pair.get("build") == inputs.manifest.build.model_dump()
        and pair.get("state_sha256") == digest(canonical_bytes(state)),
        "Pair provenance differs from effective manifest",
    )
    for key in ("png", "dump"):
        contained(path.parent, pair[key])
    if evidence is None:
        loaded = load_pair(path, pair_bytes=raw)
    else:
        png = evidence.read(path.parent, pair["png"])
        raw_dump = evidence.read(path.parent, pair["dump"])
        require(
            digest(png) == pair["png_sha256"]
            and rgba_digest(png) == pair["rgba_sha256"]
            and digest(raw_dump) == pair["dump_sha256"],
            "Capture pair hash mismatch",
        )
        with Image.open(io.BytesIO(png)) as image:
            size = list(image.size)
        dump = load_dump(
            raw_dump,
            expected={
                "screen": pair["screen"],
                "language": pair["language"],
                "state_sha256": pair["state_sha256"],
                "image_size": size,
                "build_version_code": int(pair["build"]["version_code"]),
            },
        )
        loaded = pair, png, raw_dump, dump
    require(
        loaded[3].image_size == inputs.manifest.resolution,
        "Capture resolution differs from authority",
    )
    return loaded


def write_handoff(catalog, plan, batch_id, reason, folder, manifest):
    new = split_after_interference(plan, batch_id, reason)
    raw = canonical_bytes(new)
    load_plan(raw, manifest=manifest)
    requests = canonical_bytes(build_requests(new))
    folder = no_symlinks(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "plan.json").write_bytes(raw)
    (folder / "build-requests.json").write_bytes(requests)
    handoff = {
        "handoff_version": 1,
        "parent_catalog_sha256": catalog.sha256,
        "plan_sha256": digest(raw),
        "requests_sha256": digest(requests),
        "builder_content_sha256": catalog.data["builder"]["content_sha256"],
        "builder_session": "part-b Unciv-59b; owner approval required before any build",
        "device_authorization_for_new_catalog": "required_before_install",
        "status": "awaiting_builder_approval",
    }
    write_json(folder / "handoff.json", handoff)
    return new, handoff


def nonpixel_passed(verification):
    """The exception never substitutes for intended occurrences or layout gates."""
    return not verification[
        "changed_unmutated_elements"
    ] and intended_occurrences_passed(verification)


def record_semantic_review(record):
    verification = record["verification"]
    record["side_effects"] = semantic_side_effects(verification) if verification else []
    record["qualified"] = bool(
        verification and intended_occurrences_passed(verification)
    )


def outside_proof(record, assessment=None):
    return {
        "assessment": assessment,
        "repeat_state": "control" if record["role"] == "clean" else "pending",
        "repeat": None,
        "pair_binding": None,
        "used": False,
    }


def measure_outside_record(stable, first_png, second_png, before, after, paired):
    stable["qualified"] = False
    stable["outside_rule"] = outside_proof(stable)
    try:
        assessment = assess_outside_rule(
            first_png, second_png, before, after, stable["verification"]
        )
        stable["outside_rule"]["assessment"] = assessment
        require(
            assessment["measurements_complete"] is True
            and assessment["local_criteria_passed"] is True,
            "Outside-rule local measurement failed",
        )
        key = (stable["batch_id"], stable["role"], stable["screen"], stable["language"])
        require((key, stable["pass"]) not in paired, "Duplicate outside-rule pass")
        paired[key, stable["pass"]] = stable
        if stable["pass"] == 2:
            require((key, 1) in paired, "Missing forward outside-rule proof")
            require(
                confirm_outside_pair(paired[key, 1], stable),
                "Outside-rule exact repeat failed",
            )
    except (CaptureError, ValueError, KeyError, TypeError) as exc:
        stable["outside_rule"]["repeat_state"] = "failed"
        stable["outside_rule"]["error"] = str(exc)
        return str(exc)
    return None


def confirm_outside_pair(forward, reverse):
    """Finalize BOTH comparisons only from an exact reverse measurement."""
    repeat = verify_outside_repeat(
        forward["outside_rule"]["assessment"], reverse["outside_rule"]["assessment"]
    )
    binding = {
        name: {
            "pair_sha256": shot["pair_sha256"],
            "control_pair_sha256": shot["control_pair_sha256"],
        }
        for name, shot in (("forward", forward), ("reverse", reverse))
    }
    for shot in (forward, reverse):
        proof = shot["outside_rule"]
        proof.update(
            repeat=repeat,
            pair_binding=binding,
            repeat_state="confirmed" if repeat["passed"] is True else "failed",
            used=repeat["passed"] is True
            and proof["assessment"]["rule_needed"] is True,
        )
        shot["qualified"] = repeat["passed"] is True and nonpixel_passed(
            shot["verification"]
        )
    return repeat["passed"] is True


def outside_usage(catalog, screenshots, outcome):
    """Expected batch scope never shrinks to a partial sample or includes controls."""
    expected = sorted(
        expected_capture_keys(catalog)
        - expected_capture_keys(catalog, measurement_only=True)
    )
    expected += sorted(
        k
        for k in expected_capture_keys(catalog, measurement_only=True)
        if k[1] == "calibration"
    )
    shots = [r for r in screenshots if r["role"] != "clean"]

    def tally(keys, observed):
        needed = [
            r
            for r in observed
            if r["verification"]["pixels"]["outside"]["different_pixels"] > 0
        ]
        used = [r for r in needed if r["outside_rule"]["used"]]
        pending = [r for r in needed if r["outside_rule"]["repeat_state"] == "pending"]
        unique = lambda rows: len(
            {(r["batch_id"], r["role"], r["screen"], r["language"]) for r in rows}
        )
        denominator = len(keys)
        return {
            "expected_frames": denominator,
            "observed_frames": len(observed),
            "needed_frames": len(needed),
            "used_frames": len(used),
            "pending_frames": len(pending),
            "missing_measurement_frames": sum(
                (r["outside_rule"]["assessment"] or {}).get("measurements_complete")
                is not True
                for r in observed
            ),
            "expected_unique_pairs": len({k[:4] for k in keys}),
            "observed_unique_pairs": unique(observed),
            "used_unique_pairs": unique(used),
            "needed_share_expected": len(needed) / denominator if denominator else None,
            "used_share_expected": len(used) / denominator if denominator else None,
            "used_share_observed": len(used) / len(observed) if observed else None,
            "complete": len(observed) == denominator,
        }

    scopes = []
    dimensions = [
        (),
        ("role",),
        ("language",),
        ("pass",),
        ("role", "language"),
        ("role", "pass"),
        ("role", "language", "pass"),
        ("batch_id", "role"),
        ("batch_id", "role", "language"),
        ("batch_id", "role", "pass"),
        ("batch_id", "role", "language", "pass"),
    ]
    fields = ("batch_id", "role", "screen", "language", "pass")
    for dims in dimensions[1:]:
        for values in sorted(
            {tuple(k[fields.index(d)] for d in dims) for k in expected}
        ):
            selection = dict(zip(dims, values, strict=True))
            keys = [
                k
                for k in expected
                if all(k[fields.index(d)] == v for d, v in selection.items())
            ]
            observed = [
                r for r in shots if all(r[d] == v for d, v in selection.items())
            ]
            scopes.append({**selection, **tally(keys, observed)})
    pauses = [
        {
            "batch_id": s["batch_id"],
            "role": s["role"],
            "used_frames": s["used_frames"],
            "expected_frames": s["expected_frames"],
            "recommendation": "stop; discuss a separately approved fork-side alternative",
        }
        for s in scopes
        if set(s) >= {"batch_id", "role"}
        and "language" not in s
        and "pass" not in s
        and s["complete"]
        and s["used_frames"] * 10 > s["expected_frames"]
    ]
    return {
        "version": 1,
        "engineering_stop": {
            "greater_than_share": 0.10,
            "scope": "completed-batch-combined-EN-DE",
            "controls_excluded": True,
        },
        "outcome": outcome,
        "global": tally(expected, shots),
        "scopes": scopes,
        "engineering_pauses": pauses,
    }


def implementation_hashes():
    names = (
        "mutation_run.py",
        "mutation_catalog.py",
        "mutation_device.py",
        "mutation_verify.py",
        "mutation_outside_rule.py",
        "mutation_diagnostics.py",
        "mutation_cli.py",
        "mutation_plan.py",
        "mutation_recipes.py",
        "screen_manifest.py",
        "screen_capture.py",
        "hook.py",
        "text_dump.py",
        "text_reference.py",
        "capture.py",
        "app_data.py",
    )
    return {name: digest((Path(__file__).parent / name).read_bytes()) for name in names}


class MutationRun:
    def __init__(
        self,
        catalog,
        inputs,
        folder,
        *,
        approved_root,
        device,
        tools,
        measurement_only=False,
        run_version=6,
    ):
        approved_root = manifest_output_directory(approved_root, False)
        folder = manifest_output_directory(folder, False)
        require(
            folder != approved_root and folder.is_relative_to(approved_root),
            "Run output must be beneath approved root",
        )
        require(
            inputs.capture_selection(["en", "de"])["screen_ids"]
            == catalog.plan["screen_ids"]
            and inputs.source_manifest_sha256
            == catalog.data["inputs"]["manifest"]["sha256"],
            "Capture selection/authority differs from catalog",
        )
        require(not inputs.contains_holdout, "Mutation entry point accepts dev only")
        folder.mkdir(mode=0o700, parents=True, exist_ok=False)
        (folder / "private").mkdir(mode=0o700)
        (
            self.folder,
            self.approved_root,
            self.catalog,
            self.inputs,
            self.device,
            self.tools,
        ) = folder, approved_root, catalog, inputs, device, tools
        self.counter = 0
        self.needs_restore = False
        self.restored = False
        self.restore_error = None
        self.restore_attempted = False
        self.original_inventory = None
        self.last_inventory = None
        self.allowed_outputs = set()
        self.clean = {}
        self.plan = catalog.plan
        self.journal = {
            "status": "created",
            "preservation_policy": preservation_policy(),
            "operations": [],
            "live_provider_requests": 0,
            "api_spend_usd": 0,
        }
        self.content = {
            "mutation_run_version": 2 if measurement_only else run_version,
            "preservation_policy": preservation_policy(),
            "status": "not_run",
            "capture_set_qualified": False,
            "labels_created": False,
            "catalog_sha256": catalog.sha256,
            "builder_content_sha256": catalog.data["builder"]["content_sha256"],
            "toolchain_sha256": catalog.data["toolchain"]["sha256"],
            "signing": catalog.data["signing"],
            "source_commit": catalog.data["source_commit"],
            "source_inputs": catalog.data["inputs"],
            "implementation_hashes": implementation_hashes(),
            "screen_ids": catalog.plan["screen_ids"],
            "languages": ["en", "de"],
            "passes": ["forward", "reverse"],
            "screenshots": [],
            "calibration_status": "not_run",
            "downgrade_verified": False,
            "restoration_verified": False,
            "dynamic_tests": [],
            "split_history": catalog.plan["split_history"],
            "dynamic_split_rate": split_rate([]),
            "density": catalog.plan["density"],
        }
        if measurement_only:
            self.content.update(measurement_only=True, measurement_complete=False)
        else:
            self.content["cleanup_policy"] = cleanup_policy()
            self.journal["cleanup_policy"] = cleanup_policy()
            if run_version == 5:
                self.content["outside_rule_policy"] = outside_rule_policy()
            else:
                self.content["side_effect_policy"] = side_effect_policy()
            self.journal["implementation_hashes"] = self.content[
                "implementation_hashes"
            ]
        self.checkpoint()

    def checkpoint(self):
        if self.content.get("measurement_only"):
            require(
                all(
                    "outside_rule" not in r and "side_effects" not in r
                    for r in self.content["screenshots"]
                ),
                "Measurement cannot convert existing normal evidence",
            )
            self.content["mutation_run_version"] = 2
            self.content.pop("outside_rule_policy", None)
            self.content.pop("outside_rule_usage", None)
            self.content.pop("side_effect_policy", None)
            self.journal.pop("implementation_hashes", None)
            # This mode can never publish a calibration or run success, even at
            # intermediate/error checkpoints or when every comparison is zero.
            self.content.update(
                calibration_status="failed", capture_set_qualified=False
            )
            if self.content["status"] != "restoration_failed":
                self.content["status"] = "failed"
            self.journal.update(
                measurement_only=True,
                measurement_complete=self.content["measurement_complete"],
            )
        if self.content.get("mutation_run_version") == 5:
            self.content["outside_rule_usage"] = outside_usage(
                self.catalog, self.content["screenshots"], self.content["status"]
            )
        self.content["observed_occurrence_matrix"] = occurrence_matrix(
            self.content["screenshots"]
        )
        self.content["dynamic_split_rate"] = split_rate(self.content["dynamic_tests"])
        self.content["screenshots"].sort(
            key=lambda r: (r["batch_id"], r["pass"], r["language"], r["screen"])
        )
        raw = canonical_bytes(self.content)
        (self.folder / "mutation-manifest.json").write_bytes(raw)
        (self.folder / "mutation-manifest.sha256").write_text(digest(raw) + "\n")
        write_json(self.folder / "journal.json", self.journal)

    def environment(self, build):
        return environment_check(
            build, self.folder / "environment" / f"{self.counter:03d}"
        )

    def install(self, record):
        self.counter += 1
        folder = self.folder / "private" / f"install-{self.counter:03d}"
        # Parent is private too; each transaction keeps its own verified backup.
        folder.parent.mkdir(mode=0o700, exist_ok=True)
        self.restored = False
        if record["build"]["version_code"] != "1271048":
            self.restore_attempted = False
            self.restore_error = None
            self.content["restoration_verified"] = False
        try:
            result = install_verified(
                self.device,
                self.catalog.apk_path(record),
                record["build"],
                self.catalog.data["signing"]["reference_certificate_sha256"],
                tools=self.tools,
                folder=folder,
                environment=self.environment,
                previous_inventory=self.last_inventory,
                reference_restoration=record["build"]["version_code"] == "1271048",
            )
            self.journal["operations"].append(
                {
                    "kind": "install",
                    "receipt": str((folder / "install.json").relative_to(self.folder)),
                    "sha256": digest(canonical_bytes(result)),
                }
            )
            self.needs_restore = True
            self.last_inventory = json_bytes(
                (folder / "after/inventory.json").read_bytes()
            )
            return result
        finally:
            receipt = folder / "install.json"
            if receipt.exists():
                state = json_bytes(receipt.read_bytes())
                if state.get("install_attempted"):
                    self.needs_restore = True
                    if record["build"]["version_code"] == "1271048":
                        self.restore_attempted = True
                        self.content["restoration_verified"] = (
                            state.get("identity_verified") is True
                        )
            self.checkpoint()

    def reference(self):
        return {
            "apk": self.catalog.data["reference"]["apk"],
            "build": self.inputs.manifest.build.model_dump(),
        }

    def restore(self):
        if self.restored:
            return
        if self.restore_error is not None:
            raise getattr(
                self,
                "restore_failure",
                CaptureError(
                    "Reference restoration already attempted; stop without retry: "
                    + str(self.restore_error)
                ),
            )
        try:
            self._restore_once()
        except BaseException as exc:
            self.restore_error = str(exc)
            self.restore_failure = exc
            raise

    def _restore_once(self):
        if self.restored:
            return
        require(
            self.restore_error is None,
            "Reference restoration already failed; stop without retry: "
            + str(self.restore_error),
        )
        primary = None
        if not self.restore_attempted:
            try:
                self.install(self.reference())
            except BaseException as exc:  # noqa: BLE001 - observe identity/data independently
                primary = exc
        try:
            with preserve_cleanup(self.device.unroot, "Final unroot"):
                self._verify_restoration()
        except BaseException as exc:
            if primary is None:
                raise
            retain_cleanup(primary, exc, "Final reference verification")
        if primary is not None:
            raise primary
        self.restored = True
        self.checkpoint()

    def _verify_restoration(self):
        observed = installed_identity(
            self.device, self.tools, self.folder / "private/final-apk"
        )
        require(
            observed["version_code"] == "1271048"
            and observed["apk_sha256"] == self.inputs.manifest.build.apk_sha256
            and observed["certificate_sha256"]
            == self.catalog.data["signing"]["reference_certificate_sha256"],
            "Final 1271048 restoration identity failed",
        )
        self.content["restoration_verified"] = True
        self.checkpoint()
        if self.original_inventory is not None:
            current = data_inventory(
                read_app_data(
                    self.device,
                    evidence_dir=self.folder / "private/reads",
                    purpose=f"reference-{self.counter:03d}",
                )
            )
            write_json(self.folder / "private/final-inventory.json", current)
            relative = f"private/reference-{self.counter:03d}-inventory.json"
            write_json(self.folder / relative, current)
            prior = preservation_report(self.last_inventory, current)
            changes = inventory_changes(self.original_inventory, current)
            self.journal["restoration_data_changes"] = changes
            self.journal["restoration_preservation"] = preservation_report(
                self.original_inventory, current
            )
            self.journal.setdefault("restoration_checks", []).append(
                {
                    "inventory": relative,
                    "allowed_outputs": [],
                    "prior_preservation": prior,
                    "preservation": self.journal["restoration_preservation"],
                }
            )
            self.checkpoint()
            require(
                not self.journal["restoration_preservation"]["unexpected_changes"]
                and not prior["unexpected_changes"],
                "Original app data not restored; backups retained, no repair",
            )
            self.last_inventory = current
        self.checkpoint()

    def probe(self):
        assert_idle(self.device)
        observed = installed_identity(
            self.device, self.tools, self.folder / "private/initial-apk"
        )
        reference = self.reference()["build"]
        require(
            observed["certificate_sha256"]
            == self.catalog.data["signing"]["reference_certificate_sha256"],
            "Starting installed certificate differs from catalog",
        )
        require(
            all(observed[k] == reference[k] for k in ("version_code", "apk_sha256")),
            "Starting installed package is not pinned 1271048",
        )
        environment_check(reference, self.folder / "environment/initial")
        initial = read_app_data(
            self.device,
            evidence_dir=self.folder / "private/reads",
            purpose="original-before",
        )
        self.original_inventory = data_inventory(initial)
        self.last_inventory = self.original_inventory
        self.journal["original_backup"] = save_backup(
            self.folder / "private/original", initial
        )
        readback = data_inventory(
            read_app_data(
                self.device,
                evidence_dir=self.folder / "private/reads",
                purpose="original-readback",
            )
        )
        write_json(self.folder / "private/original-readback.json", readback)
        self.journal["original_readback_preservation"] = preservation_report(
            self.original_inventory, readback
        )
        self.checkpoint()
        require(
            not self.journal["original_readback_preservation"]["unexpected_changes"],
            "Initial backup changed during readback",
        )
        self.last_inventory = readback
        self.install(self.catalog.control)
        self.install(self.reference())
        self.needs_restore = False
        self.restore()
        self.content["downgrade_verified"] = True
        self.checkpoint()

    def capture(self, record, role, *, measurement_only=False):
        measurement_only = measurement_only or self.content.get(
            "measurement_only", False
        )
        outside_gate = (
            self.content["mutation_run_version"] == 5 and not measurement_only
        )
        semantic_review = (
            self.content["mutation_run_version"] == 6 and not measurement_only
        )
        if role == "calibration" and not measurement_only:
            # Attempted is not not_run: any early exit stays failed until every
            # calibration gate below has completed, including paired-pass proof.
            self.content["calibration_status"] = "failed"
            self.checkpoint()
        if measurement_only:
            self.content.update(measurement_only=True, measurement_complete=False)
            self.checkpoint()
            require(
                role in {"clean", "calibration"}
                and record
                == (
                    self.catalog.control
                    if role == "clean"
                    else self.catalog.calibration
                ),
                "Measurement capture accepts only authorized control/calibration artifacts",
            )
        self.install(record)
        effective = self.inputs.with_build(record["build"])
        root = capture_directory(self.folder, record["request"]["id"], role)
        root.mkdir(parents=True, exist_ok=False)
        (root / "effective-manifest.json").write_bytes(effective.manifest_bytes)
        before = data_inventory(
            read_app_data(
                self.device, evidence_dir=root / "reads", purpose="capture-preflight"
            )
        )
        write_json(root / "before-inventory.json", before)
        preflight = preservation_report(self.last_inventory, before)
        write_json(root / "preflight-preservation.json", preflight)
        self.checkpoint()
        require(
            not preflight["unexpected_changes"], "Capture preflight app-data change"
        )
        prepared = prepare_device(
            self.device, effective, root / "prepare", ["en", "de"]
        )
        prepared_preservation = preservation_report(
            before, prepared["starting_inventory"]
        )
        write_json(root / "prepare-preservation.json", prepared_preservation)
        require(
            not prepared_preservation["unexpected_changes"],
            "Capture preparation app-data drift; no writes",
        )
        allowed = set()
        for output in prepared["planned_hook_output_operations"]:
            allowed.update("private:" + output[name] for name in ("file", "temporary"))
        require(
            not (allowed - {"private:files/l10n-hook"}) & set(before),
            "Prepared hook output already exists",
        )

        failures = []
        outside_fatal = []
        paired = {}
        raw_repeats = {}
        capture_root = root / "capture"
        if role == "calibration":
            ids = [self.plan["calibration"]["mutation_recipe_id"]]
        elif role == "clean":
            ids = []
        else:
            ids = next(
                b["recipe_ids"]
                for b in self.plan["batches"]
                if b["id"] == record["request"]["id"]
            )
        mutations = [self.plan["mutations"][identity] for identity in ids]

        def on_pair(captured):
            pair, png, raw_dump, dump = verified_pair(effective, capture_root, captured)
            key = (captured["screen"], captured["language"], captured["pass"])
            raw_repeats[key] = (pair["rgba_sha256"], raw_dump)
            raw_repeat_ok = (
                key[2] == 1 or raw_repeats.get((*key[:2], 1)) == raw_repeats[key]
            )
            pair_path = capture_root / captured["pair"]
            stable = {
                "batch_id": record["request"]["id"],
                "role": role,
                "build": record["build"],
                "build_identity_sha256": record["build_identity_sha256"],
                "patch_set_sha256": record["request"]["patch_set_sha256"],
                "effective_manifest_sha256": effective.sha256,
                "screen": captured["screen"],
                "language": captured["language"],
                "pass": captured["pass"],
                "state_sha256": pair["state_sha256"],
                "pair": str(pair_path.relative_to(self.folder)),
                "pair_sha256": digest(pair_path.read_bytes()),
                "png_sha256": pair["png_sha256"],
                "rgba_sha256": pair["rgba_sha256"],
                "dump_sha256": pair["dump_sha256"],
                "recipe_ids": ids,
                "verification": None,
            }
            stable["batch_recipe_ids"] = ids
            stable["recipe_ids"] = [
                identity
                for identity in ids
                if any(
                    (o["screen"], o["language"]) == key[:2]
                    for o in self.plan["mutations"][identity]["occurrences"]
                )
            ]
            if role == "clean":
                self.clean[key] = (png, dump, stable["pair_sha256"])
                if outside_gate:
                    stable["outside_rule"] = outside_proof(stable)
                    stable["qualified"] = False
            else:
                clean_png, clean_dump, clean_sha = self.clean[key]
                verification = verify_screen(
                    clean_png, png, clean_dump, dump, mutations
                )
                stable.update(control_pair_sha256=clean_sha, verification=verification)
                if outside_gate:
                    error = measure_outside_record(
                        stable, clean_png, png, clean_dump, dump, paired
                    )
                    if error:
                        outside_fatal.append(error)
                if measurement_only:
                    passed = verification["passed"]
                elif outside_gate:
                    passed = nonpixel_passed(verification)
                else:
                    passed = intended_occurrences_passed(verification)
                if not passed:
                    failures.append(stable)
            if semantic_review:
                record_semantic_review(stable)
            self.content["screenshots"].append(stable)
            self.checkpoint()
            if outside_fatal and not measurement_only:
                raise CaptureError("Fatal outside-rule STOP: " + outside_fatal[0])
            if not measurement_only:
                require(
                    raw_repeat_ok,
                    "Forward/reverse RGBA or raw dump repeatability failure",
                )
            if failures and not measurement_only:
                raise CaptureError("Strict dynamic gate failed; no further captures")

        summary = capture_manifest(
            self.device,
            effective,
            capture_root,
            ["en", "de"],
            device_plan=root / "prepare/device-plan.json",
            on_pair=on_pair,
            fail_fast=True,
            variant=role,
        )
        errors = {
            key: summary[key]
            for key in ("fatal_error_details", "cleanup_errors")
            if summary.get(key)
        }
        failed_records = [
            {
                key: captured[key]
                for key in ("screen", "language", "pass", "error_details")
            }
            for captured in summary.get("records", [])
            if captured.get("error_details")
        ]
        if failed_records:
            errors["records"] = failed_records
        if errors:
            self.journal.setdefault("capture_errors", []).append(
                {
                    "batch_id": record["request"]["id"],
                    "role": role,
                    "receipt": str(
                        (capture_root / "summary.json").relative_to(self.folder)
                    ),
                    **errors,
                }
            )
            self.checkpoint()
        after_archives = read_app_data(
            self.device, evidence_dir=root / "reads", purpose="capture-after"
        )
        save_backup(root / "after-capture", after_archives)
        after = data_inventory(after_archives)
        changes = inventory_changes(before, after)
        preservation = preservation_report(before, after)
        self.journal.setdefault("capture_data_checks", []).append(
            {
                "batch_id": record["request"]["id"],
                "role": role,
                "preflight_preservation": preflight,
                "changes": changes,
                "preservation": preservation,
            }
        )
        self.checkpoint()
        require(
            not preservation["unexpected_changes"],
            "Unexpected app-data change during capture",
        )
        self.last_inventory = after
        require(
            summary.get("hook_cleanup", {}).get("status") == "verified",
            "Capture hook cleanup failed or missing; no dynamic split",
        )
        require(
            not summary.get("cleanup_errors"),
            "Capture cleanup failed; no dynamic split",
        )
        require(
            summary.get("settings_restored"),
            "Capture did not restore original settings",
        )
        if measurement_only:
            require(
                not errors
                and not summary.get("fatal_error")
                and summary.get("saves_unchanged") is True,
                "Measurement capture operational failure",
            )
            expected = {
                (screen, language, n)
                for screen in self.plan["screen_ids"]
                for language in ("en", "de")
                for n in (1, 2)
            }
            records = summary.get("records", [])
            actual = [(r["screen"], r["language"], r["pass"]) for r in records]
            require(
                len(actual) == len(expected)
                and set(actual) == expected
                and all(r.get("status") == "captured" for r in records),
                "Incomplete measurement capture scope",
            )
            comparisons = summary.get("comparisons", [])
            keys = [(c["screen"], c["language"]) for c in comparisons]
            require(
                len(keys) == len(expected) // 2
                and set(keys) == {(s, language) for s, language, _ in expected}
                and all(
                    c.get("status") in {"identical", "different"}
                    and c.get("dump_status") in {"identical", "different"}
                    for c in comparisons
                ),
                "Incomplete measurement repeat comparisons",
            )
            repeatable = all(
                c["status"] == c["dump_status"] == "identical" for c in comparisons
            )
            require(
                summary.get("status") == ("complete" if repeatable else "failed"),
                "Measurement summary is not a repeat-only failure",
            )
            self.content.setdefault("measurement_captures", []).append(
                {
                    "batch_id": record["request"]["id"],
                    "role": role,
                    "summary": str(
                        (capture_root / "summary.json").relative_to(self.folder)
                    ),
                    "repeatability_passed": repeatable,
                }
            )
            self.checkpoint()
            return {"passed": False, "measurement_complete": True}
        require(
            not outside_fatal, "Fatal outside-rule STOP: " + "; ".join(outside_fatal)
        )
        if failures:
            if role == "calibration":
                self.content["calibration_status"] = "failed"
                self.checkpoint()
                return {"passed": False}
            failure = failures[0]
            v = failure["verification"]
            kind = "missing_mutation"
            if outside_gate:
                if v["pixels"]["outside"]["different_pixels"]:
                    kind = "outside_mask_pixels"
                elif v["changed_unmutated_elements"]:
                    kind = "changed_unmutated_element"
            reason = {
                "kind": kind,
                "screen": failure["screen"],
                "language": failure["language"],
                "pass": failure["pass"],
                "verification_sha256": digest(canonical_bytes(v)),
            }
            require(len(ids) > 1, "Failing singleton stops qualification")
            self.plan, handoff = write_handoff(
                self.catalog,
                self.plan,
                record["request"]["id"],
                reason,
                self.folder / "builder-handoff",
                self.inputs.path,
            )
            self.content["dynamic_tests"].append(
                {"id": record["request"]["id"], "recipe_ids": ids, "split": True}
            )
            self.content.update(
                status="awaiting_builder_approval",
                split_history=self.plan["split_history"],
                density=self.plan["density"],
                handoff=handoff,
            )
            self.checkpoint()
            raise CaptureError(
                "Split requires a new catalog: awaiting builder approval"
            )
        require(
            summary["status"] == "complete", "Capture operational/repeatability failure"
        )
        require(
            not errors and summary.get("saves_unchanged") is True,
            "Capture operational/save failure",
        )
        expected = {
            (s, language, n)
            for s in self.inputs.capture_selection(["en", "de"])["screen_ids"]
            for language in ("en", "de")
            for n in (1, 2)
        }
        actual = [
            (r["screen"], r["language"], r["pass"])
            for r in self.content["screenshots"]
            if (r["batch_id"], r["role"]) == (record["request"]["id"], role)
        ]
        require(
            len(actual) == len(expected) and set(actual) == expected,
            "Missing forward/reverse outside-rule measurement scope"
            if outside_gate
            else "Missing forward/reverse capture scope",
        )
        if outside_gate and role != "clean":
            require(
                all(r["qualified"] for r in paired.values()),
                "Pending outside-rule proof cannot qualify",
            )
            self.checkpoint()
            require(
                not self.content["outside_rule_usage"]["engineering_pauses"],
                "Outside-rule engineering pause: >10% of expected batch EN/DE frames; discuss fork-side alternative",
            )
        if role == "calibration":
            self.content["calibration_status"] = "passed"
        elif role == "mutation":
            self.content["dynamic_tests"].append(
                {"id": record["request"]["id"], "recipe_ids": ids, "split": False}
            )
        self.checkpoint()
        return {"passed": True}

    def run(self, *, probe_only=False, measurement_only=False):
        measurement_only = measurement_only or self.content.get(
            "measurement_only", False
        )
        if measurement_only:
            self.content.update(measurement_only=True, measurement_complete=False)
        measurement_captured = False
        primary = None
        restoration_interrupt = None
        self.content["status"] = "running"
        self.checkpoint()
        try:
            require(
                not (measurement_only and probe_only), "Measurement is not probe-only"
            )
            self.probe()
            if measurement_only:
                # Do not even construct production callbacks in this transaction.
                for record, role in (
                    (self.catalog.control, "clean"),
                    (self.catalog.calibration, "calibration"),
                ):
                    require(
                        self.capture(record, role, measurement_only=True)[
                            "measurement_complete"
                        ],
                        "Incomplete measurement capture",
                    )
                actual = [
                    (r["batch_id"], r["role"], r["screen"], r["language"], r["pass"])
                    for r in self.content["screenshots"]
                ]
                expected = expected_capture_keys(self.catalog, measurement_only=True)
                require(
                    len(actual) == len(expected) == 40
                    and set(actual) == expected
                    and self.content["dynamic_tests"] == []
                    and "handoff" not in self.content
                    and not (self.folder / "builder-handoff").exists(),
                    "Incomplete measurement matrix or production evidence",
                )
                measurement_captured = True
            elif not probe_only:
                production = [
                    lambda record=self.catalog.records[batch["id"]]: self.capture(
                        record, "mutation"
                    )
                    for batch in self.plan["batches"]
                ]
                execute_stages(
                    lambda: self.capture(self.catalog.control, "clean"),
                    lambda: self.capture(self.catalog.calibration, "calibration"),
                    production,
                    self.restore,
                )
            if not measurement_only:
                self.content.update(
                    status="probe_verified" if probe_only else "qualified",
                    capture_set_qualified=not probe_only,
                )
        except (
            CaptureError,
            OSError,
            ValueError,
            KeyError,
            subprocess.SubprocessError,
        ) as exc:
            primary = exc
            self.journal["error"] = str(exc)
            self.journal["error_details"] = failure_details(exc)
            self.journal["cleanup_errors"] = getattr(exc, "cleanup_errors", [])
            if self.content["status"] != "awaiting_builder_approval":
                self.content["status"] = "failed"
        except BaseException as exc:
            primary = exc
            self.journal["error"] = str(exc)
            self.journal["error_details"] = failure_details(exc)
            self.journal["cleanup_errors"] = getattr(exc, "cleanup_errors", [])
            self.content.update(status="failed", capture_set_qualified=False)
            raise
        finally:
            try:
                self.restore()
            except BaseException as exc:  # noqa: BLE001 - retain cleanup cancellation on primary
                expected_cleanup = isinstance(
                    exc, (CaptureError, OSError, ValueError, subprocess.SubprocessError)
                )
                self.journal["restoration_error"] = str(exc)
                self.journal["restoration_error_details"] = failure_details(exc)
                if primary is not None:
                    retain_cleanup(primary, exc, "Reference restoration")
                    self.journal["error_details"] = failure_details(primary)
                    self.journal["cleanup_errors"] = getattr(
                        primary, "cleanup_errors", []
                    )
                elif not expected_cleanup:
                    restoration_interrupt = exc
                self.content.update(
                    status="restoration_failed",
                    capture_set_qualified=False,
                )
            if measurement_only:
                self.content["measurement_complete"] = (
                    measurement_captured
                    and self.content["downgrade_verified"] is True
                    and self.content["restoration_verified"] is True
                    and "error" not in self.journal
                    and "restoration_error" not in self.journal
                )
            self.journal["status"] = self.content["status"]
            self.checkpoint()
            # The independent final root binds the manifest, avoiding a hash cycle.
            index = canonical_bytes(
                {
                    "version": self.content["mutation_run_version"] + 1,
                    "files": retained_files(self.folder),
                }
            )
            (self.folder / "evidence-index.json").write_bytes(index)
            self.evidence_sha256 = digest(index)
            if restoration_interrupt is not None:
                raise restoration_interrupt
        return {**self.content, "evidence_sha256": self.evidence_sha256}


def resume_evidence(parent, expected_sha256, catalog, manifest, approved_root):
    require(
        ".." not in Path(parent).parts and ".." not in Path(approved_root).parts,
        "Resume source parent traversal",
    )
    parent = no_symlinks(parent).resolve()
    root = no_symlinks(approved_root).resolve()
    require(
        parent != root and parent.is_relative_to(root),
        "Resume source outside approved root",
    )
    previous_raw = contained(parent, "mutation-manifest.json").read_bytes()
    require(
        digest(previous_raw) == expected_sha256, "Resume parent manifest hash mismatch"
    )
    previous = json_bytes(previous_raw)
    require(
        previous_raw == canonical_bytes(previous)
        and previous["status"] == "awaiting_builder_approval"
        and previous["labels_created"] is False,
        "Resume source is not a pending split run",
    )
    handoff = previous.get("handoff")
    sidecar = json_bytes(contained(parent, "builder-handoff/handoff.json").read_bytes())
    require(
        type(handoff) is dict and canonical_bytes(sidecar) == canonical_bytes(handoff),
        "Resume handoff differs from independently pinned parent handoff",
    )
    raw = contained(parent, "builder-handoff/plan.json").read_bytes()
    requests = contained(parent, "builder-handoff/build-requests.json").read_bytes()
    require(
        handoff["parent_catalog_sha256"] == previous["catalog_sha256"],
        "Resume parent catalog mismatch",
    )
    require(
        digest(raw)
        == handoff["plan_sha256"]
        == catalog.data["inputs"]["plan"]["sha256"],
        "New catalog does not bind exact pending split plan",
    )
    require(
        digest(requests)
        == handoff["requests_sha256"]
        == catalog.data["inputs"]["requests"]["sha256"],
        "New catalog does not bind exact pending requests",
    )
    load_plan(raw, manifest=manifest)
    require(
        catalog.data["builder"]["content_sha256"] == handoff["builder_content_sha256"],
        "Resume builder identity changed",
    )
    parents = {
        event["parent"]["id"]: event["parent"]["recipe_ids"]
        for event in catalog.plan["split_history"]
    }
    nodes = {
        **parents,
        **{batch["id"]: batch["recipe_ids"] for batch in catalog.plan["batches"]},
    }
    for test in previous["dynamic_tests"]:
        require(
            test["id"] in nodes
            and test["recipe_ids"] == nodes[test["id"]]
            and test["split"] is (test["id"] in parents),
            "Resume dynamic evidence differs from split lineage",
        )
    require(
        previous["dynamic_split_rate"] == split_rate(previous["dynamic_tests"]),
        "Resume split rate mismatch",
    )
    return {
        "parent_run_sha256": expected_sha256,
        "dynamic_tests": previous["dynamic_tests"],
    }


def run_config(config, *, probe_only=False, measurement_only=False):
    fields = {
        "catalog",
        "sha256",
        "manifest",
        "recipes",
        "sdk",
        "jdk",
        "output_dir",
        "approved_output_root",
    }
    require(
        fields <= set(config)
        and set(config) <= fields | {"serial", "resume_from", "resume_sha256"},
        "Invalid mutation device configuration",
    )
    require(
        bool(config.get("resume_from")) == bool(config.get("resume_sha256")),
        "Resume requires both parent path and independent parent SHA-256",
    )
    if measurement_only:
        require(
            measurement_only is True
            and not probe_only
            and not config.get("resume_from")
            and config["sha256"]
            == "790b21921ca3d4988b6257a6da235817c8b8407b2f029871c74a05598efaf354",
            "Measurement requires the owner-authorized frozen catalog, without probe/resume",
        )
    catalog = read_catalog(
        Path(config["catalog"]),
        config["sha256"],
        manifest=Path(config["manifest"]),
        recipes=Path(config["recipes"]),
        tools=ApkTools(Path(config["sdk"]), Path(config["jdk"])),
    )
    inputs = Inputs(Path(config["manifest"]), split="dev")
    require(
        catalog.plan["screen_ids"] == [s.id for s in inputs.screens()],
        "Mutation command requires complete dev selection",
    )
    if measurement_only:
        require(
            len(catalog.plan["screen_ids"]) == 5
            and catalog.control["build"]["version_code"] == "1888080431"
            and catalog.calibration["build"]["version_code"] == "1808820362",
            "Measurement requires all five dev screens and the two authorized actual build codes",
        )
    resumed = (
        resume_evidence(
            Path(config["resume_from"]),
            config["resume_sha256"],
            catalog,
            Path(config["manifest"]),
            Path(config["approved_output_root"]),
        )
        if config.get("resume_from")
        else {}
    )
    root = manifest_output_directory(Path(config["approved_output_root"]), False)
    root.mkdir(parents=True, exist_ok=True)
    device = Device(Path(config["sdk"]) / "platform-tools/adb", config.get("serial"))
    if device.serial is None:
        # Discovery only: no connect/root/install until the shared lock is held.
        online = [
            line.split()[0]
            for line in device.run("devices").decode().splitlines()
            if re.fullmatch(r"emulator-\d+\s+device", line.strip())
        ]
        require(len(online) == 1, "Exactly one emulator required for lock discovery")
        device.serial = online[0]
    require(
        re.fullmatch(r"emulator-\d+", device.serial) is not None,
        "Invalid emulator serial for device lock",
    )
    with device_lock(device, REPO_ROOT):
        run = MutationRun(
            catalog,
            inputs,
            Path(config["output_dir"]),
            approved_root=root,
            device=device,
            tools=ApkTools(Path(config["sdk"]), Path(config["jdk"])),
            **({"measurement_only": True} if measurement_only else {}),
        )
        run.content.update(resumed)
        run.checkpoint()
        return run.run(
            probe_only=probe_only,
            **({"measurement_only": True} if measurement_only else {}),
        )


@contextmanager
def device_lock(device, repo_root):
    """Share the existing serial lock between fresh and legacy mutation commands."""
    common = (
        subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo_root,
            capture_output=True,
            timeout=10,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    locks = no_symlinks(Path(common) / "l10n-mutation-locks")
    locks.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(
        no_symlinks(locks / (device.serial + ".lock")),
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(descriptor, "rb+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CaptureError(
                "Another mutation run owns this device boundary"
            ) from exc
        yield


class RunEvidence:
    """Authenticate bytes at the semantic read, not just an earlier disk scan."""

    def __init__(self, folder, files):
        self.folder, self.files = folder, files

    def read(self, folder, relative):
        path = contained(folder, relative)
        require(path.is_relative_to(self.folder), "Evidence read outside run")
        name = str(path.relative_to(self.folder))
        require(
            name in self.files and path.is_file(),
            f"Missing operational receipt: {name}",
        )
        raw = path.read_bytes()
        require(digest(raw) == self.files[name], f"Run evidence hash mismatch: {name}")
        return raw

    def json(self, folder, relative):
        try:
            return json_bytes(self.read(folder, relative))
        except (ValueError, TypeError) as exc:
            raise CaptureError(f"Invalid operational receipt: {relative}") from exc


def replay_reads(evidence, folder, value, inputs, catalog):
    """Replay every attempted read, then derive required coverage from stages."""
    groups = {}
    ordered = {}
    directories = {}
    attempted_receipts = set()
    for relative in sorted(evidence.files):
        if not relative.endswith(
            ("/reads-attempts.json", "/cleanup-pulls-attempts.json")
        ):
            continue
        journal = evidence.json(folder, relative)
        directory = Path(relative).with_name(
            Path(relative).name.removesuffix("-attempts.json")
        )
        require(
            journal.get("version") == 1
            and journal.get("decision") == "D055"
            and journal.get("outcome") == "attempted"
            and type(journal.get("attempts")) is list,
            "D055 missing/invalid read attempt journal",
        )
        for n, attempt in enumerate(journal["attempts"], 1):
            require(
                attempt.get("receipt") == f"{n:06d}.json",
                "D055 read attempt sequence mismatch",
            )
            name = str(directory / attempt["receipt"])
            read = evidence.json(folder, name)
            require(
                attempt
                == {
                    "receipt": attempt["receipt"],
                    **{
                        key: read.get(key)
                        for key in (
                            "root",
                            "path",
                            "purpose",
                            "kind",
                            "command",
                            "limit_s",
                        )
                    },
                },
                "D055 read attempt differs from observed receipt",
            )
            attempted_receipts.add(name)
    for relative in sorted(evidence.files):
        path = Path(relative)
        if path.parent.name not in {"reads", "cleanup-pulls"}:
            continue
        require(
            re.fullmatch(r"[0-9]{6}\.(?:json|bin)", path.name),
            "D055 unsafe telemetry filename",
        )
        if path.suffix == ".bin":
            require(
                str(path.with_suffix(".json")) in evidence.files,
                "D055 raw read has no telemetry",
            )
            continue
        require(
            relative in attempted_receipts,
            "D055 read receipt missing durable attempt binding",
        )
        receipt = evidence.json(folder, relative)
        directories.setdefault(str(path.parent), []).append(int(path.stem))
        require(
            receipt.get("version") == 1
            and receipt.get("decision") == "D055"
            and type(receipt.get("limit_s")) is int
            and receipt["limit_s"] == 300
            and receipt.get("kind") in {"tar", "file"}
            and receipt.get("outcome") in {"complete", "failed"}
            and type(receipt.get("validated")) is bool
            and receipt["validated"] is (receipt["outcome"] == "complete"),
            "D055 read telemetry completion/limit missing or inconsistent",
        )
        start, end = receipt.get("start_monotonic_ns"), receipt.get("end_monotonic_ns")
        count, duration, throughput = (
            receipt.get(k) for k in ("bytes", "duration_s", "bytes_per_second")
        )
        require(
            type(start) is int
            and type(end) is int
            and 0 <= start <= end
            and type(count) is int
            and count >= 0
            and type(duration) in {int, float}
            and math.isfinite(duration)
            and duration == (end - start) / 1_000_000_000
            and type(receipt.get("over_60s")) is bool
            and receipt["over_60s"] is (duration > 60)
            and (
                (duration == 0 and throughput is None)
                or (
                    duration > 0
                    and type(throughput) in {int, float}
                    and math.isfinite(throughput)
                    and throughput >= 0
                    and throughput == count / duration
                )
            ),
            "D055 read telemetry numeric/duration/throughput mismatch",
        )
        require(
            receipt.get("raw") == path.with_suffix(".bin").name,
            "D055 read telemetry raw path mismatch",
        )
        raw = evidence.read(folder / path.parent, receipt["raw"])
        require(
            len(raw) == count and digest(raw) == receipt.get("sha256"),
            "D055 read telemetry byte/hash mismatch",
        )
        root, remote, kind = receipt.get("root"), receipt.get("path"), receipt["kind"]
        if kind == "file":
            expected = receipt.get("expected_bytes")
            require(
                (receipt["outcome"] == "failed" and expected is None and count == 0)
                or (
                    type(expected) is int
                    and expected >= 0
                    and (receipt["outcome"] == "failed" or count == expected)
                ),
                "D055 file read completion length mismatch",
            )
        if kind == "tar":
            from l10n_checker.screen_capture import SAVES_PATH

            require(
                (root in DATA_ROOTS and remote == DATA_ROOTS[root])
                or (root == "SaveFiles" and remote == SAVES_PATH),
                "D055 read root/path mismatch",
            )
            require(
                receipt.get("command")
                == ["exec-out", "tar", "-cf", "-", "-C", remote, "."],
                "D055 read command mismatch",
            )
            if receipt["outcome"] == "complete":
                validate_tar(raw)
                data_inventory({root: raw})
        else:
            if receipt.get("purpose") == "hook-output-cleanup-pull":
                hook_paths(
                    [
                        {
                            "file": remote.removesuffix(".tmp"),
                            "temporary": remote.removesuffix(".tmp") + ".tmp",
                        }
                    ]
                )
                expected_command = [
                    "exec-out",
                    "cat",
                    DATA_ROOTS["private"] + "/" + remote,
                ]
            else:
                require(
                    remote == SETTINGS_PATH and root == "private",
                    "D055 settings telemetry root/path mismatch",
                )
                expected_command = ["exec-out", "cat", SETTINGS_PATH]
            require(
                receipt.get("command") == expected_command,
                "D055 file read command mismatch",
            )
        require(
            (receipt["outcome"] == "failed") is bool(receipt.get("error_details")),
            "D055 failed read error/outcome mismatch",
        )
        groups.setdefault((str(path.parent.parent), receipt.get("purpose")), []).append(
            (receipt, raw)
        )
        ordered.setdefault(str(path.parent), []).append(receipt)
    for numbers in directories.values():
        require(
            numbers == list(range(1, len(numbers) + 1)),
            "D055 missing read telemetry sequence",
        )

    def error_reads(node):
        if isinstance(node, dict):
            if "app_data_read" in node:
                reference = node["app_data_read"]
                matches = [
                    name
                    for name in attempted_receipts
                    if reference.get("receipt", "").endswith("/" + name)
                ]
                require(
                    len(matches) == 1,
                    "D055 failed read reference missing attempted receipt",
                )
                read = evidence.json(folder, matches[0])
                require(
                    all(
                        reference.get(key) == read.get(key)
                        for key in ("root", "path", "purpose")
                    ),
                    "D055 failed read reference scope mismatch",
                )
            for child in node.values():
                error_reads(child)
        elif isinstance(node, list):
            for child in node:
                error_reads(child)

    for relative in evidence.files:
        if relative == "journal.json" or relative.endswith(
            ("/install.json", "/capture/summary.json", "/hook-cleanup.json")
        ):
            error_reads(evidence.json(folder, relative))
    consumed = set()

    def rows_for(relative, purpose):
        consumed.add((relative, purpose))
        return groups.get((relative, purpose), [])

    def package(relative, purpose, inventory):
        rows = rows_for(relative, purpose)
        roots = {name.split(":", 1)[0] for name in inventory}
        require(
            len(rows) == len(roots)
            and [r[0]["root"] for r in rows]
            == [root for root in DATA_ROOTS if root in roots]
            and all(
                r[0]["outcome"] == "complete" and r[0]["kind"] == "tar" for r in rows
            ),
            "D055 missing/incomplete package read telemetry coverage: " + purpose,
        )
        require(
            data_inventory({r[0]["root"]: r[1] for r in rows}) == inventory,
            "D055 read inventory not derived from actual archive bytes: " + purpose,
        )

    # Each retained completed workflow boundary independently requires its reads.
    for relative in sorted(evidence.files):
        if relative.endswith("/inventory.json"):
            parent = str(Path(relative).parent)
            if parent == "private/original":
                package("private", "original-before", evidence.json(folder, relative))
            elif re.fullmatch(r"private/install-[0-9]{3}/(?:before|after)", parent):
                stage = (
                    "install-before" if parent.endswith("/before") else "install-after"
                )
                package(
                    str(Path(parent).parent), stage, evidence.json(folder, relative)
                )
            elif re.fullmatch(r"artifacts/[^/]+/[^/]+/after-capture", parent):
                package(
                    str(Path(parent).parent),
                    "capture-after",
                    evidence.json(folder, relative),
                )
        elif relative == "private/original-readback.json":
            package("private", "original-readback", evidence.json(folder, relative))
        elif re.fullmatch(r"private/install-[0-9]{3}/before-readback.json", relative):
            package(
                str(Path(relative).parent),
                "install-readback",
                evidence.json(folder, relative),
            )
        elif re.fullmatch(r"private/reference-[0-9]{3}-inventory.json", relative):
            purpose = Path(relative).name.removesuffix("-inventory.json")
            package("private", purpose, evidence.json(folder, relative))
        elif re.fullmatch(r"artifacts/[^/]+/[^/]+/before-inventory.json", relative):
            package(
                str(Path(relative).parent),
                "capture-preflight",
                evidence.json(folder, relative),
            )
        elif Path(relative).name in {
            "prepare-start-inventory.json",
            "runtime-start-inventory.json",
            "before-cleanup-inventory.json",
            "post-cleanup-inventory.json",
        }:
            purpose = Path(relative).name.removesuffix("-inventory.json")
            package(
                str(Path(relative).parent), purpose, evidence.json(folder, relative)
            )

    for relative in sorted(evidence.files):
        if not relative.endswith(("/device-plan.json", "/capture/summary.json")):
            continue
        receipt = evidence.json(folder, relative)
        parent = str(Path(relative).parent)
        if receipt.get("backup"):
            for purpose, kind, payload in (
                ("settings-backup", "file", "private/GameSettings.json"),
                ("settings-backup-readback", "file", "private/GameSettings.json"),
                ("saves-backup", "tar", "private/SaveFiles.tar"),
                ("saves-backup-readback", "tar", "private/SaveFiles.tar"),
            ):
                rows = rows_for(parent, purpose)
                require(
                    len(rows) == 1
                    and rows[0][0]["outcome"] == "complete"
                    and rows[0][0]["kind"] == kind,
                    "D055 missing capture backup/readback telemetry: " + purpose,
                )
                retained = evidence.read(folder / parent, payload)
                require(
                    rows[0][1] == retained
                    if kind == "file"
                    else save_inventory(rows[0][1]) == save_inventory(retained),
                    "D055 capture readback telemetry differs from retained backup",
                )
        if relative.endswith("/capture/summary.json"):
            operations = receipt.get("app_data_operations", [])
            for operation in ("replace_settings", "restore_original_settings"):
                verified = [
                    o
                    for o in operations
                    if o["operation"] == operation and o["status"] == "verified"
                ]
                rows = rows_for(parent, operation + "-readback")
                if receipt.get("status") == "complete":
                    require(
                        len(rows) == len(verified),
                        "D055 missing settings observation telemetry",
                    )
                require(
                    sum(r[0]["outcome"] == "complete" for r in rows) >= len(verified),
                    "D055 verified settings read missing telemetry",
                )
                attempted = [o for o in operations if o["operation"] == operation]
                require(len(rows) <= len(attempted), "D055 unbound settings readback")
                for (read, raw), op in zip(rows, attempted):
                    expected = (
                        inputs.settings[op["language"]]
                        if operation == "replace_settings"
                        else evidence.read(folder / parent, "private/GameSettings.json")
                    )
                    require(
                        op.get("sha256") == digest(expected),
                        "D055 settings operation input mismatch",
                    )
                    if read["outcome"] == "complete":
                        require(
                            raw == expected, "D055 settings readback bytes mismatch"
                        )
            rows = rows_for(parent, "capture-settings-readback")
            expected_languages = [
                language
                for n in (1, 2)
                for language in ("en", "de")
                for _ in [*inputs.screens(language, n == 2), None]
            ]
            require(
                len(rows) <= len(expected_languages),
                "D055 extra frame/pass settings telemetry",
            )
            for (read, raw), language in zip(rows, expected_languages):
                if read["outcome"] == "complete":
                    require(
                        raw == inputs.settings[language],
                        "D055 frame/pass settings readback bytes mismatch",
                    )
            verified_hooks = sum(
                o.get("operation") == "hook_output" and o.get("status") == "verified"
                for o in operations
            )
            replacements = sum(
                o.get("operation") == "replace_settings" for o in operations
            )
            require(
                len(rows) >= verified_hooks + max(0, replacements - 1),
                "D055 missing attempted frame/pass settings telemetry",
            )
            final_saves = rows_for(parent, "saves-final-readback")
            require(len(final_saves) <= 1, "D055 extra final SaveFiles telemetry")
            for read, raw in final_saves:
                if read["outcome"] == "complete":
                    require(
                        save_inventory(raw)
                        == save_inventory(
                            evidence.read(folder / parent, "private/SaveFiles.tar")
                        ),
                        "D055 final SaveFiles readback bytes mismatch",
                    )
            if receipt.get("status") == "complete":
                require(
                    len(rows) == len(expected_languages) == len(receipt["records"]) + 4,
                    "D055 missing per-frame/pass settings telemetry",
                )
                require(
                    len(final_saves) == 1,
                    "D055 missing final SaveFiles telemetry",
                )
    for (parent, purpose), rows in groups.items():
        if purpose.startswith("settings-") or purpose in {
            "replace_settings-readback",
            "restore_original_settings-readback",
            "capture-settings-readback",
        }:
            require(
                all(
                    r["kind"] == "file"
                    and r["root"] == "private"
                    and r["path"] == SETTINGS_PATH
                    for r, _ in rows
                ),
                "D055 settings read kind/root/path mismatch",
            )
        elif purpose.startswith("saves-"):
            from l10n_checker.screen_capture import SAVES_PATH

            require(
                all(
                    r["kind"] == "tar"
                    and r["root"] == "SaveFiles"
                    and r["path"] == SAVES_PATH
                    for r, _ in rows
                ),
                "D055 SaveFiles read kind/root/path mismatch",
            )
    # Incomplete boundaries have no final inventory yet, but their observations
    # still need an exact authorized kind/root prefix, never an arbitrary purpose.
    for (parent, purpose), rows in groups.items():
        if (parent, purpose) in consumed:
            continue
        package_purpose = (
            (
                parent == "private"
                and (
                    purpose in {"original-before", "original-readback"}
                    or re.fullmatch(r"reference-[0-9]{3}", purpose)
                )
            )
            or (
                re.fullmatch(r"private/install-[0-9]{3}", parent)
                and purpose in {"install-before", "install-readback", "install-after"}
            )
            or (
                re.fullmatch(r"artifacts/[^/]+/[^/]+", parent)
                and purpose in {"capture-preflight", "capture-after"}
            )
            or (
                re.fullmatch(r"artifacts/[^/]+/[^/]+/(?:prepare|capture)", parent)
                and purpose
                in {"prepare-start", "runtime-start", "before-cleanup", "post-cleanup"}
            )
        )
        if package_purpose:
            if parent == "private":
                if purpose == "original-before":
                    require(
                        "private/initial-apk/installed.apk" in evidence.files
                        and "environment/initial/receipt.json" in evidence.files,
                        "D055 initial read lacks entered probe boundary",
                    )
                elif purpose == "original-readback":
                    require(
                        "private/original/inventory.json" in evidence.files,
                        "D055 readback lacks original backup boundary",
                    )
                else:
                    number = int(purpose.removeprefix("reference-"))
                    name = f"private/install-{number:03d}/install.json"
                    require(
                        name in evidence.files
                        and "private/final-apk/installed.apk" in evidence.files
                        and evidence.json(folder, name).get("build")
                        == inputs.manifest.build.model_dump()
                        and "private/original/inventory.json" in evidence.files,
                        "D055 reference read has no matching entered restoration boundary",
                    )
            elif parent.startswith("private/install-"):
                receipt = evidence.json(folder / parent, "install.json")
                reference_tail = (
                    receipt.get("reference_restoration") == "D-056"
                    and receipt.get("build") == inputs.manifest.build.model_dump()
                    and receipt.get("reference_validated") is True
                )
                if purpose == "install-readback":
                    require(
                        reference_tail
                        or parent + "/before/inventory.json" in evidence.files,
                        "D055 install readback lacks backup boundary",
                    )
                elif purpose == "install-after":
                    require(
                        receipt.get("install_attempted") is True
                        and (
                            reference_tail
                            or (
                                receipt.get("observed_build")
                                == {
                                    key: receipt.get("build", {}).get(key)
                                    for key in ("version_code", "apk_sha256")
                                }
                                | {
                                    "certificate_sha256": catalog.data["signing"][
                                        "reference_certificate_sha256"
                                    ]
                                }
                                and parent + "/before-readback.json" in evidence.files
                            )
                        ),
                        "D055 post-install read lacks entered verified-build boundary",
                    )
            else:
                capture_parent = (
                    str(Path(parent).parent)
                    if Path(parent).name in {"prepare", "capture"}
                    else parent
                )
                require(
                    capture_parent + "/effective-manifest.json" in evidence.files,
                    "D055 capture read lacks entered effective-manifest boundary",
                )
                prerequisites = {
                    "capture-after": parent + "/capture/summary.json",
                    "prepare-start": capture_parent + "/before-inventory.json",
                    "runtime-start": capture_parent + "/prepare/device-plan.json",
                    "before-cleanup": capture_parent + "/capture/write-boundary.json",
                    "post-cleanup": capture_parent + "/capture/hook-cleanup.json",
                }
                require(
                    purpose not in prerequisites
                    or prerequisites[purpose] in evidence.files,
                    "D055 read lacks entered capture/cleanup operation boundary",
                )
            roots = [r["root"] for r, _ in rows]
            require(
                roots
                in (
                    ["private"],
                    ["private", "device_encrypted"],
                    ["private", "external"],
                    list(DATA_ROOTS),
                ),
                "D055 incomplete package read root/order mismatch",
            )
            require(
                all(r["kind"] == "tar" for r, _ in rows),
                "D055 package read kind mismatch",
            )
        elif re.fullmatch(
            r"artifacts/[^/]+/[^/]+/(?:prepare|capture)", parent
        ) and purpose in {
            "settings-backup",
            "settings-backup-readback",
            "saves-backup",
            "saves-backup-readback",
        }:
            require(
                len(rows) == 1
                and rows[0][0]["kind"]
                == ("file" if purpose.startswith("settings") else "tar"),
                "D055 incomplete backup read coverage mismatch",
            )
        elif (
            re.fullmatch(r"artifacts/[^/]+/[^/]+/capture", parent)
            and purpose == "hook-output-cleanup-pull"
        ):
            proof = evidence.json(folder / parent, "hook-cleanup.json")
            referenced = {p.get("host") for p in proof["paths"]}
            require(
                all(
                    "cleanup-pulls/" + r["raw"] in referenced
                    for r, _ in rows
                    if r["outcome"] == "complete"
                ),
                "D055 unbound cleanup read telemetry",
            )
        else:
            require(False, "D055 unconsumed/unapproved read telemetry: " + purpose)
        require(
            value["status"] not in {"qualified", "probe_verified"}
            or purpose == "hook-output-cleanup-pull",
            "D055 unbound successful read boundary",
        )
        require(
            all(r["outcome"] == "complete" for r, _ in rows[:-1]),
            "D055 read continued after failed observation",
        )
    if value["status"] in {"qualified", "probe_verified"}:
        require(
            all(
                r["outcome"] == "complete" for rows in groups.values() for r, _ in rows
            ),
            "D055 failed read cannot qualify",
        )
    replay_read_workflow(evidence, folder, ordered, inputs)
    return groups


def replay_read_workflow(evidence, folder, ordered, inputs):
    """Consume writer order, including interrupted main prefixes and cleanup tails.

    Directories have distinct writers: probe/reference, install, capture's outer
    inventory, preparation, and the capture loop. Numeric timestamps cannot bind
    these roles; use their actual call order and durable entry/operation records.
    Payload, root coverage and cleanup's whole-set unlink barrier remain separate.
    """
    backups = [
        "settings-backup",
        "settings-backup-readback",
        "saves-backup",
        "saves-backup-readback",
    ]

    def blocks(rows):
        result = []
        for row in rows:
            if not result or result[-1][0] != row["purpose"]:
                result.append((row["purpose"], []))
            result[-1][1].append(row)
        return result

    def sequence(rows, purposes, *, tail=False):
        actual = blocks(rows)
        require(
            [p for p, _ in actual] == purposes[: len(actual)],
            "D055 read workflow purpose order mismatch",
        )
        for i, (_, batch) in enumerate(actual):
            require(
                all(r["outcome"] == "complete" for r in batch[:-1]),
                "D055 read workflow continued after failed observation",
            )
            if i < len(actual) - 1 and not tail:
                require(
                    batch[-1]["outcome"] == "complete"
                    and (
                        batch[-1]["kind"] != "tar"
                        or batch[-1]["root"] in {"external", "SaveFiles"}
                    ),
                    "D055 read workflow advanced past an incomplete boundary",
                )

    for directory, rows in ordered.items():
        parent = str(Path(directory).parent)
        if Path(directory).name == "cleanup-pulls":
            proof = evidence.json(folder / parent, "hook-cleanup.json")
            summary = evidence.json(folder / parent, "summary.json")
            mapped = {
                r["readiness"]["dump"]["file"]
                for r in summary.get("records", [])
                if r.get("dump")
            }
            expected = [
                p["path"]
                for p in proof["paths"]
                if "private:" + p["path"] in proof.get("before", {})
                and p["path"] not in mapped
            ]
            require(
                [r["path"] for r in rows] == expected[: len(rows)]
                and all(r["outcome"] == "complete" for r in rows[:-1]),
                "D055 cleanup pull workflow order mismatch",
            )
        elif parent == "private":
            main = [r for r in rows if not r["purpose"].startswith("reference-")]
            references = rows[len(main) :]
            require(
                rows == main + references, "D055 reference read precedes probe reads"
            )
            sequence(main, ["original-before", "original-readback"])
            purposes = sorted(
                {r["purpose"] for r in references},
                key=lambda p: int(p.removeprefix("reference-")),
            )
            sequence(references, purposes)
        elif re.fullmatch(r"private/install-[0-9]{3}", parent):
            receipt = evidence.json(folder / parent, "install.json")
            reference_tail = (
                receipt.get("reference_restoration") == "D-056"
                and receipt.get("build") == inputs.manifest.build.model_dump()
                and receipt.get("reference_validated") is True
            )
            purposes = ["install-before", "install-readback", "install-after"]
            if reference_tail:
                missing = set(purposes) - {r["purpose"] for r in rows}
                errors = {e["stage"] for e in receipt["observation_errors"]}
                require(
                    missing <= errors,
                    "Reference missing read lacks observation failure",
                )
                purposes = [p for p in purposes if p not in missing]
            sequence(rows, purposes, tail=reference_tail)
        elif re.fullmatch(r"artifacts/[^/]+/[^/]+", parent):
            sequence(rows, ["capture-preflight", "capture-after"])
        elif re.fullmatch(r"artifacts/[^/]+/[^/]+/prepare", parent):
            sequence(rows, ["prepare-start", *backups])
        elif re.fullmatch(r"artifacts/[^/]+/[^/]+/capture", parent):
            summary = evidence.json(folder / parent, "summary.json")
            operations = summary.get("app_data_operations", [])
            # Root inventory and backups are mandatory before the write boundary.
            initial = [r for r in rows if r["purpose"] == "runtime-start"]
            require(
                rows[: len(initial)] == initial, "D055 runtime inventory read order"
            )
            prefix = [r for r in rows[len(initial) :] if r["purpose"] in backups]
            require(
                rows[len(initial) : len(initial) + len(prefix)] == prefix,
                "D055 capture backup read order",
            )
            sequence([*initial, *prefix], ["runtime-start", *backups])
            remaining = rows[len(initial) + len(prefix) :]
            if remaining:
                require(
                    initial
                    and initial[-1]["root"] == "external"
                    and all(r["outcome"] == "complete" for r in initial + prefix)
                    and [r["purpose"] for r in prefix] == backups,
                    "D055 capture workflow lacks completed inventory/backups",
                )
            tail_purposes = {
                "restore_original_settings-readback",
                "before-cleanup",
                "post-cleanup",
            }
            boundary = next(
                (i for i, r in enumerate(remaining) if r["purpose"] in tail_purposes),
                len(remaining),
            )
            main, tail = remaining[:boundary], remaining[boundary:]
            replacements = [
                o for o in operations if o["operation"] == "replace_settings"
            ]
            stages = [(n, lang) for n in (1, 2) for lang in ("en", "de")]
            require(
                [(o.get("pass_number"), o.get("language")) for o in replacements]
                == stages[: len(replacements)],
                "D055 settings replacement workflow mismatch",
            )
            records = summary.get("records", [])
            expected_keys = [
                (n, lang, s.id)
                for n, lang in stages
                for s in inputs.screens(lang, n == 2)
            ]
            require(
                [(r.get("pass"), r.get("language"), r.get("screen")) for r in records]
                == expected_keys[: len(records)],
                "D055 frame attempt workflow mismatch",
            )
            by_key = {(r["pass"], r["language"], r["screen"]): r for r in records}
            hooks = {
                (o["pass"], o["language"], o["screen"]): o
                for o in operations
                if o["operation"] == "hook_output"
            }
            expected = []
            all_frames = True
            for n, language in stages[: len(replacements)]:
                expected.append("replace_settings-readback")
                for screen in inputs.screens(language, n == 2):
                    key = (n, language, screen.id)
                    if key not in by_key:
                        all_frames = False
                        break
                    record = by_key[key]
                    if hooks.get(key, {}).get("status") == "verified" or record.get(
                        "pair"
                    ):
                        expected.append("capture-settings-readback")
                if not all_frames:
                    break
                expected.append("capture-settings-readback")  # end of language pass
            if all_frames and len(replacements) == len(stages):
                expected.append("saves-final-readback")
            require(
                [r["purpose"] for r in main] == expected[: len(main)]
                and all(r["outcome"] == "complete" for r in main[:-1]),
                "D055 capture read workflow is not an ordered execution prefix",
            )
            if tail:
                require(
                    any(
                        o["operation"] == "restore_original_settings"
                        for o in operations
                    )
                    and len(
                        [
                            r
                            for r in tail
                            if r["purpose"] == "restore_original_settings-readback"
                        ]
                    )
                    <= 1,
                    "D055 read finalization lacks entered restoration boundary",
                )
                # Restoration may fail before its read; quiescence may fail before
                # before-cleanup. Both still authorize the single post-inventory.
                sequence(
                    tail,
                    [
                        p
                        for p in (
                            "restore_original_settings-readback",
                            "before-cleanup",
                            "post-cleanup",
                        )
                        if any(r["purpose"] == p for r in tail)
                    ],
                    tail=True,
                )
        else:
            require(False, "D055 unapproved read workflow directory")


def replay_backup(evidence, folder, relative, receipt=None):
    root = contained(folder, relative)
    inventory = evidence.json(root, "inventory.json")
    names = {p.stem for p in root.glob("*.tar")}
    require(
        {"private", "external"} <= names <= {"private", "external", "device_encrypted"},
        "Incomplete app-data backup roots",
    )
    archives = {name: evidence.read(root, name + ".tar") for name in names}
    actual = data_inventory(archives)
    require(inventory == actual, "App-data backup inventory replay mismatch")
    if receipt is not None:
        expected = {
            "archives": {
                name: {"path": name + ".tar", "sha256": digest(raw), "bytes": len(raw)}
                for name, raw in archives.items()
            },
            "inventory_sha256": digest(canonical_bytes(actual)),
        }
        require(receipt == expected, "App-data backup receipt mismatch")
    return actual


def replay_environment(evidence, folder, relative, build):
    root = contained(folder, relative)
    receipt = evidence.json(root, "receipt.json")
    command = [str(REPO_ROOT / "scripts/check_env.sh")]
    if build["version_code"] != "1271048":
        command += ["--version-code", build["version_code"]]
    require(
        receipt.get("command") == command
        and receipt.get("build") == build
        and type(receipt.get("exit_code")) is int
        and receipt["exit_code"] == 0
        and "error_details" not in receipt,
        "Unsuccessful environment receipt",
    )
    for stream in ("stdout", "stderr"):
        require(
            digest(evidence.read(root, stream + ".txt"))
            == receipt.get(stream + "_sha256"),
            "environment log hash mismatch",
        )
    return receipt


def replay_installed_apk(evidence, folder, relative, build, certificate):
    # read_catalog authenticated the signed catalog APK. Exact retained bytes
    # establish the same build/signature without running native tools on replay.
    require(
        digest(evidence.read(folder, relative + "/installed.apk"))
        == build["apk_sha256"],
        "Installed/reference APK readback mismatch",
    )
    return {key: build[key] for key in ("version_code", "apk_sha256")} | {
        "certificate_sha256": certificate,
    }


def replay_capture_backup(evidence, root, backup, inputs, inventory):
    require(
        type(backup) is dict
        and backup.get("settings_backup") == "private/GameSettings.json"
        and backup.get("saves_backup") == "private/SaveFiles.tar"
        and backup.get("save_copies_needed") == [],
        "Invalid capture backup receipt",
    )
    settings = evidence.read(root, backup["settings_backup"])
    stat = backup.get("settings_stat", "").split()
    require(
        len(stat) == 4
        and all(s.isdigit() for s in stat)
        and len(settings) == int(stat[3])
        and type(json_bytes(settings)) is dict
        and digest(settings) == backup.get("settings_sha256"),
        "Capture settings backup receipt mismatch",
    )
    expected = {
        "type": "file",
        "uid": int(stat[0]),
        "gid": int(stat[1]),
        "mode": int(stat[2], 8),
        "bytes": len(settings),
        "sha256": digest(settings),
    }
    require(
        inventory.get("private:files/GameSettings.json") == expected,
        "Capture settings inventory mismatch",
    )
    raw = evidence.read(root, backup["saves_backup"])
    data_inventory({"external": raw})  # Validate tar paths/types, never extract.
    saves = save_inventory(raw)
    files = {
        "external:files/SaveFiles/" + str(Path(name)): checksum
        for name, checksum in saves.items()
    }
    require(
        saves == backup.get("saves")
        and all(
            saves.get("./" + name) == digest(raw)
            for name, raw in inputs.fixtures.items()
        )
        and files
        == {
            name: entry["sha256"]
            for name, entry in inventory.items()
            if name.startswith("external:files/SaveFiles/") and entry["type"] == "file"
        },
        "Capture saves backup/inventory mismatch",
    )
    return digest(settings)


def replay_preservation(recorded, before, after, allowed_new=()):
    """Bind the complete ledger to authenticated inventories and the exact policy."""
    expected = preservation_report(before, after, allowed_new)
    require(
        canonical_bytes(recorded) == canonical_bytes(expected),
        "Preservation policy/ledger receipt mismatch",
    )
    require(not expected["unexpected_changes"], "Unexpected app-data inventory change")
    return expected


def replay_cleanup(evidence, root, prepared, summary, outputs, *, partial=False):
    """Exact deletion authority from inventories and authenticated host bytes."""
    capture_root = root / "capture"
    proof = evidence.json(capture_root, "hook-cleanup.json")
    starting = evidence.json(capture_root, "runtime-start-inventory.json")
    plan_start = evidence.json(root / "prepare", "prepare-start-inventory.json")
    require(
        prepared.get("starting_inventory") == plan_start
        and summary.get("starting_inventory") == starting
        and proof.get("starting") == starting,
        "D055 cleanup starting inventory mismatch",
    )
    replay_preservation(preservation_report(plan_start, starting), plan_start, starting)
    directory = prepared.get("directory_identity")
    require(
        type(directory) is list
        and len(directory) == 3
        and summary.get("directory_identity") == directory
        and proof.get("directory_identity") == directory,
        "D055 cleanup directory identity mismatch",
    )
    require(
        all(
            starting.get("private:" + p, {}).get("type") == "directory"
            for p in (".", "files", "files/l10n-hook")
        ),
        "D055 cleanup needs pre-existing hook directory",
    )
    for path, identity in zip(
        (".", "files", "files/l10n-hook"), directory, strict=True
    ):
        parts = identity.split()
        require(
            len(parts) == 7
            and all(re.fullmatch(r"[0-9]+", parts[k]) for k in (0, 1, 2, 4, 5, 6))
            and re.fullmatch(r"[0-9a-fA-F]+", parts[3])
            and int(parts[2]) >= 1
            and int(parts[3], 16) & 0o170000 == 0o040000
            and [int(parts[4]), int(parts[5]), int(parts[3], 16) & 0o7777]
            == [starting["private:" + path][k] for k in ("uid", "gid", "mode")],
            "D055 cleanup directory identity/type/metadata invalid",
        )
    require(
        canonical_bytes(proof.get("policy")) == canonical_bytes(cleanup_policy())
        and summary.get("hook_cleanup") == proof
        and proof.get("status")
        in ({"verified", "failed"} if partial else {"verified"}),
        "D055 cleanup proof missing/altered/failed",
    )
    paths = hook_paths(outputs)
    entries = proof.get("paths")
    require(
        type(entries) is list
        and [p.get("path") for p in entries] == paths
        and not {"private:" + p for p in paths} & set(starting),
        "D055 cleanup authority is not exact plan-new paths",
    )
    before = proof.get("before")
    if before is None:
        require(
            partial
            and proof["status"] == "failed"
            and proof.get("error_details")
            and all(
                set(p) == {"path", "status"} and p["status"] == "unavailable"
                for p in entries
            )
            and proof.get("quiescence")
            in (None, {"force_stopped": True, "pid": "", "package_stopped": True})
            and str(
                (capture_root / "before-cleanup-inventory.json").relative_to(
                    evidence.folder
                )
            )
            not in evidence.files,
            "D055 cleanup incomplete predelete proof",
        )
        if proof.get("after") is not None:
            after = evidence.json(capture_root, "post-cleanup-inventory.json")
            require(
                proof["after"] == after
                and proof.get("preservation") == preservation_report(starting, after),
                "D055 failed prebarrier post inventory/ledger mismatch",
            )
        else:
            require(
                proof["error_details"].get("cleanup_errors"),
                "D055 failed prebarrier missing post-inventory failure evidence",
            )
        return None
    require(
        proof.get("quiescence")
        == {"force_stopped": True, "pid": "", "package_stopped": True},
        "D055 cleanup missing writer quiescence",
    )
    require(
        before == evidence.json(capture_root, "before-cleanup-inventory.json"),
        "D055 cleanup before inventory mismatch",
    )
    mapped = {
        r["readiness"]["dump"]["file"]: r["dump"]
        for r in summary.get("records", [])
        if r.get("dump")
    }
    deleted = set()
    unlink_started = any(
        p.get("status") in {"deleted", "attempted", "failed"} or "command" in p
        for p in entries
    )
    stopped = False
    require(
        proof["status"] != "failed" or proof.get("error_details"),
        "D055 failed cleanup lacks primary failure",
    )
    for entry in entries:
        path, status = entry["path"], entry.get("status")
        value = before.get("private:" + path)
        require(
            ("command" in entry) is (status in {"deleted", "attempted", "failed"})
            and ("error_details" in entry) is (status == "failed"),
            "D055 cleanup phase command/error state regression",
        )
        if status in {"absent", "unavailable"}:
            require(
                set(entry) == {"path", "status"},
                "D055 cleanup unavailable/absent state retained attempt/proof fields",
            )
        if value is None:
            require(
                status == "absent"
                or (partial and not unlink_started and status == "unavailable"),
                "D055 cleanup forged absence/deletion",
            )
            continue
        require(
            value.get("type") == "file"
            and status
            in (
                {"deleted", "attempted", "failed", "verified", "unavailable"}
                if partial
                else {"deleted"}
            ),
            "D055 cleanup present file not verified/deleted",
        )
        if status == "unavailable":
            require(
                partial and proof["status"] == "failed" and not unlink_started,
                "D055 cleanup missing host proof",
            )
            continue
        if unlink_started:
            require(
                not stopped or status == "verified",
                "D055 cleanup continued after first failure/unattempted path",
            )
            if status != "deleted":
                stopped = True
        identity = entry.get("identity")
        require(
            type(identity) is list and len(identity) == 4 and identity[:3] == directory,
            "D055 cleanup identity/ancestor mismatch",
        )
        parts = identity[-1].split()
        require(
            len(parts) == 7
            and parts[2] == "1"
            and int(parts[3], 16) & 0o170000 == 0o100000
            and [int(parts[k]) for k in (4, 5, 6)]
            == [value[k] for k in ("uid", "gid", "bytes")]
            and int(parts[3], 16) & 0o7777 == value["mode"],
            "D055 cleanup unsafe leaf identity/type/link/metadata",
        )
        host = entry.get("host")
        require(
            type(host) is str
            and (
                host == mapped.get(path)
                or re.fullmatch(r"cleanup-pulls/[0-9]{6}\.bin", host)
            ),
            "D055 cleanup host proof path is not actual retained output",
        )
        raw = evidence.read(capture_root, host)
        require(
            type(entry.get("bytes")) is int
            and len(raw) == entry["bytes"] == value["bytes"]
            and digest(raw) == entry.get("sha256") == value["sha256"],
            "D055 cleanup host hash/bytes proof mismatch",
        )
        if status in {"deleted", "attempted", "failed"}:
            require(
                entry.get("command") == unlink_command(path, identity, digest(raw)),
                "D055 cleanup unguarded/widened unlink command",
            )
        if status == "failed":
            require(
                partial and proof["status"] == "failed" and entry.get("error_details"),
                "D055 failed path lacks failure evidence",
            )
        if status == "deleted":
            deleted.add("private:" + path)
    if proof.get("after") is not None:
        after = evidence.json(capture_root, "post-cleanup-inventory.json")
        require(proof["after"] == after, "D055 cleanup post inventory mismatch")
        # A failed guarded command may already have unlinked its one exact path.
        # Derive its observed effect without claiming a successful deletion.
        if partial:
            deleted.update(
                "private:" + entry["path"]
                for entry in proof["paths"]
                if entry["status"] in {"attempted", "failed"}
                and "private:" + entry["path"] not in after
            )
        expected = {k: v for k, v in before.items() if k not in deleted}
        replay_preservation(preservation_report(expected, after), expected, after)
        require(
            proof.get("preservation") == preservation_report(starting, after),
            "D055 cleanup preservation ledger mismatch",
        )
        if proof["status"] == "verified":
            replay_preservation(proof["preservation"], starting, after)
        return after
    require(
        partial and proof["status"] == "failed" and proof.get("error_details"),
        "D055 cleanup missing fresh post inventory",
    )
    return None


def replay_partial_d055(evidence, folder, catalog, inputs):
    """Validate every available D055 capture attempt without requiring later stages."""
    artifacts = {
        ("clean", catalog.control["request"]["id"]): catalog.control,
        ("calibration", catalog.calibration["request"]["id"]): catalog.calibration,
    }
    artifacts.update(
        {
            ("mutation", b["id"]): catalog.records[b["id"]]
            for b in catalog.plan["batches"]
        }
    )
    seen = set()
    for relative in sorted(evidence.files):
        match = re.fullmatch(
            r"artifacts/([^/]+)/([^/]+)/prepare/device-plan.json", relative
        )
        if not match:
            continue
        key = match.groups()
        require(key in artifacts, "D055 unapproved capture attempt")
        root = folder / "artifacts" / key[0] / key[1]
        effective = inputs.with_build(artifacts[key]["build"])
        prepared = evidence.json(root / "prepare", "device-plan.json")
        outputs = planned_hook_outputs(
            effective, ["en", "de"], prepared.get("request_namespace", "")
        )
        require(
            prepared.get("planned_hook_output_operations") == outputs
            and prepared.get("manifest_sha256") == effective.sha256
            and prepared.get("selection") == effective.capture_selection(["en", "de"])
            and prepared.get("planned_hook_directory_operation")
            == HOOK_DIRECTORY_OPERATION
            and canonical_bytes(prepared.get("cleanup_policy"))
            == canonical_bytes(cleanup_policy()),
            "D055 attempted preparation authority mismatch",
        )
        start = evidence.json(root / "prepare", "prepare-start-inventory.json")
        require(
            prepared.get("starting_inventory") == start
            and not {"private:" + p for p in hook_paths(outputs)} & set(start),
            "D055 attempted preparation classified existing output as new",
        )
        before_name = str((root / "before-inventory.json").relative_to(folder))
        if before_name in evidence.files:
            before = evidence.json(root, "before-inventory.json")
            require(
                not preservation_report(before, start)["unexpected_changes"],
                "D055 attempted preparation rebaselined inventory",
            )
        summary_name = str((root / "capture/summary.json").relative_to(folder))
        if summary_name not in evidence.files:
            continue
        summary = evidence.json(root / "capture", "summary.json")
        require(
            summary.get("manifest_sha256") == effective.sha256
            and summary.get("selection") == effective.capture_selection(["en", "de"]),
            "D055 attempted capture scope mismatch",
        )
        cleanup_name = str((root / "capture/hook-cleanup.json").relative_to(folder))
        boundary_name = str((root / "capture/write-boundary.json").relative_to(folder))
        writes_possible = (
            boundary_name in evidence.files
            or bool(summary.get("records"))
            or any(
                name.startswith(str((root / "capture").relative_to(folder)) + "/pass-")
                for name in evidence.files
            )
            or any(
                evidence.json(folder, name).get("purpose")
                in {
                    "replace_settings-readback",
                    "capture-settings-readback",
                    "restore_original_settings-readback",
                }
                for name in evidence.files
                if name.startswith(
                    str((root / "capture/reads").relative_to(folder)) + "/"
                )
                and name.endswith(".json")
            )
            or (
                summary.get("backup")
                and summary.get("device_plan_sha256")
                == digest(evidence.read(root / "prepare", "device-plan.json"))
            )
        )
        if writes_possible:
            require(
                evidence.json(root / "capture", "write-boundary.json")
                == {
                    "manifest_sha256": effective.sha256,
                    "device_plan_sha256": digest(
                        evidence.read(root / "prepare", "device-plan.json")
                    ),
                    "cleanup_required": True,
                },
                "D055 missing/altered capture write boundary",
            )
        if (
            writes_possible
            or summary.get("app_data_operations")
            or summary.get("hook_cleanup")
            or cleanup_name in evidence.files
        ):
            require(
                cleanup_name in evidence.files,
                "D055 missing cleanup for attempted capture",
            )
            replay_cleanup(evidence, root, prepared, summary, outputs, partial=True)
            seen.add(cleanup_name)
    require(
        {name for name in evidence.files if name.endswith("/hook-cleanup.json")}
        == seen,
        "D055 unbound cleanup receipt outside an exact prepared capture",
    )


def replay_capture(
    evidence,
    folder,
    artifact,
    role,
    inputs,
    screenshots,
    before,
    *,
    measurement_only=False,
    partial_mapping=False,
    legacy_measurement=False,
):
    identity = artifact["request"]["id"]
    root = capture_directory(folder, identity, role)
    effective = inputs.with_build(artifact["build"])
    require(
        evidence.read(root, "effective-manifest.json") == effective.manifest_bytes,
        "Effective capture manifest receipt mismatch",
    )
    actual_before = evidence.json(root, "before-inventory.json")
    preflight = replay_preservation(
        evidence.json(root, "preflight-preservation.json"), before, actual_before
    )
    before = actual_before
    prepared_raw = evidence.read(root, "prepare/device-plan.json")
    prepared = json_bytes(prepared_raw)
    summary = evidence.json(root, "capture/summary.json")
    require(
        summary.get("status")
        in ({"complete", "failed"} if measurement_only else {"complete"})
        and summary.get("settings_restored") is True
        and summary.get("saves_unchanged") is True
        and not summary.get("fatal_error")
        and summary.get("schema_version") == 1
        and summary.get("languages") == ["en", "de"]
        and summary.get("passes") == ["forward", "reverse"]
        and summary.get("live_provider_requests") == 0
        and summary.get("api_spend_usd") == 0
        and summary.get("device_plan_sha256") == digest(prepared_raw)
        and prepared.get("mode") == "prepare_only"
        and prepared.get("app_data_writes") == 0
        and re.fullmatch(r"emulator-\d+", prepared.get("serial", "")),
        "Unsuccessful capture/preparation summary receipt",
    )
    settings_sha = replay_capture_backup(
        evidence, root / "prepare", prepared.get("backup"), effective, before
    )
    require(
        settings_sha
        == replay_capture_backup(
            evidence, root / "capture", summary.get("backup"), effective, before
        ),
        "Capture settings changed since preparation",
    )
    observed = {
        "version_code": artifact["build"]["version_code"],
        "apk_sha256": artifact["build"]["apk_sha256"],
        "density_dpi": effective.manifest.density_dpi,
    }
    for receipt in (prepared, summary):
        require(
            receipt.get("manifest_sha256") == effective.sha256
            and receipt.get("selection") == effective.capture_selection(["en", "de"])
            and receipt.get("observed_build") == observed
            and receipt.get("planned_app_data_operations")
            == planned_operations(effective, ["en", "de"], settings_sha),
            "Capture plan/build/settings receipt mismatch",
        )
    outputs = planned_hook_outputs(
        effective, ["en", "de"], prepared.get("request_namespace", "")
    )
    require(
        prepared.get("planned_hook_output_operations") == outputs
        and prepared.get("planned_hook_directory_operation")
        == HOOK_DIRECTORY_OPERATION,
        "Capture prepared hook operations receipt mismatch",
    )
    records = summary.get("records")
    expected_keys = [(o["screen"], o["language"], o["pass"]) for o in outputs]
    require(
        type(records) is list
        and [(r["screen"], r["language"], r["pass"]) for r in records] == expected_keys,
        "Capture summary receipt records missing/duplicate/out of order",
    )
    if measurement_only:
        require(
            not summary.get("fatal_error_details")
            and not summary.get("cleanup_errors")
            and all(not r.get("error_details") for r in cast(list[dict], records)),
            "Measurement operational/cleanup failure is not repeat evidence",
        )
    width, height = effective.manifest.resolution
    comparisons = [
        {
            "screen": screen.id,
            "language": language,
            "status": "identical",
            "dump_status": "identical",
            "total_pixels": width * height,
            "different_pixels": 0,
            "different_share": 0,
            "bounding_box": None,
            "bounding_box_convention": "[left, top, right-exclusive, bottom-exclusive] or null",
        }
        for language in ("en", "de")
        for screen in effective.screens(language)
    ]
    if measurement_only:
        for comparison in comparisons:
            pair_records = [
                r
                for r in cast(list[dict], records)
                if (r["screen"], r["language"])
                == (comparison["screen"], comparison["language"])
            ]
            pngs = [evidence.read(root / "capture", r["png"]) for r in pair_records]
            pixels = compare_rgba(pngs[0], pngs[1], [])["total"]
            count = pixels["different_pixels"]
            comparison.update(
                status="different" if count else "identical",
                different_pixels=count,
                different_share=count / (width * height),
                bounding_box=pixels["bounding_box"],
            )
            dumps = [evidence.read(root / "capture", r["dump"]) for r in pair_records]
            comparison["dump_status"] = (
                "identical" if dumps[0] == dumps[1] else "different"
            )
        repeatable = all(
            c["status"] == c["dump_status"] == "identical" for c in comparisons
        )
        require(
            summary["status"] == ("complete" if repeatable else "failed"),
            "Measurement repeat-only summary status mismatch",
        )
    require(
        summary.get("comparisons") == comparisons,
        "Capture repeatability comparisons receipt mismatch",
    )
    mapped = {
        (r["screen"], r["language"], r["pass"]): r
        for r in screenshots
        if (r["batch_id"], r["role"]) == (identity, role)
    }
    operations = []
    for n in (1, 2):
        for language in ("en", "de"):
            operations.append(
                {
                    "operation": "replace_settings",
                    "path": SETTINGS_PATH,
                    "sha256": digest(effective.settings[language]),
                    "status": "verified",
                    "language": language,
                    "pass_number": n,
                }
            )
            for record, output in zip(records, outputs, strict=True):
                if (record["pass"], record["language"]) != (n, language):
                    continue
                key = (record["screen"], record["language"], record["pass"])
                pair_path = contained(root / "capture", record["pair"])
                pair = evidence.json(pair_path.parent, pair_path.name)
                require(
                    key in mapped or partial_mapping,
                    "Capture receipt has no runtime screenshot",
                )
                if key in mapped:
                    shot = mapped[key]
                else:
                    verified_pair(
                        effective, root / "capture", record, evidence=evidence
                    )
                    shot = {**pair, "pair": str(pair_path.relative_to(folder))}
                require(
                    str(pair_path.relative_to(folder)) == shot["pair"]
                    and record.get("status") == "captured"
                    and record.get("request") == output["request"]
                    and record.get("state") == effective.states[key[:2]]
                    and all(
                        record.get(name) == shot[name]
                        for name in ("png_sha256", "rgba_sha256", "dump_sha256")
                    )
                    and contained(root / "capture", record["png"])
                    == contained(pair_path.parent, pair["png"])
                    and contained(root / "capture", record["dump"])
                    == contained(pair_path.parent, pair["dump"]),
                    "Capture summary pair mapping receipt mismatch",
                )
                if not any(
                    op["operation"] == HOOK_DIRECTORY_OPERATION["operation"]
                    for op in operations
                ):
                    operations.append(
                        {**HOOK_DIRECTORY_OPERATION, "status": "verified_present"}
                    )
                operations.append(
                    {
                        "operation": "hook_output",
                        **output,
                        "status": "verified",
                        "sha256": shot["dump_sha256"],
                    }
                )
    operations.append(
        {
            "operation": "restore_original_settings",
            "path": operations[0]["path"],
            "sha256": settings_sha,
            "status": "verified",
        }
    )
    require(
        summary.get("app_data_operations") == operations,
        "Capture settings/hook operations receipt mismatch",
    )
    allowed = {"private:" + o[name] for o in outputs for name in ("file", "temporary")}
    if legacy_measurement:
        require(measurement_only, "Legacy capture allowance is measurement-only")
        allowed.add("private:files/l10n-hook")
    require(
        not (allowed - {"private:files/l10n-hook"}) & set(before),
        "Capture hook outputs already existed",
    )
    after = replay_backup(evidence, root, "after-capture")
    if not legacy_measurement:
        cleaned = replay_cleanup(evidence, root, prepared, summary, outputs)
        require(
            not preservation_report(cleaned, after)["unexpected_changes"],
            "D055 post-cleanup continuity changed before capture boundary",
        )
        require(
            not preservation_report(before, prepared["starting_inventory"])[
                "unexpected_changes"
            ],
            "D055 capture preparation rebaselined app data",
        )
    allowance = allowed if legacy_measurement else set()
    check = {
        "batch_id": identity,
        "role": role,
        "preflight_preservation": preflight,
        "changes": inventory_changes(before, after, allowance),
        "preservation": preservation_report(before, after, allowance),
    }
    require(
        not check["preservation"]["unexpected_changes"],
        "Capture app-data inventory preservation failed",
    )
    return after, allowance, check


def replay_reference_data(evidence, folder, recorded, original, previous, allowed, n):
    relative = f"private/reference-{n:03d}-inventory.json"
    current = evidence.json(folder, relative)
    expected = {
        "inventory": relative,
        "allowed_outputs": sorted(allowed),
        "prior_preservation": preservation_report(previous, current),
        "preservation": preservation_report(original, current, allowed),
    }
    require(
        canonical_bytes(recorded) == canonical_bytes(expected),
        "Reference preservation ledger receipt mismatch",
    )
    require(
        not expected["prior_preservation"]["unexpected_changes"]
        and not expected["preservation"]["unexpected_changes"],
        "Final reference app-data preservation failed",
    )
    return current


def replay_reference_install(evidence, folder, relative, receipt, build, certificate):
    """Identity success is authenticated separately from preservation success."""
    expected = {key: build[key] for key in ("version_code", "apk_sha256")} | {
        "certificate_sha256": certificate,
    }
    require(
        receipt.get("reference_restoration") == "D-056"
        and type(receipt.get("reference_validated")) is bool
        and type(receipt.get("identity_verified")) is bool
        and type(receipt.get("observation_errors")) is list,
        "Missing/altered reference restoration receipt",
    )
    if receipt["reference_validated"]:
        require(
            receipt.get("reference_identity") == expected,
            "Reference identity receipt mismatch",
        )
    if receipt.get("install_attempted"):
        require(receipt["reference_validated"], "Unvalidated reference install attempt")
    if receipt["identity_verified"]:
        require(
            receipt.get("install_attempted") is True
            and receipt.get("observed_build")
            == replay_installed_apk(
                evidence, folder, relative + "/after-apk", build, certificate
            ),
            "Reference identity verification receipt mismatch",
        )
    elif receipt.get("install_attempted"):
        require(
            any(
                error.get("stage") == "installed-identity"
                and error.get("error_details")
                for error in receipt["observation_errors"]
            ),
            "Unverified reference identity lacks failed observation",
        )
    if receipt.get("status") == "verified":
        require(
            receipt["reference_validated"]
            and receipt["identity_verified"]
            and receipt["observation_errors"] == [],
            "Successful reference has failed observations",
        )
    else:
        require(receipt.get("error_details"), "Failed reference lacks error receipt")


def replay_available_operations(evidence, folder, catalog, inputs, value):
    """Replay retained completed transactions and the honest failed tail."""
    journal = evidence.json(folder, "journal.json")
    require(
        journal.get("status") == value["status"]
        and journal.get("live_provider_requests") == 0
        and journal.get("api_spend_usd") == 0
        and journal.get("preservation_policy") == preservation_policy(),
        "Failed operational receipt journal mismatch",
    )
    reference = {
        "build": inputs.manifest.build.model_dump(),
        "apk": catalog.data["reference"]["apk"],
    }
    certificate = catalog.data["signing"]["reference_certificate_sha256"]

    def available(name):
        return name in evidence.files

    def ledger(recorded, before, after, *, successful=False):
        expected = preservation_report(before, after)
        require(
            canonical_bytes(recorded) == canonical_bytes(expected),
            "Preservation policy/ledger receipt mismatch",
        )
        require(
            not successful or not expected["unexpected_changes"],
            "Successful transaction has unexpected app-data change",
        )
        return expected

    def environment(relative, build, *, successful=False):
        receipt = evidence.json(folder, relative + "/receipt.json")
        command = [str(REPO_ROOT / "scripts/check_env.sh")]
        if build["version_code"] != "1271048":
            command += ["--version-code", build["version_code"]]
        require(
            receipt.get("command") == command and receipt.get("build") == build,
            "Install environment authority mismatch",
        )
        for stream in ("stdout", "stderr"):
            require(
                digest(evidence.read(folder, relative + "/" + stream + ".txt"))
                == receipt.get(stream + "_sha256"),
                "Install environment log mismatch",
            )
        if successful:
            replay_environment(evidence, folder, relative, build)
        else:
            require(
                type(receipt.get("exit_code")) is int or receipt.get("error_details"),
                "Failed environment observation lacks outcome",
            )
        return receipt

    # Only reference restoration may enter after failed initial diagnostics.
    # Original data reads and ordinary installs still require both initial gates.
    progressed = any(
        name.startswith(("private/reads/", "private/original/", "artifacts/"))
        or name in {"private/reads-attempts.json", "private/original-readback.json"}
        or (
            re.fullmatch(r"private/install-[0-9]{3}/install.json", name)
            and evidence.json(folder, name).get("build") != reference["build"]
        )
        for name in evidence.files
    )
    if progressed or available("environment/initial/receipt.json"):
        require(
            available("private/initial-apk/installed.apk"),
            "Initial environment/data observation lacks initial APK authority",
        )
    if progressed:
        require(
            available("environment/initial/receipt.json"),
            "Initial environment prerequisite missing before app-data/transactions",
        )
    if available("private/initial-apk/installed.apk"):
        if progressed:
            replay_installed_apk(
                evidence, folder, "private/initial-apk", reference["build"], certificate
            )
        else:
            # Failed initial diagnostics cannot prohibit the reference-only tail.
            evidence.read(folder, "private/initial-apk/installed.apk")
    if available("environment/initial/receipt.json"):
        environment("environment/initial", reference["build"], successful=progressed)
    original = previous_inventory = None
    if available("private/original/inventory.json"):
        original = previous_inventory = replay_backup(
            evidence, folder, "private/original", journal.get("original_backup")
        )
    if available("private/original-readback.json"):
        require(original is not None, "Original readback has no backup")
        current = evidence.json(folder, "private/original-readback.json")
        ledger(journal.get("original_readback_preservation"), original, current)
        previous_inventory = current
    captures = [
        (catalog.control, "clean"),
        (catalog.calibration, "calibration"),
        *[(catalog.records[b["id"]], "mutation") for b in catalog.plan["batches"]],
    ]
    main = [(catalog.control, None), (reference, None), *captures]
    installs = sorted(
        name
        for name in evidence.files
        if re.fullmatch(r"private/install-[0-9]{3}/install.json", name)
    )
    require(
        installs
        == [
            f"private/install-{n:03d}/install.json" for n in range(1, len(installs) + 1)
        ],
        "Missing attempted install receipt sequence",
    )
    previous_builds = [reference["build"]]
    completed, checks, reference_checks = [], [], []
    halted = final_reference = False
    last_reference = None
    last_install = {}
    for n, name in enumerate(installs, 1):
        receipt = evidence.json(folder, name)
        last_install = receipt
        relative = str(Path(name).parent)
        build = receipt.get("build")
        require(not final_reference, "Install continued after final reference attempt")
        is_reference = build == reference["build"]
        if is_reference and (n != 2 or halted):
            artifact, role = reference, None
            final_reference = True
            require(
                journal.get("error_details"),
                "Early/final reference lacks stopped stage",
            )
        else:
            require(n <= len(main), "Extra install beyond authorized stage prefix")
            artifact, role = main[n - 1]
            require(
                not halted or build == reference["build"],
                "Install continued after failed stage",
            )
        require(
            build == artifact["build"]
            and receipt.get("command")
            == [
                "install",
                "-r",
                "-d",
                str(catalog.path.parent / artifact["apk"]["path"]),
            ]
            and receipt.get("preservation_policy") == preservation_policy(),
            "Failed/partial install authority or preservation policy mismatch",
        )
        verified = receipt.get("status") == "verified"
        if is_reference:
            replay_reference_install(
                evidence, folder, relative, receipt, build, certificate
            )
        require(
            receipt.get("status")
            in {"verified", "failed", "preparing", "install_attempted"},
            "Unknown partial install state",
        )
        if verified:
            require(
                receipt.get("install_attempted") is True
                and receipt.get("app_data_preserved") is True
                and not receipt.get("error_details")
                and not receipt.get("error")
                and receipt.get("stdout", "").strip().splitlines()[-1:] == ["Success"],
                "Unsuccessful completed install receipt",
            )
            completed.append(
                {
                    "kind": "install",
                    "receipt": name,
                    "sha256": digest(canonical_bytes(receipt)),
                }
            )
        else:
            require(
                receipt.get("app_data_preserved") is False
                and (
                    receipt.get("error_details")
                    or journal.get("error_details")
                    or journal.get("restoration_error_details")
                ),
                "Partial install lacks failure evidence",
            )
            halted = True
        if verified or available(relative + "/before-apk/installed.apk"):
            raw = evidence.read(folder, relative + "/before-apk/installed.apk")
            candidates = [b for b in previous_builds if digest(raw) == b["apk_sha256"]]
            previous_error = (
                is_reference
                and not verified
                and any(
                    error.get("stage") == "previous-identity"
                    for error in receipt.get("observation_errors", [])
                )
            )
            if previous_error and "previous_build" not in receipt:
                pass  # Retained bytes are an observation, not a verified previous identity.
            elif is_reference and not candidates:
                require(
                    receipt.get("previous_build", {}).get("apk_sha256") == digest(raw),
                    "Reference previous diagnostic receipt mismatch",
                )
            else:
                require(
                    len(candidates) == 1, "Install previous APK continuity mismatch"
                )
                require(
                    receipt.get("previous_build")
                    == replay_installed_apk(
                        evidence,
                        folder,
                        relative + "/before-apk",
                        candidates[0],
                        certificate,
                    ),
                    "Install previous identity receipt mismatch",
                )
        before = readback = after = None
        if verified or available(relative + "/before/inventory.json"):
            require(
                (is_reference or previous_inventory is not None)
                and "backup" in receipt,
                "Install has no original/input backup",
            )
            before = replay_backup(
                evidence, folder, relative + "/before", receipt["backup"]
            )
            if previous_inventory is not None:
                ledger(
                    receipt.get("input_preservation"),
                    previous_inventory,
                    before,
                    successful=verified,
                )
            else:
                require(
                    "input_preservation" not in receipt,
                    "Reference invented input inventory",
                )
        if verified or available(relative + "/before-readback.json"):
            require(
                is_reference or before is not None,
                "Install readback lacks before inventory",
            )
            readback = evidence.json(folder, relative + "/before-readback.json")
            if before is not None:
                ledger(
                    receipt.get("backup_readback_preservation"),
                    before,
                    readback,
                    successful=verified,
                )
        if verified or available(relative + "/after-apk/installed.apk"):
            if is_reference and receipt.get("identity_verified") is False:
                # A failed reinstall may retain the previous APK, not the reference.
                raw = evidence.read(folder, relative + "/after-apk/installed.apk")
                if "observed_build" in receipt:
                    require(
                        receipt["observed_build"].get("apk_sha256") == digest(raw),
                        "Failed reference observed APK digest mismatch",
                    )
            else:
                require(
                    receipt.get("observed_build")
                    == replay_installed_apk(
                        evidence, folder, relative + "/after-apk", build, certificate
                    ),
                    "Install observed identity receipt mismatch",
                )
        if verified or available(f"environment/{n:03d}/receipt.json"):
            observed = environment(f"environment/{n:03d}", build, successful=verified)
            require(
                not verified or receipt.get("environment") == observed,
                "Install environment receipt mismatch",
            )
        if verified or available(relative + "/after/inventory.json"):
            require(
                (is_reference or (before is not None and readback is not None))
                and "post_install" in receipt,
                "Install after inventory lacks backup/readback",
            )
            after = replay_backup(
                evidence, folder, relative + "/after", receipt["post_install"]
            )
            if before is not None:
                require(
                    receipt.get("data_changes") == inventory_changes(before, after),
                    "Install data-change ledger mismatch",
                )
                ledger(receipt.get("preservation"), before, after, successful=verified)
            if readback is not None:
                ledger(
                    receipt.get("post_readback_preservation"),
                    readback,
                    after,
                    successful=verified,
                )
        if verified:
            previous_builds, previous_inventory = [build], after
        elif receipt.get("install_attempted"):
            previous_builds = list(
                {b["apk_sha256"]: b for b in [*previous_builds, build]}.values()
            )
        if role is not None and verified:
            root = capture_directory(folder, artifact["request"]["id"], role)
            base = str(root.relative_to(folder))
            if available(base + "/before-inventory.json"):
                capture_before = evidence.json(root, "before-inventory.json")
                preflight = ledger(
                    evidence.json(root, "preflight-preservation.json"),
                    previous_inventory,
                    capture_before,
                )
                if available(base + "/after-capture/inventory.json"):
                    captured = replay_backup(evidence, root, "after-capture")
                    check = {
                        "batch_id": artifact["request"]["id"],
                        "role": role,
                        "preflight_preservation": preflight,
                        "changes": inventory_changes(capture_before, captured),
                        "preservation": preservation_report(capture_before, captured),
                    }
                    checks.append(check)
                    summary = evidence.json(root, "capture/summary.json")
                    if summary.get("status") == "complete" and not summary.get(
                        "fatal_error_details"
                    ):
                        _, _, expected_check = replay_capture(
                            evidence,
                            folder,
                            artifact,
                            role,
                            inputs,
                            value["screenshots"],
                            previous_inventory,
                            partial_mapping=True,
                        )
                        require(
                            check == expected_check,
                            "Completed capture continuity mismatch",
                        )
                    else:
                        halted = True
                    if not check["preservation"]["unexpected_changes"]:
                        previous_inventory = captured
                else:
                    halted = True
            else:
                halted = True
        ref_name = f"private/reference-{n:03d}-inventory.json"
        if available(ref_name):
            require(
                build == reference["build"]
                and original is not None
                and previous_inventory is not None,
                "Reference inventory has no authorized reference transaction",
            )
            current = evidence.json(folder, ref_name)
            expected = {
                "inventory": ref_name,
                "allowed_outputs": [],
                "prior_preservation": preservation_report(previous_inventory, current),
                "preservation": preservation_report(original, current),
            }
            reference_checks.append(expected)
            last_reference = current
            if (
                not expected["prior_preservation"]["unexpected_changes"]
                and not expected["preservation"]["unexpected_changes"]
            ):
                previous_inventory = current
    require(
        journal.get("operations") == completed,
        "Missing/altered completed install receipt journal",
    )
    require(
        journal.get("capture_data_checks", []) == checks,
        "Missing/altered partial capture preservation ledger",
    )
    require(
        journal.get("restoration_checks", []) == reference_checks,
        "Missing/altered reference preservation ledger",
    )
    if available("private/final-inventory.json"):
        current = evidence.json(folder, "private/final-inventory.json")
        require(
            last_reference == current and original is not None,
            "Final reference inventory receipt mismatch",
        )
        require(
            journal.get("restoration_data_changes")
            == inventory_changes(original, current),
            "Final reference changes mismatch",
        )
        ledger(
            journal.get("restoration_preservation"),
            original,
            current,
        )
    if value["restoration_verified"]:
        replay_installed_apk(
            evidence, folder, "private/final-apk", reference["build"], certificate
        )
        require(
            installs
            and last_install.get("build") == reference["build"]
            and last_install.get("install_attempted") is True
            and last_install.get("reference_validated") is True,
            "Verified restoration lacks authorized reference attempt",
        )


def replay_operations(evidence, folder, catalog, inputs, value):
    if value["mutation_run_version"] in {5, 6} and value["status"] not in {
        "qualified",
        "probe_verified",
    }:
        return replay_available_operations(evidence, folder, catalog, inputs, value)
    journal = evidence.json(folder, "journal.json")
    require(
        journal.get("status") == value["status"]
        and not any(
            journal.get(key)
            for key in (
                "error",
                "error_details",
                "capture_errors",
                "cleanup_errors",
                "restoration_error",
                "restoration_error_details",
            )
        )
        and journal.get("live_provider_requests") == 0
        and journal.get("api_spend_usd") == 0,
        "Unsuccessful operational receipt journal",
    )
    require(
        canonical_bytes(journal.get("preservation_policy"))
        == canonical_bytes(preservation_policy()),
        "Preservation policy receipt mismatch",
    )
    reference = inputs.manifest.build.model_dump()
    certificate = catalog.data["signing"]["reference_certificate_sha256"]
    original = replay_backup(
        evidence, folder, "private/original", journal.get("original_backup")
    )
    require("original_backup" in journal, "Missing original backup receipt")
    original_readback = evidence.json(folder, "private/original-readback.json")
    replay_preservation(
        journal.get("original_readback_preservation"), original, original_readback
    )
    replay_installed_apk(
        evidence, folder, "private/initial-apk", reference, certificate
    )
    replay_environment(evidence, folder, "environment/initial", reference)
    captures = (
        []
        if value["status"] == "probe_verified"
        else [
            (catalog.control, "clean"),
            (catalog.calibration, "calibration"),
            *(
                []
                if value.get("measurement_only")
                else [
                    (catalog.records[b["id"]], "mutation")
                    for b in catalog.plan["batches"]
                ]
            ),
        ]
    )
    reference_record = {"build": reference, "apk": catalog.data["reference"]["apk"]}
    expected = [catalog.control, reference_record, *[r for r, _ in captures]]
    if captures:
        expected.append(reference_record)
    operations = journal.get("operations")
    require(
        type(operations) is list and len(operations) == len(expected),
        "Missing/extra install operations in receipt journal",
    )
    previous = reference
    previous_inventory = original_readback
    allowed_outputs = set()
    checks = []
    restoration_checks = journal.get("restoration_checks")
    require(
        type(restoration_checks) is list
        and len(restoration_checks) == (2 if captures else 1),
        "Missing/extra reference preservation receipts",
    )
    for n, (operation, artifact) in enumerate(
        zip(operations, expected, strict=True), 1
    ):
        relative = f"private/install-{n:03d}"
        receipt = evidence.json(folder, relative + "/install.json")
        build = artifact["build"]
        if build == reference:
            replay_reference_install(
                evidence, folder, relative, receipt, build, certificate
            )
        require(
            operation
            == {
                "kind": "install",
                "receipt": relative + "/install.json",
                "sha256": digest(canonical_bytes(receipt)),
            }
            and receipt.get("status") == "verified"
            and receipt.get("install_attempted") is True
            and receipt.get("app_data_preserved") is True
            and receipt.get("build") == build
            and receipt.get("command")
            == [
                "install",
                "-r",
                "-d",
                str(catalog.path.parent / artifact["apk"]["path"]),
            ]
            and receipt.get("stdout", "").strip().splitlines()[-1:] == ["Success"]
            and not receipt.get("error")
            and not receipt.get("error_details"),
            "Unsuccessful install receipt",
        )
        require(
            receipt.get("previous_build")
            == replay_installed_apk(
                evidence, folder, relative + "/before-apk", previous, certificate
            )
            and receipt.get("observed_build")
            == replay_installed_apk(
                evidence, folder, relative + "/after-apk", build, certificate
            ),
            "Install build/signature readback receipt mismatch",
        )
        before = replay_backup(
            evidence, folder, relative + "/before", receipt.get("backup")
        )
        after = replay_backup(
            evidence, folder, relative + "/after", receipt.get("post_install")
        )
        readback = evidence.json(folder, relative + "/before-readback.json")
        require(
            "backup" in receipt
            and "post_install" in receipt
            and receipt.get("data_changes") == inventory_changes(before, after),
            "Install app-data backup preservation/readback mismatch",
        )
        require(
            canonical_bytes(receipt.get("preservation_policy"))
            == canonical_bytes(preservation_policy()),
            "Install preservation policy receipt mismatch",
        )
        replay_preservation(
            receipt.get("backup_readback_preservation"), before, readback
        )
        replay_preservation(receipt.get("preservation"), before, after)
        replay_preservation(receipt.get("post_readback_preservation"), readback, after)
        replay_preservation(
            receipt.get("input_preservation"), previous_inventory, before
        )
        require(
            receipt.get("environment")
            == replay_environment(evidence, folder, f"environment/{n:03d}", build),
            "Install environment receipt mismatch",
        )
        previous = build
        previous_inventory = after
        if n == 2 or (captures and n == len(expected)):
            previous_inventory = replay_reference_data(
                evidence,
                folder,
                restoration_checks[0 if n == 2 else 1],
                original,
                previous_inventory,
                allowed_outputs,
                n,
            )
        if 3 <= n < 3 + len(captures):
            capture_artifact, role = captures[n - 3]
            previous_inventory, allowed, check = replay_capture(
                evidence,
                folder,
                capture_artifact,
                role,
                inputs,
                value["screenshots"],
                after,
                measurement_only=value.get("measurement_only", False),
                legacy_measurement=(
                    value["mutation_run_version"] == 2
                    and value.get("measurement_only") is True
                    and "cleanup_policy" not in journal
                    and not any(
                        "/reads/" in name or name.endswith("/hook-cleanup.json")
                        for name in evidence.files
                    )
                ),
            )
            allowed_outputs.update(allowed)
            checks.append(check)
    require(
        canonical_bytes(journal.get("capture_data_checks", []))
        == canonical_bytes(checks),
        "Missing/failed capture inventory receipt",
    )
    final_inventory = evidence.json(folder, "private/final-inventory.json")
    require(
        final_inventory == previous_inventory,
        "Final reference app-data inventory/readback mismatch",
    )
    require(
        journal.get("restoration_data_changes")
        == inventory_changes(original, final_inventory, allowed_outputs),
        "Missing final reference data receipt",
    )
    replay_preservation(
        journal.get("restoration_preservation"),
        original,
        final_inventory,
        allowed_outputs,
    )
    replay_installed_apk(evidence, folder, "private/final-apk", reference, certificate)
    return original


def validate_run_claims(value):
    """Status and flags are a bidirectional contract, including CLI return codes."""
    if {"measurement_only", "measurement_complete", "measurement_captures"} & set(
        value
    ):
        require(
            value.get("measurement_only") is True
            and type(value.get("measurement_complete")) is bool
            and value.get("calibration_status") == "failed"
            and value.get("capture_set_qualified") is False
            and value.get("status") in {"failed", "restoration_failed"}
            and value.get("dynamic_tests") == []
            and "handoff" not in value
            and all(
                r.get("role") in {"clean", "calibration"}
                for r in value.get("screenshots", [])
            ),
            "Measurement evidence is strictly nonqualifying",
        )
        if value["measurement_complete"]:
            require(
                value["status"] == "failed"
                and value.get("downgrade_verified") is True
                and value.get("restoration_verified") is True,
                "Complete measurement requires verified downgrade/restoration",
            )
    require(
        value.get("status")
        in {
            "not_run",
            "running",
            "failed",
            "restoration_failed",
            "awaiting_builder_approval",
            "qualified",
            "probe_verified",
        }
        and all(
            type(value.get(name)) is bool
            for name in (
                "capture_set_qualified",
                "downgrade_verified",
                "restoration_verified",
                "labels_created",
            )
        )
        and value["labels_created"] is False
        and value["capture_set_qualified"] is (value["status"] == "qualified"),
        "Contradictory runtime status/flag claim",
    )
    if value["status"] in {"qualified", "probe_verified"}:
        require(
            value["downgrade_verified"] is True
            and value["restoration_verified"] is True,
            "Success status requires downgrade/restoration flags",
        )
    if value["status"] == "qualified":
        require(
            value.get("calibration_status") == "passed",
            "Incomplete calibration qualification claim",
        )
    if value["status"] == "probe_verified":
        require(
            value.get("calibration_status") == "not_run"
            and value.get("screenshots") == []
            and value.get("dynamic_tests") == [],
            "Contradictory probe-only proof claim",
        )


def verify_run(folder, catalog, inputs, *, evidence_sha256):
    """Replay an independently pinned index, never a neighboring checksum's claim."""
    folder = no_symlinks(folder)
    index_raw = contained(folder, "evidence-index.json").read_bytes()
    require(
        type(evidence_sha256) is str
        and re.fullmatch("[a-f0-9]{64}", evidence_sha256)
        and digest(index_raw) == evidence_sha256,
        "Run evidence root differs from independent SHA-256",
    )
    index = json_bytes(index_raw)
    require(
        set(index) == {"version", "files"}
        and type(index["version"]) is int
        and index["version"] in {1, 2, 3, 4, 5, 6, 7}
        and type(index["files"]) is dict,
        "Unsupported evidence index",
    )
    require(
        index["files"] == retained_files(folder)
        and {"mutation-manifest.json", "mutation-manifest.sha256", "journal.json"}
        <= set(index["files"]),
        "Run evidence membership/hash mismatch",
    )
    evidence = RunEvidence(folder, index["files"])
    raw = evidence.read(folder, "mutation-manifest.json")
    value = json_bytes(raw)
    require(
        raw == canonical_bytes(value)
        and evidence.read(folder, "mutation-manifest.sha256").decode().strip()
        == digest(raw),
        "Runtime manifest hash/canonical mismatch",
    )
    require(
        type(value["mutation_run_version"]) is int
        and value["mutation_run_version"] in {1, 2, 3, 4, 5, 6}
        and value["catalog_sha256"] == catalog.sha256
        and value["labels_created"] is False
        and value["screen_ids"] == catalog.plan["screen_ids"],
        "Runtime provenance/scope mismatch",
    )
    validate_run_claims(value)
    journal = evidence.json(folder, "journal.json")
    mode_fields = ("measurement_only", "measurement_complete")
    require(
        canonical_bytes({name: value[name] for name in mode_fields if name in value})
        == canonical_bytes(
            {name: journal[name] for name in mode_fields if name in journal}
        ),
        "Measurement flags differ from retained journal",
    )
    if value.get("measurement_complete"):
        actual = [
            (r["batch_id"], r["role"], r["screen"], r["language"], r["pass"])
            for r in value["screenshots"]
        ]
        expected = expected_capture_keys(catalog, measurement_only=True)
        require(
            len(actual) == len(expected) == 40
            and set(actual) == expected
            and not (folder / "builder-handoff").exists(),
            "Complete measurement requires the exact forty-pair matrix",
        )
    require(
        value["mutation_run_version"] != 3 and index["version"] != 4,
        "Legacy D053 run v3/index 4 cannot use the current producer; replay with "
        "the exact archived 09acc674516196be2badfae247cc1ff76228fa17 producer, "
        "without rewriting or promoting evidence",
    )
    require(
        value["mutation_run_version"] != 4 and index["version"] != 5,
        "Legacy D054 run v4/index 5 requires exact archived "
        "960dae205aafcc679e8a2b7e7cbfd569a14deb88 producer; never rewrite or promote evidence",
    )
    outside_gate = value["mutation_run_version"] == 5
    semantic_review = value["mutation_run_version"] == 6
    current_protocol = outside_gate or semantic_review
    has_d055 = (
        "cleanup_policy" in value
        or "cleanup_policy" in journal
        or any(
            name.endswith("/hook-cleanup.json") or "/reads/" in name
            for name in evidence.files
        )
    )
    require(
        current_protocol
        or not has_d055
        or (
            value.get("measurement_only") is True
            and value["mutation_run_version"] == 2
            and index["version"] == 3
        ),
        "Legacy downgrade cannot hide D055 cleanup/read artifacts",
    )
    if current_protocol:
        require(
            not value.get("measurement_only")
            and index["version"] == value["mutation_run_version"] + 1,
            "Legacy/outside-rule version/index/mode mismatch",
        )
        require(
            value.get("cleanup_policy") == cleanup_policy()
            and journal.get("cleanup_policy") == cleanup_policy(),
            "D055 cleanup policy missing or altered",
        )
        replay_reads(evidence, folder, value, inputs, catalog)
        replay_partial_d055(evidence, folder, catalog, inputs)
        # New normal evidence replays only with the exact current frozen producer;
        # a matching journal copy is corroboration, not independent authority.
        require(
            type(value.get("implementation_hashes")) is dict
            and value["implementation_hashes"] == implementation_hashes()
            and all(
                type(h) is str and re.fullmatch("[a-f0-9]{64}", h)
                for h in value["implementation_hashes"].values()
            )
            and canonical_bytes(value["implementation_hashes"])
            == canonical_bytes(journal.get("implementation_hashes")),
            "Outside-rule producer implementation hashes mismatch",
        )
    if outside_gate:
        require(
            canonical_bytes(value.get("outside_rule_policy"))
            == canonical_bytes(outside_rule_policy()),
            "Outside-rule policy missing or altered",
        )
    else:
        require(
            not ({"outside_rule_policy", "outside_rule_usage"} & set(value))
            and all(
                "outside_rule" not in r and (semantic_review or "qualified" not in r)
                for r in value["screenshots"]
            ),
            "Legacy evidence cannot downgrade outside-rule policy/proofs",
        )
    if semantic_review:
        require(
            value.get("side_effect_policy") == side_effect_policy()
            and type(value["side_effect_policy"]["version"]) is int,
            "D058 side-effect policy missing or altered",
        )
    else:
        require(
            index["version"] != 7
            and "side_effect_policy" not in value
            and all("side_effects" not in r for r in value["screenshots"]),
            "D058 evidence cannot use an older policy",
        )
    if value["mutation_run_version"] >= 2:
        require(
            canonical_bytes(value.get("preservation_policy"))
            == canonical_bytes(preservation_policy()),
            "Preservation policy missing or altered",
        )
    require(
        current_protocol
        or (
            index["version"] == 3
            and value["mutation_run_version"] == 2
            and value.get("measurement_only") is True
        )
        or (
            not value.get("measurement_complete")
            and value["capture_set_qualified"] is False
            and value["status"] not in {"qualified", "probe_verified"}
        ),
        "Legacy evidence is inspectable only, never qualified",
    )
    if value["status"] in {"qualified", "probe_verified"} or value.get(
        "measurement_complete"
    ):
        require(
            value.get("builder_content_sha256")
            == catalog.data["builder"]["content_sha256"]
            and value.get("toolchain_sha256") == catalog.data["toolchain"]["sha256"]
            and value.get("signing") == catalog.data["signing"]
            and value.get("source_commit") == catalog.data["source_commit"]
            and value.get("source_inputs") == catalog.data["inputs"]
            and value.get("languages") == ["en", "de"]
            and value.get("passes") == ["forward", "reverse"]
            and value.get("observed_occurrence_matrix")
            == occurrence_matrix(value["screenshots"]),
            "Runtime success metadata/provenance mismatch",
        )
        replay_operations(evidence, folder, catalog, inputs, value)
    elif current_protocol:
        replay_operations(evidence, folder, catalog, inputs, value)
    if value.get("measurement_complete"):
        measured = []
        for artifact, role in (
            (catalog.control, "clean"),
            (catalog.calibration, "calibration"),
        ):
            root = capture_directory(folder, artifact["request"]["id"], role)
            summary = evidence.json(root, "capture/summary.json")
            measured.append(
                {
                    "batch_id": artifact["request"]["id"],
                    "role": role,
                    "summary": str((root / "capture/summary.json").relative_to(folder)),
                    "repeatability_passed": all(
                        c["status"] == c["dump_status"] == "identical"
                        for c in summary["comparisons"]
                    ),
                }
            )
        require(
            canonical_bytes(value.get("measurement_captures"))
            == canonical_bytes(measured),
            "Measurement repeatability claims differ from retained receipts",
        )
    clean = {}
    repeats = {}
    rederived = []
    paired = {}
    authorized = expected_capture_keys(catalog)
    for record in sorted(
        value["screenshots"],
        key=lambda r: (
            r["role"] != "clean",
            r["batch_id"],
            r["pass"],
            r["language"],
            r["screen"],
        ),
    ):
        require(record["batch_id"] in catalog.records, "Unknown screenshot batch")
        require(
            (
                record["batch_id"],
                record["role"],
                record["screen"],
                record["language"],
                record["pass"],
            )
            in authorized,
            "Screenshot role/scope differs from plan",
        )
        artifact = catalog.records[record["batch_id"]]
        effective = inputs.with_build(artifact["build"])
        require(
            record["build"] == artifact["build"]
            and record.get("build_identity_sha256") == artifact["build_identity_sha256"]
            and record.get("patch_set_sha256")
            == artifact["request"]["patch_set_sha256"]
            and record["effective_manifest_sha256"] == effective.sha256,
            "Effective screenshot build identity mapping mismatch",
        )
        pair, png, raw_dump, dump = verified_pair(
            effective, folder, record, evidence=evidence
        )
        derived = dict(record)
        rederived.append(derived)
        repeat_key = (
            record["batch_id"],
            record["role"],
            record["screen"],
            record["language"],
        )
        repeats.setdefault(repeat_key, {})[record["pass"]] = (
            pair["rgba_sha256"],
            raw_dump,
        )
        require(
            all(
                record[key] == pair[key]
                for key in ("png_sha256", "rgba_sha256", "dump_sha256", "state_sha256")
            ),
            "Screenshot hash mapping mismatch",
        )
        key = (record["screen"], record["language"], record["pass"])
        if record["role"] == "clean":
            require(
                record["batch_id"] == catalog.control["request"]["id"]
                and record.get("verification") is None
                and record.get("recipe_ids") == []
                and record.get("batch_recipe_ids") == []
                and key not in clean,
                "Invalid control mapping",
            )
            clean[key] = (png, dump, record["pair_sha256"])
            if outside_gate:
                derived["outside_rule"] = outside_proof(record)
                derived["qualified"] = False
        else:
            old, old_dump, old_hash = clean[key]
            require(
                record["control_pair_sha256"] == old_hash, "Wrong comparison control"
            )
            expected_ids = (
                [catalog.plan["calibration"]["mutation_recipe_id"]]
                if record["role"] == "calibration"
                else next(
                    b["recipe_ids"]
                    for b in catalog.plan["batches"]
                    if b["id"] == record["batch_id"]
                )
            )
            carried = [
                identity
                for identity in expected_ids
                if any(
                    (o["screen"], o["language"]) == key[:2]
                    for o in catalog.plan["mutations"][identity]["occurrences"]
                )
            ]
            require(
                record["batch_recipe_ids"] == expected_ids
                and record["recipe_ids"] == carried,
                "Screenshot recipe mapping differs from plan",
            )
            expected = verify_screen(
                old,
                png,
                old_dump,
                dump,
                [catalog.plan["mutations"][identity] for identity in expected_ids],
            )
            require(
                canonical_bytes(record["verification"]) == canonical_bytes(expected),
                "Dynamic gate replay mismatch",
            )
            if outside_gate:
                derived["verification"] = expected
                measure_outside_record(derived, old, png, old_dump, dump, paired)
            if semantic_review:
                derived["verification"] = expected
        if semantic_review:
            record_semantic_review(derived)
            require(
                canonical_bytes(record.get("side_effects"))
                == canonical_bytes(derived["side_effects"])
                and record.get("qualified") is derived["qualified"],
                "D058 side-effect/qualification replay mismatch",
            )
    if outside_gate:
        for record, derived in zip(
            sorted(
                value["screenshots"],
                key=lambda r: (
                    r["role"] != "clean",
                    r["batch_id"],
                    r["pass"],
                    r["language"],
                    r["screen"],
                ),
            ),
            rederived,
            strict=True,
        ):
            require(
                canonical_bytes(record.get("outside_rule"))
                == canonical_bytes(derived["outside_rule"])
                and type(record.get("qualified")) is bool
                and record["qualified"] is derived["qualified"],
                "Outside-rule proof/repeat/qualification replay mismatch",
            )
        require(
            canonical_bytes(value.get("outside_rule_usage"))
            == canonical_bytes(outside_usage(catalog, rederived, value["status"])),
            "Outside-rule usage replay mismatch",
        )
    if current_protocol:
        calibration_rows = [r for r in rederived if r["role"] == "calibration"]
        # replay_operations authenticates the ordered probe/control/calibration
        # prefix. APK identity alone is not a role: production may reinstall it.
        calibration_install = "private/install-004/install.json"
        calibration_attempted = bool(calibration_rows) or (
            calibration_install in evidence.files
            and evidence.json(folder, calibration_install).get("build")
            == catalog.calibration["build"]
        )
        root = capture_directory(
            folder, catalog.calibration["request"]["id"], "calibration"
        )
        summary_path = str((root / "capture/summary.json").relative_to(folder))
        summary = {}
        if summary_path in evidence.files:
            summary = evidence.json(root, "capture/summary.json")
            effective = inputs.with_build(catalog.calibration["build"])
            require(
                summary.get("schema_version") == 1
                and summary.get("manifest_sha256") == effective.sha256
                and summary.get("selection")
                == effective.capture_selection(["en", "de"])
                and summary.get("languages") == ["en", "de"]
                and summary.get("passes") == ["forward", "reverse"],
                "Calibration capture attempt summary scope mismatch",
            )
            calibration_attempted = True
        calibration_attempted = calibration_attempted or any(
            name.startswith(str(root.relative_to(folder)) + "/")
            for name in evidence.files
        )
        calibration_expected = {k[2:] for k in authorized if k[1] == "calibration"}
        keys = [(r["screen"], r["language"], r["pass"]) for r in calibration_rows]
        complete = (
            len(keys) == len(calibration_expected)
            and set(keys) == calibration_expected
            and all(r["qualified"] for r in calibration_rows)
            and all(
                set(passes) == {1, 2} and passes[1] == passes[2]
                for key, passes in repeats.items()
                if key[1] == "calibration"
            )
            and summary.get("status") == "complete"
            and not summary.get("fatal_error_details")
            and not summary.get("cleanup_errors")
            and summary.get("settings_restored") is True
            and summary.get("saves_unchanged") is True
            and (
                not outside_gate
                or not any(
                    p["role"] == "calibration"
                    for p in value["outside_rule_usage"]["engineering_pauses"]
                )
            )
            and str((root / "after-capture/inventory.json").relative_to(folder))
            in evidence.files
            and any(
                c.get("role") == "calibration"
                and c.get("batch_id") == catalog.calibration["request"]["id"]
                and not c.get("preservation", {}).get("unexpected_changes")
                for c in journal.get("capture_data_checks", [])
            )
        )
        if complete:
            require(
                calibration_install in evidence.files,
                "Calibration completion lacks exact verified install",
            )
            install = evidence.json(folder, calibration_install)
            require(
                install.get("build") == catalog.calibration["build"]
                and install.get("status") == "verified",
                "Calibration completion lacks exact verified install",
            )
            calibration_input = replay_backup(
                evidence,
                folder,
                str(Path(calibration_install).parent / "after"),
                install.get("post_install"),
            )
            replay_capture(
                evidence,
                folder,
                catalog.calibration,
                "calibration",
                inputs,
                value["screenshots"],
                calibration_input,
            )
        calibration_status = (
            "passed" if complete else "failed" if calibration_attempted else "not_run"
        )
        require(
            value.get("calibration_status") == calibration_status,
            "Calibration status contradicts authenticated attempt/repeat/gates",
        )
    require(
        value["dynamic_split_rate"] == split_rate(value["dynamic_tests"]),
        "Dynamic split rate mismatch",
    )
    if value["capture_set_qualified"]:
        parents = {
            event["parent"]["id"]: event["parent"]["recipe_ids"]
            for event in catalog.plan["split_history"]
        }
        batches = {b["id"]: b["recipe_ids"] for b in catalog.plan["batches"]}
        nodes = {**parents, **batches}
        stages = [
            {"id": b["id"], "recipe_ids": b["recipe_ids"], "split": False}
            for b in catalog.plan["batches"]
        ]
        require(
            value["dynamic_tests"][-len(stages) :] == stages
            and all(
                set(test) == {"id", "recipe_ids", "split"}
                and test["id"] in nodes
                and test["recipe_ids"] == nodes[test["id"]]
                and test["split"] is (test["id"] in parents)
                for test in value["dynamic_tests"]
            ),
            "Qualified dynamic production stage gates differ from plan",
        )
        require(
            value["status"] == "qualified"
            and value["calibration_status"] == "passed"
            and value["downgrade_verified"]
            and value["restoration_verified"],
            "Incomplete qualification claim",
        )
        expected = authorized
        actual = [
            (r["batch_id"], r["role"], r["screen"], r["language"], r["pass"])
            for r in value["screenshots"]
        ]
        require(
            len(actual) == len(set(actual)) and set(actual) == expected,
            "Qualified run has missing/duplicate captures",
        )
        require(
            all(
                set(passes) == {1, 2} and passes[1] == passes[2]
                for passes in repeats.values()
            ),
            "Forward/reverse RGBA or raw dump repeatability failure",
        )
        require(
            all(
                r["verification"] is None
                or (r["qualified"] if current_protocol else r["verification"]["passed"])
                for r in value["screenshots"]
            ),
            "Failed screenshot in qualified run",
        )
        require(
            not outside_gate or not value["outside_rule_usage"]["engineering_pauses"],
            "Outside-rule engineering pause cannot qualify",
        )
    return value
