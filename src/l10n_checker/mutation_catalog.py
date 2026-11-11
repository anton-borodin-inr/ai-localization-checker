"""Authenticated, read-only catalog-v1 inputs. No builder or device execution."""

import io
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest, json_bytes
from l10n_checker.text_dump import canonical_bytes

TRANSLATIONS = tuple(
    f"android/assets/jsons/translations/{name}.properties"
    for name in ("English", "German")
)
BUILDER_SHA256 = "e9ec71c5bb0d8816bfa84c1eab911e6b7a0d3300d0bc54ae2b8357a058478086"
CHECKER_COMMIT = "e26914a4870d7755634cf547931f88c3e3093e5c"
INSTALLATION = {
    "command_template": ["adb", "install", "-r", "-d", "<apk>"],
    "requires_debuggable": True,
    "downgrade_permission_required": True,
    "uninstall_allowed": False,
    "backup_restore_required_in_part_c": True,
    "emulator_downgrade_verified": False,
    "app_data_preservation_verified": False,
}


def require(condition, message):
    if not condition:
        raise CaptureError(message)


def fields(value, keys):
    require(
        type(value) is dict and set(value) == set(keys), "Unexpected catalog fields"
    )


def no_symlinks(path):
    path = Path(path).absolute()
    require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        "Symbolic-link path component",
    )
    return path


class HashGraph:
    """Keep the exact authenticated bytes; never re-read a mutable sidecar as input."""

    def __init__(self, root):
        self.root = no_symlinks(root)
        self.files = {}

    def read(self, ref):
        fields(ref, {"path", "sha256", "bytes"})
        name = ref["path"]
        require(
            type(name) is str
            and name
            and not Path(name).is_absolute()
            and ".." not in Path(name).parts,
            "Unsafe catalog path",
        )
        require(
            type(ref["bytes"]) is int and 0 <= ref["bytes"] <= 128 * 1024**2,
            "Invalid reference size",
        )
        require(
            type(ref["sha256"]) is str and re.fullmatch("[a-f0-9]{64}", ref["sha256"]),
            "Invalid reference hash",
        )
        path = no_symlinks(self.root / name)
        require(
            path.is_file() and path.stat().st_size == ref["bytes"],
            "Reference size mismatch",
        )
        raw = path.read_bytes()
        require(digest(raw) == ref["sha256"], "Reference hash mismatch")
        if name in self.files:
            require(self.files[name] == raw, "Reference changed during read")
            return raw
        self.files[name] = raw
        if path.suffix == ".json":
            self.walk(json_bytes(raw))
        return raw

    def walk(self, value):
        if isinstance(value, dict):
            if {"path", "sha256", "bytes"} <= set(value):
                self.read(value)
            else:
                for child in value.values():
                    self.walk(child)
        elif isinstance(value, list):
            for child in value:
                self.walk(child)

    def recheck(self):
        for name, raw in self.files.items():
            path = no_symlinks(self.root / name)
            require(
                path.read_bytes() == raw, "Catalog file changed during verification"
            )


