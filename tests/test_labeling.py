"""Unit tests for Stage 3 label drafting, review page, and confirmed writer (D-062)."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from l10n_checker.label_cli import main as label_cli_main
from l10n_checker.label_page import render_page
from l10n_checker.labeling import (
    build_drafts,
    draft_label_from_occurrence,
    draft_run,
    region_from_bounds,
    write_labels,
)
from l10n_checker.matching import load_labels


def _make_png(path: Path, size: tuple[int, int] = (2400, 1080)) -> None:
    buf = io.BytesIO()
    Image.new("RGBA", size, (20, 30, 40, 255)).save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


def _occurrence(
    *,
    intended_class: str,
    before_display: str,
    after_display: str,
    expected_input: str | None = None,
    before_warnings: list[str] | None = None,
    after_warnings: list[str] | None = None,
    glyph_bounds: list[float] | None = None,
    owner_bounds: list[float] | None = None,
    qualified: bool = True,
    recipe_id: str = "test-recipe",
) -> dict:
    gb = glyph_bounds or [1000.0, 450.0, 1400.0, 630.0]
    ob = owner_bounds if owner_bounds is not None else gb
    return {
        "recipe_id": recipe_id,
        "intended_class": intended_class,
        "actor_path": "root/0:Table/0:Label",
        "qualified": qualified,
        "expected_input_text": expected_input
        if expected_input is not None
        else after_display,
        "before": {
            "display_text": before_display,
            "input_text": before_display,
            "warnings": before_warnings or [],
            "bounds": ob,
            "glyph_bounds": gb,
        },
        "after": {
            "display_text": after_display,
            "input_text": expected_input
            if expected_input is not None
            else after_display,
            "warnings": after_warnings or [],
            "bounds": ob,
            "glyph_bounds": gb,
        },
    }


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [
        ([0, 0, 100, 100], "top-left"),
        ([1000, 50, 1400, 150], "top"),
        ([2000, 50, 2300, 150], "top-right"),
        ([100, 450, 500, 600], "left"),
        ([1000, 450, 1400, 600], "center"),
        ([1800, 450, 2200, 600], "right"),
        ([100, 800, 500, 1000], "bottom-left"),
        ([1000, 800, 1400, 1000], "bottom"),
        ([1800, 800, 2300, 1000], "bottom-right"),
        # Spans left and center columns; centre x = 850 > 800 -> center (D-025).
        ([700, 400, 1000, 600], "center"),
        # Spans left and center columns; centre x = 750 < 800 -> left (D-025).
        ([600, 400, 900, 600], "left"),
        # Out-of-frame edges clamp to outer cells.
        ([-200, -100, -10, -10], "top-left"),
        ([2450, 1100, 2600, 1200], "bottom-right"),
    ],
)
def test_region_from_bounds_2400x1080(bounds, expected):
    assert region_from_bounds(bounds, (2400, 1080)) == expected


def test_region_from_bounds_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="Reversed"):
        region_from_bounds([500, 100, 400, 200])
    with pytest.raises(ValueError, match="Invalid bounds"):
        region_from_bounds([1, 2, 3])
    with pytest.raises(ValueError, match="Invalid image size"):
        region_from_bounds([0, 0, 10, 10], (0, 1080))


def test_draft_mapping_overflow():
    occ = _occurrence(
        intended_class="overflow",
        before_display="+",
        after_display="Increase",
        glyph_bounds=[1531.0, 921.0, 1655.0, 965.0],
        owner_bounds=[1579.0, 935.0, 1607.0, 962.0],
        recipe_id="slider-increase-overflow-en",
    )
    draft = draft_label_from_occurrence(occ)
    assert draft["defect_type"] == "overflow"
    assert draft["text_seen"] == "Increase"
    assert draft["text_expected"] == "Increase"
    assert draft["note"] == ""
    assert draft["region"] == "bottom"
    assert draft["confirmed"] is False
    assert draft["glyph_bounds"] == [1531.0, 921.0, 1655.0, 965.0]
    assert draft["owner_bounds"] == [1579.0, 935.0, 1607.0, 962.0]


def test_draft_mapping_truncated_text_strips_color_markup():
    occ = _occurrence(
        intended_class="truncated_text",
        before_display="Bergbau",
        after_display="Bergbau und Erzgew...",
        expected_input="[RED]Bergbau und Erzgewinnung[]",
        glyph_bounds=[111.0, 686.0, 361.0, 720.0],
        recipe_id="mining-truncation-de",
    )
    draft = draft_label_from_occurrence(occ)
    assert draft["defect_type"] == "truncated_text"
    assert draft["text_seen"] == "Bergbau und Erzgew..."
    assert draft["text_expected"] == "Bergbau und Erzgewinnung"
    assert draft["note"] == ""
    assert draft["region"] == "left"


def test_draft_mapping_wrong_language_strips_engine_icons():
    occ = _occurrence(
        intended_class="wrong_language",
        before_display="Worker\n31⚙ 8⏳",
        after_display="Arbeiter\n31⚙ 8⏳",
        before_warnings=["icon_glyph:2699", "icon_glyph:23f3"],
        after_warnings=["icon_glyph:2699", "icon_glyph:23f3"],
        glyph_bounds=[2050.0, 950.0, 2350.0, 1030.0],
        recipe_id="worker-foreign-en",
    )
    draft = draft_label_from_occurrence(occ)
    assert draft["defect_type"] == "wrong_language"
    assert draft["text_seen"] == "Arbeiter\n31 8"
    assert draft["text_expected"] == "Worker\n31 8"
    assert draft["note"] == ""
    assert draft["region"] == "bottom-right"


def test_draft_mapping_other_preserves_literal_placeholder_and_sets_note():
    occ = _occurrence(
        intended_class="other",
        before_display="Research \ue1aeArchery\n(0/24)",
        after_display="Research [amount]\n(0/24)",
        expected_input="Research [amount]\n(0/24)",
        before_warnings=["icon_glyph:e1ae"],
        after_warnings=["markup_input"],
        glyph_bounds=[2088.0, 956.0, 2359.0, 1031.0],
        recipe_id="research-placeholder-en",
    )
    draft = draft_label_from_occurrence(occ)
    assert draft["defect_type"] == "other"
    assert draft["text_seen"] == "Research [amount]\n(0/24)"
    assert draft["text_expected"] == "Research Archery\n(0/24)"
    assert draft["note"] == "broken placeholder"
    assert draft["region"] == "bottom-right"


def test_draft_label_rejects_unqualified_occurrence():
    occ = _occurrence(
        intended_class="wrong_language",
        before_display="Mining",
        after_display="Bergbau",
        qualified=False,
    )
    with pytest.raises(ValueError, match="unqualified"):
        draft_label_from_occurrence(occ)


def _setup_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mut_png = "tech-picker__de__2400x1080__batch-aaa__1001.png"
    clean_png = "tech-picker__de__2400x1080__batch-clean__1000.png"
    rejected_png = "options-gameplay__en__2400x1080__batch-bbb__1002.png"
    for name in (mut_png, clean_png, rejected_png):
        _make_png(run_dir / name)

    acceptance = {
        "run_id": "test-run",
        "commit": "abc1234",
        "decisions": [
            {
                "png": mut_png,
                "role": "mutation",
                "screen": "tech-picker",
                "language": "de",
                "batch": "batch-aaa",
                "status": "accepted",
            },
            {
                "png": clean_png,
                "role": "clean",
                "screen": "tech-picker",
                "language": "de",
                "batch": "batch-clean",
                "status": "accepted",
            },
            {
                "png": rejected_png,
                "role": "mutation",
                "screen": "options-gameplay",
                "language": "en",
                "batch": "batch-bbb",
                "status": "rejected",
            },
        ],
    }
    manifest = {
        "status": "completed",
        "screenshots": [
            {
                "batch_id": "batch-aaa",
                "role": "mutation",
                "screen": "tech-picker",
                "language": "de",
                "png": mut_png,
                "review_flags": [
                    {"actor_path": "root/Desc", "before": [], "after": []}
                ],
                "verification": {
                    "qualified": True,
                    "occurrences": [
                        _occurrence(
                            intended_class="truncated_text",
                            before_display="Bergbau",
                            after_display="Bergbau und Erzgew...",
                            expected_input="Bergbau und Erzgewinnung",
                            glyph_bounds=[111.0, 686.0, 361.0, 720.0],
                        ),
                        _occurrence(
                            intended_class="wrong_language",
                            before_display="Mauerarbeiten",
                            after_display="Masonry",
                            qualified=False,
                        ),
                    ],
                },
            },
            {
                "batch_id": "batch-clean",
                "role": "clean",
                "screen": "tech-picker",
                "language": "de",
                "png": clean_png,
            },
            {
                "batch_id": "batch-bbb",
                "role": "mutation",
                "screen": "options-gameplay",
                "language": "en",
                "png": rejected_png,
                "review_flags": [],
                "verification": {"qualified": True, "occurrences": []},
            },
        ],
    }
    (run_dir / "acceptance.json").write_text(json.dumps(acceptance), encoding="utf-8")
    (run_dir / "mutation-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {"run_id": "test-run", "commit": "abc1234", "builder_commit": "def"}
        ),
        encoding="utf-8",
    )
    return run_dir


def test_build_drafts_and_self_contained_html(tmp_path):
    run_dir = _setup_run_dir(tmp_path)
    payload = build_drafts(run_dir)
    assert payload["run_id"] == "test-run"
    assert len(payload["screenshots"]) == 2
    mut, clean = payload["screenshots"]
    assert mut["role"] == "mutation"
    assert len(mut["labels"]) == 1  # unqualified occurrence skipped
    assert mut["labels"][0]["defect_type"] == "truncated_text"
    assert len(mut["review_flags"]) == 1
    assert clean["role"] == "clean"
    assert clean["labels"] == []

    html_path = draft_run(run_dir)
    assert html_path == run_dir / "label-review.html"
    assert not (run_dir / "drafts").exists()
    content = html_path.read_text(encoding="utf-8")
    assert "INITIAL_DRAFTS" in content
    assert "Bergbau und Erzgew..." in content
    assert "root/Desc" in content
    assert "http://" not in content.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in content

    # Escaping closing script tags in inline JSON stays safe.
    rendered = render_page(
        {
            "run_id": "r1",
            "screenshots": [
                {
                    "png": "a.png",
                    "screen": "tech-picker",
                    "language": "en",
                    "role": "clean",
                    "image_size": [2400, 1080],
                    "review_flags": [],
                    "labels": [{"text_seen": "</script>"}],
                }
            ],
        }
    )
    assert "<\\/script>" in rendered


def test_build_drafts_refuses_holdout_screen(tmp_path):
    run_dir = tmp_path / "holdout-run"
    run_dir.mkdir()
    png = "world__en__2400x1080__batch-clean__1000.png"
    _make_png(run_dir / png)
    (run_dir / "acceptance.json").write_text(
        json.dumps(
            {
                "run_id": "bad",
                "decisions": [
                    {
                        "png": png,
                        "role": "clean",
                        "screen": "world",
                        "language": "en",
                        "status": "accepted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "mutation-manifest.json").write_text(
        json.dumps(
            {
                "screenshots": [
                    {
                        "batch_id": "batch-clean",
                        "role": "clean",
                        "screen": "world",
                        "language": "en",
                        "png": png,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Hold-out"):
        build_drafts(run_dir)


def _valid_export_dict() -> dict:
    return {
        "export_version": 1,
        "run_id": "test-run",
        "screenshots": [
            {
                "png": "tech-picker__de__2400x1080__batch-aaa__1001.png",
                "screen": "tech-picker",
                "language": "de",
                "role": "mutation",
                "reviewed": True,
                "labels": [
                    {
                        "defect_type": "truncated_text",
                        "text_expected": "Bergbau und Erzgewinnung",
                        "text_seen": "Bergbau und Erzgew...",
                        "region": "left",
                        "note": "",
                        "confirmed": True,
                        "source": "manifest",
                    },
                    {
                        "defect_type": "other",
                        "text_expected": "Bogenschießen erforschen\n(0/24)",
                        "text_seen": "[amount] erforschen\n(0/24)",
                        "region": "bottom-right",
                        "note": "broken placeholder",
                        "confirmed": True,
                        "source": "manifest",
                    },
                ],
            },
            {
                "png": "tech-picker__de__2400x1080__batch-clean__1000.png",
                "screen": "tech-picker",
                "language": "de",
                "role": "clean",
                "reviewed": True,
                "labels": [],
            },
        ],
    }


def test_write_labels_valid_export_passes_load_labels(tmp_path):
    run_dir = _setup_run_dir(tmp_path)
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(_valid_export_dict()), encoding="utf-8")
    out_dir = tmp_path / "dataset"

    written = write_labels(
        export_path,
        out_dir,
        acceptance_path=run_dir / "acceptance.json",
        copy_pngs_from=run_dir,
    )
    assert len(written) == 2

    mut_file = out_dir / "tech-picker__de__2400x1080__batch-aaa__1001.labels.json"
    clean_file = out_dir / "tech-picker__de__2400x1080__batch-clean__1000.labels.json"
    assert mut_file.is_file() and clean_file.is_file()
    assert (out_dir / "tech-picker__de__2400x1080__batch-aaa__1001.png").is_file()
    assert (out_dir / "tech-picker__de__2400x1080__batch-clean__1000.png").is_file()

    mut_doc = json.loads(mut_file.read_text(encoding="utf-8"))
    version, labels = load_labels(mut_doc)
    assert version == 2
    assert len(labels) == 2
    assert "note" not in mut_doc["labels"][0]
    assert mut_doc["labels"][1]["note"] == "broken placeholder"
    assert labels[1].text_seen == "[amount] erforschen\n(0/24)"

    clean_doc = json.loads(clean_file.read_text(encoding="utf-8"))
    clean_version, clean_labels = load_labels(clean_doc)
    assert clean_version == 2
    assert clean_labels == []


def test_write_labels_refuses_unreviewed_screenshot_and_writes_nothing(tmp_path):
    export = _valid_export_dict()
    export["screenshots"][1]["reviewed"] = False
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(export), encoding="utf-8")
    out_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="unreviewed"):
        write_labels(export_path, out_dir)
    assert not out_dir.exists()


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda e: e["screenshots"][0]["labels"][0].update(confirmed=False),
            "not confirmed",
        ),
        (
            lambda e: e["screenshots"][0]["labels"][0].update(defect_type="overlap"),
            "invalid defect_type",
        ),
        (
            lambda e: e["screenshots"][0]["labels"][0].update(region="middle"),
            "invalid region",
        ),
        (
            lambda e: e["screenshots"][0]["labels"][0].update(text_seen="   "),
            "empty text_seen",
        ),
        (
            lambda e: e["screenshots"][0]["labels"][0].update(text_expected=""),
            "empty text_expected",
        ),
        (
            lambda e: e["screenshots"][0]["labels"][1].update(note="   "),
            "requires a note",
        ),
        (
            lambda e: e["screenshots"][0].update(language="en"),
            "Language mismatch",
        ),
        (
            lambda e: e["screenshots"][1].update(
                png="world__de__2400x1080__batch-clean__1000.png"
            ),
            "Hold-out",
        ),
    ],
)
def test_write_labels_refuses_invalid_labels(tmp_path, mutator, pattern):
    export = _valid_export_dict()
    mutator(export)
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(export), encoding="utf-8")
    out_dir = tmp_path / "out"

    with pytest.raises(ValueError, match=pattern):
        write_labels(export_path, out_dir)
    assert not out_dir.exists()


def test_write_labels_refuses_acceptance_mismatch(tmp_path):
    run_dir = _setup_run_dir(tmp_path)
    export = _valid_export_dict()
    export["screenshots"].pop()  # missing clean control
    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(export), encoding="utf-8")

    with pytest.raises(ValueError, match="acceptance.json"):
        write_labels(
            export_path,
            tmp_path / "out",
            acceptance_path=run_dir / "acceptance.json",
        )


def test_label_cli_draft_and_write(tmp_path):
    run_dir = _setup_run_dir(tmp_path)
    assert label_cli_main(["draft", "--run-dir", str(run_dir)]) == 0
    assert (run_dir / "label-review.html").is_file()

    export_path = tmp_path / "export.json"
    export_path.write_text(json.dumps(_valid_export_dict()), encoding="utf-8")
    out_dir = tmp_path / "written"
    assert (
        label_cli_main(
            [
                "write",
                "--export",
                str(export_path),
                "--output-dir",
                str(out_dir),
                "--acceptance",
                str(run_dir / "acceptance.json"),
            ]
        )
        == 0
    )
    assert len(list(out_dir.glob("*.labels.json"))) == 2

    # Unreviewed export exits non-zero.
    bad_export = _valid_export_dict()
    bad_export["screenshots"][0]["reviewed"] = False
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad_export), encoding="utf-8")
    assert (
        label_cli_main(
            ["write", "--export", str(bad_path), "--output-dir", str(out_dir)]
        )
        == 1
    )


def test_committed_dev_dataset_loads_cleanly():
    from l10n_checker.capture import REPO_ROOT

    dataset = REPO_ROOT / "datasets" / "dev"
    pngs = sorted(dataset.glob("*.png"))
    label_files = sorted(dataset.glob("*.labels.json"))
    assert len(pngs) == 34
    assert len(label_files) == 34
    assert {p.stem for p in pngs} == {
        lf.name.removesuffix(".labels.json") for lf in label_files
    }

    split = json.loads(
        (REPO_ROOT / "fixtures" / "stage2" / "split.json").read_text(encoding="utf-8")
    )
    holdout = set(split["holdout"])

    total_labels = 0
    for lf in label_files:
        screen = lf.name.split("__")[0]
        assert screen not in holdout
        doc = json.loads(lf.read_text(encoding="utf-8"))
        version, labels = load_labels(doc)
        assert version == 2
        assert doc["screenshot"] == f"{lf.name.removesuffix('.labels.json')}.png"
        total_labels += len(labels)
    assert total_labels == 33
