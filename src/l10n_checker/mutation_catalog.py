"""Authenticated, read-only catalog-v1 inputs. No builder or device execution."""

import io
import os
import re
import subprocess
import zipfile
from pathlib import Path

from l10n_checker.capture import CaptureError
from l10n_checker.screen_manifest import digest

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