def apply_patches(originals, patches):
    """Independent literal RHS implementation, preserving all unrelated bytes."""
    result = dict(originals)
    targets = set()
    for patch in patches:
        fields(patch, {"file", "operation", "key", "original", "replacement"})
        name, key, operation = patch["file"], patch["key"], patch["operation"]
        require(
            name in TRANSLATIONS
            and name in originals
            and operation in {"add", "replace", "remove"},
            "Invalid translation edit",
        )
        require((name, key) not in targets, "Conflicting translation edit")
        targets.add((name, key))
        for literal in (key, patch["original"], patch["replacement"]):
            require(
                literal is None
                or (
                    type(literal) is str
                    and not any(c in literal for c in "\r\n\\\0")
                    and not any(0xD800 <= ord(c) <= 0xDFFF for c in literal)
                ),
                "Invalid patch literal",
            )
        require(
            type(key) is str
            and key
            and key == key.strip()
            and " = " not in key
            and not key.startswith("#"),
            "Invalid source key",
        )
        require(
            (operation == "add") == (patch["original"] is None)
            and (operation == "remove") == (patch["replacement"] is None),
            "Invalid patch absence",
        )
        require(
            patch["replacement"] is None
            or (
                patch["replacement"].strip()
                and patch["replacement"] != patch["original"]
            ),
            "Empty/no-op replacement",
        )
    for name, raw in originals.items():
        raw.decode("utf-8", errors="strict")
        lines = raw.splitlines(keepends=True)
        changes, additions = {}, []
        for patch in sorted(
            (p for p in patches if p["file"] == name), key=lambda p: p["key"]
        ):
            key = patch["key"].encode("utf-8")
            hits = []
            for index, line in enumerate(lines):
                content = line.rstrip(b"\r\n")
                if not content.startswith(b"#") and b" = " in content:
                    source, rhs = content.split(b" = ", 1)
                    if source == key:
                        hits.append((index, rhs, line[len(content) :]))
            if patch["operation"] == "add":
                require(not hits, "Add requires absent original")
                additions.append(key + b" = " + patch["replacement"].encode("utf-8"))
            else:
                require(len(hits) == 1, "Ambiguous/missing original entry")
                index, rhs, ending = hits[0]
                require(
                    rhs == patch["original"].encode("utf-8"),
                    "Translation original RHS mismatch",
                )
                changes[index] = (
                    b""
                    if patch["operation"] == "remove"
                    else key + b" = " + patch["replacement"].encode("utf-8") + ending
                )
        output = b"".join(changes.get(i, line) for i, line in enumerate(lines))
        if additions:
            require(not raw or raw.endswith(b"\n"), "Addition needs final LF")
            ending = (
                b"\r\n" if raw and raw.count(b"\r\n") == raw.count(b"\n") else b"\n"
            )
            output += ending.join(additions) + ending
        result[name] = output
    return result


def certificate(text):
    counts = re.findall(r"(?m)^Number of signers: (\d+)$", text)
    require(not counts or counts == ["1"], "Unexpected signer count")
    matches = re.findall(
        r"(?m)^(?:Signer #\d+ |V2 Signer: )certificate SHA-256 digest: ([a-fA-F0-9]{64})$",
        text,
    )
    require(len(matches) == 1, "Missing/ambiguous APK signing certificate")
    return matches[0].lower()


def normalize_manifest(text):
    result, count = re.subn(
        r"(?m)^(\s*A: (?:android:|http://schemas\.android\.com/apk/res/android:)versionCode\(0x0101021b\)=).*$",
        r"\1<allocated-versionCode>",
        text,
    )
    require(count == 1, "Cannot normalize exactly one versionCode")
    return result


class ApkTools:
    def __init__(self, sdk, jdk):
        self.tools = Path(sdk) / "build-tools/37.0.0"
        self.jdk = Path(jdk)

    def inspect(self, path):
        before = digest(path.read_bytes())
        env = {
            "PATH": str(self.jdk / "bin") + ":/usr/bin:/bin",
            "JAVA_HOME": str(self.jdk),
            "LANG": "C",
            "LC_ALL": "C",
        }
        if os.environ.get("TMPDIR"):
            env["TMPDIR"] = os.environ["TMPDIR"]

        def run(*args):
            try:
                return subprocess.run(
                    list(map(str, args)),
                    check=True,
                    capture_output=True,
                    timeout=120,
                    env=env,
                ).stdout.decode("utf-8")
            except (OSError, subprocess.SubprocessError) as exc:
                raise CaptureError("Native APK verification failed") from exc

        signed = run(
            self.tools / "apksigner", "verify", "--verbose", "--print-certs", path
        )
        badging = run(self.tools / "aapt2", "dump", "badging", path)
        match = re.search(
            r"(?m)^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'",
            badging,
        )
        require(match is not None, "Missing APK package metadata")
        package, version, name = match.groups()
        require(
            package == "com.unciv.app"
            and name == "4.22.10"
            and "application-debuggable" in badging.splitlines(),
            "Unexpected package/version/debuggable APK",
        )
        xml = run(
            self.tools / "aapt2",
            "dump",
            "xmltree",
            path,
            "--file",
            "AndroidManifest.xml",
        )
        require(
            digest(path.read_bytes()) == before,
            "APK changed during native verification",
        )
        return {
            "certificate_sha256": certificate(signed),
            "version_code": version,
            "normalized_manifest": normalize_manifest(xml).encode(),
        }


