"""Reproduce issue 10's candidate reference from pinned sources and verified APKs.

This is a narrow assembly of manually selected translation entries, not OCR or
a general Unciv translation engine. Anton must confirm the visible spans before
any experiment call. No provider is imported and no key is needed.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = "android/assets/jsons/translations/"
TECHS = [
    "Agriculture",
    "Animal Husbandry",
    "Archery",
    "Mining",
    "Writing",
    "Trapping",
    "The Wheel",
    "Masonry",
    "Bronze Working",
    "Horseback Riding",
    "Mathematics",
    "Construction",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_bytes(source, commit, path):
    return subprocess.check_output(
        ["git", "-C", str(source), "show", f"{commit}:{path}"]
    )


def properties(data):
    entries = {}
    for number, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if line.lstrip().startswith(("#", "!")) or " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        entries[key] = {"key": key, "value": value, "line": number}
    return entries


def prepare(source, apk_dir):
    manifest = json.loads((ROOT / "docs/evidence/8/pair-manifest.json").read_text())
    builds = {}
    tables = {}
    for kind in ("clean", "defective"):
        build = manifest["builds"][kind]
        commit = build["fork_commit"]
        apk = apk_dir / build["apk"]
        apk_bytes = apk.read_bytes()
        if sha(apk_bytes) != build["apk_sha256"]:
            raise ValueError(f"APK hash differs from issue 8: {kind}")
        config = source_bytes(source, commit, "buildSrc/src/main/kotlin/BuildConfig.kt")
        if f"appCodeNumber = {build['version_code']}".encode() not in config:
            raise ValueError("Build code does not match pinned source")
        resources = {}
        with ZipFile(apk) as archive:
            for lang in ("English", "German"):
                path = RESOURCE + lang + ".properties"
                data = source_bytes(source, commit, path)
                packaged = archive.read(
                    "assets/jsons/translations/" + lang + ".properties"
                )
                if data != packaged:
                    raise ValueError(f"Source/APK translation mismatch: {kind}/{lang}")
                resources[lang] = {
                    "path": path,
                    "sha256": sha(data),
                    "apk_bytes_equal": True,
                }
                tables[kind, lang] = properties(data)
        builds[kind] = {
            "version_code": build["version_code"],
            "commit": commit,
            "repository": "https://github.com/anton-borodin-inr/Unciv",
            "apk_sha256": sha(apk_bytes),
            "translations": resources,
        }

    screens = []
    for capture in manifest["captures"]:
        filename = capture["file"]
        image = ROOT / "docs/evidence/8/final" / filename
        if sha(image.read_bytes()) != capture["sha256"]:
            raise ValueError(f"Screenshot hash differs: {filename}")
        kind = "defective" if capture["variant"] == "injected" else "clean"
        lang = capture["language"]
        table = tables[kind, lang]
        rows = []

        def tr(key, table=table):
            entry = table[key]
            return entry["value"] or entry["key"]

        def row(
            identifier,
            key,
            section,
            region,
            text=None,
            visibility="full",
            keys=(),
            table=table,
            rows=rows,
            tr=tr,
        ):
            rows.append(
                {
                    "id": identifier,
                    "section": section,
                    "region": region,
                    "text_seen": tr(key) if text is None else text,
                    "visibility": visibility,
                    "primary_denominator": visibility in ("full", "visible_prefix"),
                    "sources": [table[k] for k in (key, *keys)],
                }
            )

        regions = [
            "top-left",
            "top",
            "center",
            "center",
            "top",
            "top",
            "center",
            "center",
            "bottom",
            "top-right",
            "right",
            "right",
        ]
        for key, region in zip(TECHS, regions, strict=True):
            if key == "Writing" and lang == "English":
                # Its icons are visible; the title is entirely above the frame.
                continue
            visibility = "vertical_clip" if key == "Writing" else "full"
            text = tr(key)
            if key == "Mining" and kind == "defective":
                text, visibility = "Bergbau und Erzgew...", "visible_prefix"
            row(key, key, "tree", region, text, visibility)

        if kind == "clean":
            row("close", "Close", "controls", "bottom-left")
            research = tr("Research [technology]").replace(
                "[technology]", tr("Archery")
            )
            row(
                "research",
                "Research [technology]",
                "controls",
                "bottom-right",
                research,
                keys=("Archery",),
            )
        row(
            "units-heading",
            "Units enabled",
            "description",
            "bottom-left",
            tr("Units enabled") + ":",
        )
        row("archer", "Archer", "description", "bottom-left")
        row(
            "wonders-heading",
            "Wonders enabled",
            "description",
            "bottom-left",
            tr("Wonders enabled") + ":",
        )

        clip = "vertical_clip" if lang == "German" and kind == "clean" else "full"
        row(
            "temple", "Temple of Artemis", "description", "bottom-left", visibility=clip
        )
        row(
            "culture",
            "Culture",
            "description",
            "bottom-left",
            "+1 " + tr("Culture"),
            clip,
        )
        food_key = "[relativeAmount]% [stat] [cityFilter]"
        food = (
            tr(food_key)
            .replace("[relativeAmount]", "+10")
            .replace("[stat]", tr("Food"))
            .replace("[cityFilter]", tr("in all cities"))
        )
        row(
            "food",
            food_key,
            "description",
            "bottom",
            food,
            clip,
            ("Food", "in all cities"),
        )
        production_key = "[relativeAmount]% Production when constructing [baseUnitFilter] units [cityFilter]"
        production = (
            tr(production_key)
            .replace("[relativeAmount]", "+15")
            .replace("[baseUnitFilter]", tr("Archery"))
            .replace("[cityFilter]", tr("in this city"))
        )
        visible_production = (
            "+15% Produktion beim Bau von" if lang == "German" else production
        )
        row(
            "production",
            production_key,
            "description",
            "bottom",
            visible_production,
            clip
            if clip != "full"
            else "visible_prefix"
            if lang == "German"
            else "full",
            ("Archery", "in this city"),
        )
        rows[-1]["assembled_full_text"] = production
        screens.append(
            {
                "image": "docs/evidence/8/final/" + filename,
                "sha256": capture["sha256"],
                "build": kind,
                "language": lang,
                "rows": rows,
                "numeric_diagnostics": ["6", "10", "19", "5", "7", "+1", "+10%", "+15%"]
                + (["(0/24)"] if kind == "clean" else []),
                "notes": [
                    "Icons and bullet glyphs are not translated text; numeric diagnostics are outside the primary denominator.",
                    "Vertical clipping is diagnostic only, not an unreadable-text omission or a defect label.",
                    "Only the visible production prefix is scored in German; hidden continuation is not a reference string.",
                ]
                + (
                    [
                        "Close/research buttons are absent from this injected screenshot, unlike the clean screenshots."
                    ]
                    if kind == "defective"
                    else []
                ),
            }
        )
    return {
        "status": "candidate_awaiting_Anton_confirmation",
        "detector_output_used": False,
        "method": "Manually selected build-specific translation entries; visible spans inspected from original screenshots. Not ground truth until Anton confirms.",
        "builds": builds,
        "screens": screens,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unciv-source", type=Path, required=True)
    parser.add_argument("--apk-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = prepare(args.unciv_source, args.apk_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for screen in reference["screens"]:
        print(
            screen["image"],
            "primary strings:",
            sum(r["primary_denominator"] for r in screen["rows"]),
        )


if __name__ == "__main__":
    main()
