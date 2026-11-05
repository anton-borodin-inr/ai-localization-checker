"""Plan translation-only dev mutation batches entirely offline."""

import argparse
import sys
from pathlib import Path

from l10n_checker.capture import CaptureError
from l10n_checker.mutation_plan import create_plan, load_plan
from l10n_checker.screen_capture import manifest_output_directory
from l10n_checker.screen_manifest import digest
from l10n_checker.text_dump import canonical_bytes


def build_requests(plan):
    """Builder inputs only: no invented APK hashes/version codes or device commands."""
    requests = {}
    for batch, role in [
        (plan["clean_build"], "clean"),
        *[(b, "mutation") for b in plan["batches"]],
    ]:
        requests[batch["patch_set_sha256"]] = {
            "id": batch["id"],
            "patch_set_sha256": batch["patch_set_sha256"],
            "patches": batch["patches"],
            "role": role,
            "calibration": False,
        }
    identity = plan["calibration"]["mutation_recipe_id"]
    patches = [plan["mutations"][identity]["patch"]]
    checksum = digest(canonical_bytes(patches))
    if checksum not in requests:
        requests[checksum] = {
            "id": f"batch-{checksum[:16]}",
            "patch_set_sha256": checksum,
            "patches": patches,
            "role": "calibration",
            "calibration": True,
        }
    requests[checksum]["calibration"] = True
    return {
        "requests_version": 1,
        "source_commit": plan["fork_commit"],
        "plan_sha256": digest(canonical_bytes(plan)),
        "recipe_version": plan["recipe_version"],
        "requests": sorted(requests.values(), key=lambda r: r["id"]),
        "constraints": {
            "translation_files_only": True,
            "same_builder_for_empty_and_mutated_patches": True,
            "build_only_no_device_operations": True,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser(
        "plan", help="Write an unqualified offline plan and builder requests"
    )
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--recipes", type=Path, required=True)
    plan.add_argument("--inventory", type=Path, required=True)
    selector = plan.add_mutually_exclusive_group(required=True)
    selector.add_argument("--split", choices=["dev"])
    selector.add_argument("--screen-id", action="append", dest="screen_ids")
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--output-dir", type=Path, required=True)
    for name in ("run", "probe", "verify"):
        command = commands.add_parser(
            name,
            help="Catalog-bound dev runtime"
            if name != "verify"
            else "Offline replay of retained dev evidence",
        )
        command.add_argument("--catalog", type=Path, required=True)
        command.add_argument("--sha256", required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--recipes", type=Path, required=True)
        command.add_argument("--sdk", type=Path, required=True)
        command.add_argument("--jdk", type=Path, required=True)
        if name == "verify":
            command.add_argument("--run-dir", type=Path, required=True)
            command.add_argument("--evidence-sha256", required=True)
        else:
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--approved-output-root", type=Path, required=True)
            command.add_argument("--serial")
            command.add_argument("--resume-from", type=Path)
            command.add_argument("--resume-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command != "plan":
            from l10n_checker.mutation_run import (
                run_config,
                validate_run_claims,
                verify_run,
            )

            if args.command == "verify":
                from l10n_checker.mutation_catalog import ApkTools, read_catalog
                from l10n_checker.screen_manifest import Inputs

                catalog = read_catalog(
                    args.catalog,
                    args.sha256,
                    manifest=args.manifest,
                    recipes=args.recipes,
                    tools=ApkTools(args.sdk, args.jdk),
                )
                value = verify_run(
                    args.run_dir,
                    catalog,
                    Inputs(args.manifest, split="dev"),
                    evidence_sha256=args.evidence_sha256,
                )
            else:
                config = {
                    name: str(getattr(args, name))
                    for name in (
                        "catalog",
                        "sha256",
                        "manifest",
                        "recipes",
                        "sdk",
                        "jdk",
                        "output_dir",
                        "approved_output_root",
                    )
                }
                if args.serial:
                    config["serial"] = args.serial
                if args.resume_from:
                    config["resume_from"] = str(args.resume_from)
                if args.resume_sha256:
                    config["resume_sha256"] = args.resume_sha256
                value = run_config(config, probe_only=args.command == "probe")
            validate_run_claims(value)
            print(f"Mutation runtime: {value['status']}; no labels")
            print(
                f"Evidence SHA-256: {value.get('evidence_sha256', args.evidence_sha256 if args.command == 'verify' else 'unavailable')}"
            )
            return 0 if value["status"] in {"qualified", "probe_verified"} else 2
        result = create_plan(
            manifest=args.manifest,
            recipes=args.recipes,
            inventory=args.inventory,
            seed=args.seed,
            split=args.split,
            screen_ids=args.screen_ids,
        )
        raw = canonical_bytes(result)
        load_plan(raw, manifest=args.manifest)
        folder = manifest_output_directory(args.output_dir, False)
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "build-requests.json").open("xb") as stream:
            stream.write(canonical_bytes(build_requests(result)))
        with (folder / "plan.json").open("xb") as stream:
            stream.write(raw)
        print(f"Offline plan: {folder / 'plan.json'} (not production-ready)")
    except (CaptureError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Mutation planning error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