def apk_payloads(raw, translations):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [m.filename for m in archive.infolist() if not m.is_dir()]
        require(len(names) == len(set(names)), "Duplicate APK ZIP member")
        require(
            all(not n.startswith("/") and ".." not in Path(n).parts for n in names),
            "Unsafe APK member",
        )
        require(
            sum(m.file_size for m in archive.infolist()) < 512 * 1024**2,
            "Oversized APK payload",
        )
        payloads = {name: digest(archive.read(name)) for name in names}
        for name, expected in translations.items():
            member = name.removeprefix("android/")
            require(
                member in names and archive.read(member) == expected,
                "Packaged translation bytes differ",
            )
    return payloads


def invariant_payloads(payloads, manifest):
    translations = {name.removeprefix("android/") for name in TRANSLATIONS}
    result = {
        n: h
        for n, h in payloads.items()
        if n not in translations
        and n != "AndroidManifest.xml"
        and n != "META-INF/MANIFEST.MF"
        and not re.fullmatch(r"META-INF/[^/]+\.(SF|RSA|DSA|EC)", n)
    }
    result["AndroidManifest.xml (versionCode normalized)"] = digest(manifest)
    return result


@dataclass
class Catalog:
    path: Path
    sha256: str
    data: dict
    plan: dict
    records: dict
    graph: HashGraph

    @property
    def control(self):
        return self.records[self.data["empty_control_id"]]

    @property
    def calibration(self):
        return next(r for r in self.records.values() if r["request"]["calibration"])

    def apk_path(self, record):
        self.graph.recheck()
        return no_symlinks(self.path.parent / record["apk"]["path"])


def source_assets(pin):
    excluded = {"SaveFiles", "fonts", "maps", "music", "mods", "CVS", "SCCS"}
    result = {}
    for name, checksum in pin.items():
        if not name.startswith("android/assets/"):
            continue
        parts = Path(name.removeprefix("android/assets/")).parts
        if any(p in excluded or p.startswith(".") or p.endswith("~") for p in parts):
            continue
        if parts[-1].lower() in {"thumbs.db", "picasa.ini"} or parts[-1].endswith(
            ".scc"
        ):
            continue
        result[name.removeprefix("android/")] = checksum
    return result


def read_catalog(
    path, sha256, *, manifest, recipes, tools, builder_sha256=BUILDER_SHA256
):
    """Validate the authenticated graph against independently supplied authority."""
    from l10n_checker.mutation_cli import build_requests
    from l10n_checker.mutation_plan import load_plan

    try:
        path = no_symlinks(path)
        raw = path.read_bytes()
        require(
            type(sha256) is str
            and re.fullmatch("[a-f0-9]{64}", sha256)
            and digest(raw) == sha256,
            "Catalog differs from approved SHA-256",
        )
        data = json_bytes(raw)
        require(raw == canonical_bytes(data), "Noncanonical catalog")
        fields(
            data,
            {
                "catalog_version",
                "source_commit",
                "source_tree",
                "checker_commit",
                "inputs",
                "builder",
                "toolchain",
                "signing",
                "reference",
                "installation",
                "empty_control_id",
                "artifacts",
                "qualification",
                "source_inventory",
                "source_assets",
                "source_translations",
            },
        )
        require(
            type(data["catalog_version"]) is int
            and data["catalog_version"] == 1
            and data["checker_commit"] == CHECKER_COMMIT,
            "Unsupported catalog version/authority",
        )
        require(
            canonical_bytes(data["installation"]) == canonical_bytes(INSTALLATION),
            "Unsafe catalog installation semantics",
        )
        require(
            canonical_bytes(data["qualification"])
            == canonical_bytes(
                {
                    "stage": "built_unqualified",
                    "production_ready": False,
                    "device_verification": "not_run_part_c",
                    "labels_created": False,
                }
            ),
            "Unexpected catalog qualification claim",
        )
        graph = HashGraph(path.parent)
        graph.walk(data)
        fields(data["inputs"], {"plan", "requests", "recipes", "manifest", "split"})
        inputs = {name: graph.read(ref) for name, ref in data["inputs"].items()}
        require(
            inputs["manifest"] == manifest.read_bytes()
            and inputs["split"] == manifest.with_name("split.json").read_bytes()
            and inputs["recipes"] == recipes.read_bytes(),
            "Catalog input authority mismatch",
        )
        plan = load_plan(inputs["plan"], manifest=manifest)
        require(
            inputs["plan"] == canonical_bytes(plan)
            and inputs["requests"] == canonical_bytes(build_requests(plan)),
            "Catalog requests differ from validated plan",
        )
        recipe_data = json_bytes(inputs["recipes"])
        require(
            {r["id"]: r for r in recipe_data["recipes"]}
            == {identity: m["recipe"] for identity, m in plan["mutations"].items()},
            "Plan differs from frozen recipes",
        )
        authority = json_bytes(inputs["manifest"])
        require(
            data["source_commit"]
            == plan["fork_commit"]
            == authority["build"]["fork_commit"],
            "Source commit mismatch",
        )
        fields(
            data["builder"], {"files", "content_sha256", "git_head", "worktree_dirty"}
        )
        fields(
            data["builder"]["files"],
            {
                "l10n_apk_builder.py",
                "l10n_builder_runtime.py",
                "l10n-builder.init.gradle",
            },
        )
        builder = digest(
            canonical_bytes(
                {name: ref["sha256"] for name, ref in data["builder"]["files"].items()}
            )
        )
        require(
            builder == data["builder"]["content_sha256"] == builder_sha256,
            "Builder content identity mismatch",
        )
        fields(data["reference"], {"apk", "version_code"})
        fields(
            data["signing"],
            {
                "reference_certificate_sha256",
                "builder_certificate_sha256",
                "reference_apk_sha256",
            },
        )
        original = {
            name: graph.read(ref) for name, ref in data["source_translations"].items()
        }
        fields(original, TRANSLATIONS)
        pin = json_bytes(graph.read(data["source_inventory"]))
        assets = json_bytes(graph.read(data["source_assets"]))
        require(
            all(pin.get(name) == digest(value) for name, value in original.items())
            and source_assets(pin) == assets,
            "Source translation/asset inventory mismatch",
        )
        reference = data["reference"]
        require(
            reference["version_code"] == "1271048"
            and reference["apk"]["sha256"]
            == authority["build"]["apk_sha256"]
            == data["signing"]["reference_apk_sha256"],
            "Original reference APK mismatch",
        )
        apk_payloads(graph.read(reference["apk"]), original)
        inspected = tools.inspect(path.parent / reference["apk"]["path"])
        cert = inspected["certificate_sha256"]
        require(
            inspected["version_code"] == "1271048"
            and cert
            == data["signing"]["reference_certificate_sha256"]
            == data["signing"]["builder_certificate_sha256"],
            "Reference certificate/version mismatch",
        )
        requests = build_requests(plan)["requests"]
        require(
            [e["id"] for e in data["artifacts"]] == [r["id"] for r in requests],
            "Missing/extra/duplicate artifact",
        )
        records, codes, invariant = {}, set(), None
        entries = {e["id"]: e for e in data["artifacts"]}
        for request in sorted(requests, key=lambda r: (r["role"] != "clean", r["id"])):
            entry = entries[request["id"]]
            fields(entry, {"id", "record"})
            record_raw = graph.read(entry["record"])
            record = json_bytes(record_raw)
            require(
                record_raw == canonical_bytes(record), "Noncanonical artifact record"
            )
            fields(
                record,
                {
                    "record_version",
                    "request",
                    "build_identity_sha256",
                    "build",
                    "certificate_sha256",
                    "apk",
                    "translations",
                    "zip_payloads",
                    "normalized_manifest",
                    "source_audits",
                    "reproducibility",
                    "reused_from_catalog_sha256",
                },
            )
            require(
                type(record["record_version"]) is int
                and record["record_version"] == 1
                and canonical_bytes(record["request"]) == canonical_bytes(request),
                "Artifact request differs from plan",
            )
            identity = digest(
                canonical_bytes(
                    {
                        "identity_version": 1,
                        "source_commit": data["source_commit"],
                        "patch_set_sha256": request["patch_set_sha256"],
                        "builder_sha256": builder,
                        "toolchain_sha256": data["toolchain"]["sha256"],
                        "certificate_sha256": cert,
                    }
                )
            )
            code = str(1800000000 + int(identity, 16) % 100000000)
            require(
                record["build_identity_sha256"] == identity and code not in codes,
                "Invalid/duplicate build identity",
            )
            codes.add(code)
            require(
                record["build"]
                == {
                    "version_code": code,
                    "apk_sha256": record["apk"]["sha256"],
                    "fork_commit": data["source_commit"],
                    "implementation_commit": data["source_commit"],
                },
                "Invalid checker build projection",
            )
            apk = graph.read(record["apk"])
            inspected = tools.inspect(path.parent / record["apk"]["path"])
            require(
                inspected["certificate_sha256"] == record["certificate_sha256"] == cert
                and inspected["version_code"] == code,
                "APK certificate/version mismatch",
            )
            normalized = inspected["normalized_manifest"]
            require(
                normalized == graph.read(record["normalized_manifest"]),
                "APK normalized manifest mismatch",
            )
            expected = apply_patches(original, request["patches"])
            fields(record["translations"], TRANSLATIONS)
            for name, value in record["translations"].items():
                fields(value, {"source_sha256", "file"})
                require(
                    value["source_sha256"] == digest(original[name])
                    and graph.read(value["file"]) == expected[name],
                    "Translation bytes differ from validated plan",
                )
            payloads = apk_payloads(apk, expected)
            require(
                payloads == json_bytes(graph.read(record["zip_payloads"])),
                "APK payload inventory mismatch",
            )
            expected_assets = {
                **assets,
                **{n.removeprefix("android/"): digest(v) for n, v in expected.items()},
            }
            require(
                {n: h for n, h in payloads.items() if n.startswith("assets/")}
                == expected_assets,
                "Unapproved packaged asset",
            )
            current = invariant_payloads(payloads, normalized)
            if invariant is None:
                require(
                    request["role"] == "clean"
                    and request["id"] == data["empty_control_id"],
                    "Missing same-builder empty control",
                )
                invariant = current
            require(current == invariant, "Nontranslation APK payload drift")
            audit = {
                "files_verified": len(pin),
                "expected_inventory_sha256": digest(
                    canonical_bytes(
                        {**pin, **{n: digest(v) for n, v in expected.items()}}
                    )
                ),
            }
            require(record["source_audits"] == [audit, audit], "Source audit mismatch")
            repro = record["reproducibility"]
            fields(
                repro,
                {
                    "passes",
                    "translation_files_byte_identical",
                    "apk_byte_identical",
                    "pass_1_apk_sha256",
                    "pass_2_apk_sha256",
                    "pass_2_zip_payloads",
                    "pass_2_normalized_manifest",
                    "different_zip_entries",
                },
            )
            require(
                type(repro["passes"]) is int
                and repro["passes"] == 2
                and repro["translation_files_byte_identical"] is True
                and repro["pass_1_apk_sha256"] == digest(apk),
                "Invalid two-pass evidence",
            )
            require(
                type(repro["apk_byte_identical"]) is bool
                and type(repro["pass_2_apk_sha256"]) is str
                and re.fullmatch("[a-f0-9]{64}", repro["pass_2_apk_sha256"])
                and repro["apk_byte_identical"]
                == (repro["pass_1_apk_sha256"] == repro["pass_2_apk_sha256"]),
                "False APK reproducibility claim",
            )
            second = json_bytes(graph.read(repro["pass_2_zip_payloads"]))
            require(
                invariant_payloads(
                    second, graph.read(repro["pass_2_normalized_manifest"])
                )
                == invariant
                and {n: h for n, h in second.items() if n.startswith("assets/")}
                == expected_assets,
                "Second-pass payload drift",
            )
            require(
                repro["different_zip_entries"]
                == sorted(
                    n
                    for n in set(payloads) | set(second)
                    if payloads.get(n) != second.get(n)
                ),
                "Two-pass difference report mismatch",
            )
            records[request["id"]] = record
        graph.recheck()
        require(path.read_bytes() == raw, "Catalog changed during verification")
        return Catalog(path, sha256, data, plan, records, graph)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise CaptureError(f"Invalid artifact catalog: {exc}") from exc
