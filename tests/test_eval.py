"""Unit tests for Stage 6 dataset evaluation (`l10n-eval`)."""

import io
import json
import subprocess
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from PIL import Image

from l10n_checker import eval_cli, evaluation
from l10n_checker.baseline import TSV_HEADER, BaselineError, OcrOutput
from l10n_checker.capture import CaptureError
from l10n_checker.deepseek import DeepSeekProvider
from l10n_checker.text_dump import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]
HEADER = "\t".join(TSV_HEADER) + "\n"
DEV_BUILD_REQUESTS = ROOT / "fixtures/stage3/dev-build-requests.json"
EXPECTED_DEV_BUILD_REQUESTS_SHA256 = (
    "36cf23d92bba9a059284dbdd7dfe7ccc90ba95b52b3b9bae0c9997308d289b94"
)


def make_png(size: tuple[int, int] = (2400, 1080)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(30, 40, 50)).save(buf, format="PNG")
    return buf.getvalue()


def make_tsv(words: list[tuple[str, int, int, int, int]]) -> str:
    rows = [
        f"5\t1\t1\t1\t{i + 1}\t1\t{left}\t{top}\t{w}\t{h}\t90\t{text}\n"
        for i, (text, left, top, w, h) in enumerate(words)
    ]
    return HEADER + "".join(rows)


class MapOcrEngine:
    preprocessing = "upscale2x-otsu"

    def __init__(self, responses: dict[str, OcrOutput | Exception]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def recognize(self, image: Path, language: str) -> OcrOutput:
        self.calls.append((image.name, language))
        item = self.responses[image.name]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def synthetic_env(tmp_path: Path):
    """Create a self-contained external dataset, git fork, inventory, and references."""
    fork = tmp_path / "unciv-fork"
    fork.mkdir()
    subprocess.run(["git", "init", str(fork)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(fork), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(fork), "config", "user.name", "Test"],
        check=True,
    )
    trans_dir = fork / "android/assets/jsons/translations"
    trans_dir.mkdir(parents=True)
    (trans_dir / "English.properties").write_text(
        "Mining = Mining\nWriting = Writing\nArchery = Archery\n",
        encoding="utf-8",
    )
    (trans_dir / "German.properties").write_text(
        "Mining = Bergbau\nWriting = Schrift\nArchery = Bogenschießen\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(fork), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(fork), "commit", "-m", "base"],
        check=True,
        capture_output=True,
    )
    base_commit = subprocess.run(
        ["git", "-C", str(fork), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    clean_patches: list[dict] = []
    clean_sha = evaluation.sha256_bytes(canonical_bytes(clean_patches))
    clean_batch_id = f"batch-{clean_sha[:16]}"

    mut_patches = [
        {
            "file": "android/assets/jsons/translations/German.properties",
            "operation": "replace",
            "key": "Mining",
            "original": "Bergbau",
            "replacement": "Bergbau und Erzgewinnung",
        },
        {
            "file": "android/assets/jsons/translations/German.properties",
            "operation": "remove",
            "key": "Archery",
            "original": "Bogenschießen",
            "replacement": None,
        },
    ]
    mut_sha = evaluation.sha256_bytes(canonical_bytes(mut_patches))
    mut_batch_id = f"batch-{mut_sha[:16]}"

    build_requests_path = tmp_path / "build-requests.json"
    evaluation.write_json(
        build_requests_path,
        {
            "requests_version": 1,
            "source_commit": base_commit,
            "requests": [
                {
                    "id": clean_batch_id,
                    "patch_set_sha256": clean_sha,
                    "patches": clean_patches,
                    "role": "clean",
                    "calibration": False,
                },
                {
                    "id": mut_batch_id,
                    "patch_set_sha256": mut_sha,
                    "patches": mut_patches,
                    "role": "mutation",
                    "calibration": False,
                },
            ],
        },
    )

    inventories_dir = tmp_path / "inventories"
    inventories_dir.mkdir()
    evaluation.write_json(
        inventories_dir / "tech-picker.json",
        {
            "schema_version": 1,
            "screen": "tech-picker",
            "base_commit": base_commit,
            "context": "synthetic test inventory",
            "slots": [
                {
                    "id": "slot-mining",
                    "request": "Mining",
                    "box": [0.0, 0.0, 0.3, 0.3],
                    "source": "TechButton",
                },
                {
                    "id": "slot-writing",
                    "request": "Writing",
                    "box": [0.35, 0.0, 0.65, 0.3],
                    "source": "TechButton",
                },
                {
                    "id": "slot-archery",
                    "request": "Archery",
                    "box": [0.7, 0.7, 1.0, 1.0],
                    "source": "TechButton",
                },
            ],
        },
    )

    references_dir = tmp_path / "references"
    ref_de = references_dir / "tech-picker__de"
    ref_de.mkdir(parents=True)
    # Note: "Schrift" is omitted from #47 reference to verify Change 2 union
    # with rendered inventory slots.
    evaluation.write_json(
        ref_de / "reference.json",
        {
            "status": "confirmed",
            "screen": "tech-picker",
            "language": "German",
            "screen_texts": ["Bergbau", "Bogenschießen"],
        },
    )

    dataset_dir = tmp_path / "external-dataset"
    dataset_dir.mkdir()
    png_bytes = make_png((2400, 1080))

    clean_name = f"tech-picker__de__2400x1080__{clean_batch_id}__1001.png"
    (dataset_dir / clean_name).write_bytes(png_bytes)
    evaluation.write_json(
        dataset_dir / f"tech-picker__de__2400x1080__{clean_batch_id}__1001.labels.json",
        {
            "schema_version": 2,
            "screenshot": clean_name,
            "language": "de",
            "labels": [],
        },
    )

    mut_name = f"tech-picker__de__2400x1080__{mut_batch_id}__1002.png"
    (dataset_dir / mut_name).write_bytes(png_bytes)
    evaluation.write_json(
        dataset_dir / f"tech-picker__de__2400x1080__{mut_batch_id}__1002.labels.json",
        {
            "schema_version": 2,
            "screenshot": mut_name,
            "language": "de",
            "labels": [
                {
                    "defect_type": "truncated_text",
                    "text_expected": "Bergbau und Erzgewinnung",
                    "text_seen": "Bergbau und Erzgew...",
                    "region": "top-left",
                },
                {
                    "defect_type": "wrong_language",
                    "text_expected": "Bogenschießen",
                    "text_seen": "Archery",
                    "region": "bottom-right",
                },
            ],
        },
    )

    return {
        "fork": fork,
        "base_commit": base_commit,
        "build_requests": build_requests_path,
        "inventories_dir": inventories_dir,
        "references_dir": references_dir,
        "dataset_dir": dataset_dir,
        "clean_name": clean_name,
        "mut_name": mut_name,
        "clean_batch_id": clean_batch_id,
        "mut_batch_id": mut_batch_id,
    }


def test_committed_dev_build_requests_authenticates():
    raw = DEV_BUILD_REQUESTS.read_bytes()
    assert evaluation.sha256_bytes(raw) == EXPECTED_DEV_BUILD_REQUESTS_SHA256
    doc = json.loads(raw.decode("utf-8"))
    assert doc["requests_version"] == 1
    assert doc["source_commit"] == "b534a8ae67c390412984869c7a03b168d532c36c"
    ids = {r["id"] for r in doc["requests"]}
    assert {
        "batch-37517e5f3dc66819",
        "batch-99984bb52ea65c2f",
        "batch-e45e29bd1f0f9039",
        "batch-e46946a0afe9ec07",
    } <= ids


def test_baseline_evaluation_metrics_and_default_outputs(synthetic_env, tmp_path: Path):
    clean_name = synthetic_env["clean_name"]
    mut_name = synthetic_env["mut_name"]
    # Clean image: reads "Bergbau" (exact), misses "Schrift" (missing FP) and
    # reads prefix "Bogenschi" on Archery (observed prefix FP).
    clean_tsv = make_tsv(
        [
            ("Bergbau", 100, 100, 200, 40),
            ("Bogenschi", 1800, 800, 200, 40),
        ]
    )
    # Mutated image: reads "Bergbau und Erzgew..." (observed prefix TP),
    # reads "Schrift" (exact), misses "Archery" (missing-rule TP via text_expected!).
    mut_tsv = make_tsv(
        [
            ("Bergbau und Erzgew...", 100, 100, 300, 40),
            ("Schrift", 950, 100, 200, 40),
        ]
    )
    engine = MapOcrEngine(
        {
            clean_name: OcrOutput(clean_tsv, {"engine": "fake-tesseract"}),
            mut_name: OcrOutput(mut_tsv, {"engine": "fake-tesseract"}),
        }
    )

    out_dir = tmp_path / "data/runs/unit-baseline-1"
    run_record, per_image = evaluation.evaluate_dataset(
        dataset_dir=synthetic_env["dataset_dir"],
        detector="baseline",
        output_dir=out_dir,
        command=["l10n-eval", "--dataset", str(synthetic_env["dataset_dir"])],
        build_requests_path=synthetic_env["build_requests"],
        unciv_fork=synthetic_env["fork"],
        inventories_dir=synthetic_env["inventories_dir"],
        references_dir=synthetic_env["references_dir"],
        ocr_engine=engine,
        keep_records=False,
    )

    # Change 4: only run.json and per_image.json by default.
    assert sorted(p.name for p in out_dir.iterdir()) == ["per_image.json", "run.json"]
    assert run_record["run_id"] == "unit-baseline-1"
    assert run_record["detector"] == "baseline"
    assert run_record["seed"] is None
    assert run_record["requests_sent"] == 0
    assert run_record["token_usage"] == {}
    assert run_record["estimated_cost_usd"] == "0"

    metrics = run_record["metrics"]
    assert metrics["tp"] == 2
    assert metrics["tp_observed"] == 1
    assert metrics["tp_missing"] == 1
    assert metrics["fp"] == 2
    assert metrics["fp_observed"] == 1
    assert metrics["fp_missing"] == 1
    assert metrics["fn"] == 0
    assert metrics["not_checked_screens"] == 0
    assert metrics["fn_on_not_checked"] == 0
    assert metrics["empty_label_images"] == 1
    assert metrics["empty_label_fp"] == 2
    assert metrics["empty_label_fp_observed"] == 1
    assert metrics["empty_label_fp_missing"] == 1
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall_all"] == pytest.approx(1.0)
    assert metrics["recall_checked"] == pytest.approx(1.0)
    # Change 2: "Schrift" is in inventory rendered texts, so the missing-rule
    # finding for "Schrift" on the clean screen is NOT a hallucination!
    # "Bogenschi" is a partial word not in screen_texts, so 1 hallucination.
    assert metrics["hallucinations"] == 1
    assert metrics["per_class_recall"]["truncated_text"] == {
        "matched": 1,
        "exact_type": 1,
        "total": 1,
        "recall": 1.0,
    }
    assert metrics["per_class_recall"]["wrong_language"] == {
        "matched": 1,
        "exact_type": 0,
        "total": 1,
        "recall": 1.0,
    }
    assert metrics["per_class_recall"]["overflow"]["recall"] is None
    assert len(per_image) == 2


def test_baseline_failure_is_not_checked_and_keep_records_writes_folders(
    synthetic_env, tmp_path: Path
):
    clean_name = synthetic_env["clean_name"]
    mut_name = synthetic_env["mut_name"]
    clean_tsv = make_tsv(
        [
            ("Bergbau", 100, 100, 200, 40),
            ("Schrift", 950, 100, 200, 40),
            ("Bogenschießen", 1800, 800, 200, 40),
        ]
    )
    engine = MapOcrEngine(
        {
            clean_name: OcrOutput(clean_tsv, {"engine": "fake-tesseract"}),
            mut_name: BaselineError("OCR subprocess timed out"),
        }
    )

    out_dir = tmp_path / "data/runs/unit-baseline-keep"
    run_record, per_image = evaluation.evaluate_dataset(
        dataset_dir=synthetic_env["dataset_dir"],
        detector="baseline",
        output_dir=out_dir,
        command=["l10n-eval", "--keep-records"],
        build_requests_path=synthetic_env["build_requests"],
        unciv_fork=synthetic_env["fork"],
        inventories_dir=synthetic_env["inventories_dir"],
        references_dir=synthetic_env["references_dir"],
        ocr_engine=engine,
        keep_records=True,
    )

    assert (out_dir / "records").is_dir()
    assert (out_dir / "records" / Path(clean_name).stem / "ocr.tsv").is_file()
    assert (out_dir / "records" / Path(mut_name).stem / "result.json").is_file()

    metrics = run_record["metrics"]
    assert metrics["not_checked_screens"] == 1
    assert metrics["fn_on_not_checked"] == 2
    assert metrics["tp"] == 0
    assert metrics["fp"] == 0
    assert metrics["fn"] == 0
    assert metrics["recall_checked"] is None
    assert metrics["recall_all"] == 0.0
    mut_row = next(r for r in per_image if r["image"] == mut_name)
    assert mut_row["status"] == "not_checked"
    assert "BaselineError: OCR subprocess timed out" in mut_row["reason"]


def _mock_deepseek_provider(outcomes: list, sent_requests: list):
    def handler(request: httpx.Request) -> httpx.Response:
        sent_requests.append(json.loads(request.content))
        outcome = outcomes.pop(0)
        if isinstance(outcome, int):
            return httpx.Response(outcome, text=f"HTTP {outcome} failure")
        if isinstance(outcome, str):
            body = outcome
        else:
            body = json.dumps(outcome)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "system_fingerprint": "fp_unit_test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": body},
                    }
                ],
                "usage": {
                    "prompt_tokens": 1800,
                    "completion_tokens": 50,
                    "total_tokens": 1850,
                    "prompt_cache_hit_tokens": 1600,
                    "prompt_cache_miss_tokens": 200,
                },
            },
        )

    return DeepSeekProvider(
        "secret-api-key-123",
        transport=httpx.MockTransport(handler),
    )


def test_vision_evaluation_scores_and_handles_invalid_response_as_not_checked(
    synthetic_env, tmp_path: Path
):
    sent: list = []
    outcomes = [
        # Clean screen: readable, 1 FP finding on "Schrift"
        {
            "readability": "readable",
            "unreadable_regions": [],
            "readability_reason": None,
            "findings": [
                {
                    "defect_type": "truncated_text",
                    "text_seen": "Schrift",
                    "region": "top",
                    "confidence": 0.7,
                }
            ],
        },
        # Mutated screen: invalid schema response -> not_checked (D-013)
        '{"not_a_valid_schema": true}',
    ]
    provider = _mock_deepseek_provider(outcomes, sent)
    out_dir = tmp_path / "data/runs/unit-vision-1"
    run_record, per_image = evaluation.evaluate_dataset(
        dataset_dir=synthetic_env["dataset_dir"],
        detector="vision",
        output_dir=out_dir,
        command=["l10n-eval", "--key", "secret-api-key-123"],
        build_requests_path=synthetic_env["build_requests"],
        unciv_fork=synthetic_env["fork"],
        inventories_dir=synthetic_env["inventories_dir"],
        references_dir=synthetic_env["references_dir"],
        provider=provider,
        max_requests=5,
        max_usd=Decimal("1.00"),
        secrets=("secret-api-key-123",),
        retry_delay_s=0.0,
    )

    assert len(sent) == 2
    assert "[REDACTED]" in run_record["command"]
    assert "secret-api-key-123" not in (out_dir / "run.json").read_text(
        encoding="utf-8"
    )
    assert run_record["requests_sent"] == 2
    assert run_record["token_usage"]["total_tokens"] == 3700
    assert Decimal(run_record["estimated_cost"]["peak_usd"]) > 0

    metrics = run_record["metrics"]
    assert metrics["tp"] == 0
    assert metrics["fp"] == 1
    assert metrics["empty_label_fp"] == 1
    # "Schrift" is in the rendered baseline inventory union (Change 2), so not a hallucination.
    assert metrics["hallucinations"] == 0
    assert metrics["not_checked_screens"] == 1
    assert metrics["fn_on_not_checked"] == 2
    assert per_image[1]["status"] == "not_checked"
    assert per_image[1]["reason"].startswith("invalid_response:")


def test_vision_budget_enforces_max_requests_and_worst_case_usd_reserve(
    synthetic_env, tmp_path: Path
):
    # 1. Request cap of 1 stops before second image.
    sent_req_cap: list = []
    provider_req = _mock_deepseek_provider(
        [
            {
                "readability": "readable",
                "unreadable_regions": [],
                "readability_reason": None,
                "findings": [],
            }
        ],
        sent_req_cap,
    )
    out_req = tmp_path / "data/runs/unit-vision-req-cap"
    run_req, rows_req = evaluation.evaluate_dataset(
        dataset_dir=synthetic_env["dataset_dir"],
        detector="vision",
        output_dir=out_req,
        command=["l10n-eval"],
        build_requests_path=synthetic_env["build_requests"],
        unciv_fork=synthetic_env["fork"],
        inventories_dir=synthetic_env["inventories_dir"],
        references_dir=synthetic_env["references_dir"],
        provider=provider_req,
        max_requests=1,
        max_usd=Decimal("1.00"),
        retry_delay_s=0.0,
    )
    assert len(sent_req_cap) == 1
    assert run_req["requests_sent"] == 1
    assert rows_req[0]["status"] == "checked"
    assert rows_req[1]["status"] == "not_checked"
    assert rows_req[1]["requests_sent"] == 0
    assert rows_req[1]["reason"].startswith("request_cap_reached:")

    # 2. USD cap: worst-case reserve is 0.319488 USD. With max_usd=0.35 and an
    # HTTP 500 failure on image 1 (no usage returned), the full 0.319488 USD
    # unknown-cost reserve is retained, blocking image 2.
    sent_usd_cap: list = []
    provider_usd = _mock_deepseek_provider([500], sent_usd_cap)
    out_usd = tmp_path / "data/runs/unit-vision-usd-cap"
    run_usd, rows_usd = evaluation.evaluate_dataset(
        dataset_dir=synthetic_env["dataset_dir"],
        detector="vision",
        output_dir=out_usd,
        command=["l10n-eval"],
        build_requests_path=synthetic_env["build_requests"],
        unciv_fork=synthetic_env["fork"],
        inventories_dir=synthetic_env["inventories_dir"],
        references_dir=synthetic_env["references_dir"],
        provider=provider_usd,
        max_requests=5,
        max_usd=Decimal("0.35"),
        retry_delay_s=0.0,
    )
    assert len(sent_usd_cap) == 1
    assert run_usd["requests_sent"] == 1
    assert run_usd["estimated_cost"]["unknown_cost_reserve_usd"] == "0.319488"
    assert rows_usd[0]["status"] == "not_checked"
    assert rows_usd[0]["reason"].startswith("api_error:")
    assert rows_usd[1]["status"] == "not_checked"
    assert rows_usd[1]["requests_sent"] == 0
    assert rows_usd[1]["reason"].startswith("usd_cap_reached:")


def test_cli_validation_and_output_directory_guard(
    synthetic_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/runs").mkdir(parents=True)

    # Vision requires --max-requests and --max-usd.
    with pytest.raises(SystemExit) as exc:
        eval_cli.main(
            [
                "--dataset",
                str(synthetic_env["dataset_dir"]),
                "--detector",
                "vision",
                "--output-dir",
                "data/runs/v-missing-caps",
            ]
        )
    assert exc.value.code == 2

    # Baseline rejects --max-requests / --max-usd.
    with pytest.raises(SystemExit) as exc:
        eval_cli.main(
            [
                "--dataset",
                str(synthetic_env["dataset_dir"]),
                "--detector",
                "baseline",
                "--output-dir",
                "data/runs/b-with-caps",
                "--max-requests",
                "1",
            ]
        )
    assert exc.value.code == 2

    # Output folder outside data/ is rejected with exit code 1.
    code = eval_cli.main(
        [
            "--dataset",
            str(synthetic_env["dataset_dir"]),
            "--detector",
            "baseline",
            "--output-dir",
            str(tmp_path / "outside-data"),
            "--build-requests",
            str(synthetic_env["build_requests"]),
            "--unciv-fork",
            str(synthetic_env["fork"]),
            "--inventories-dir",
            str(synthetic_env["inventories_dir"]),
            "--references-dir",
            str(synthetic_env["references_dir"]),
        ]
    )
    assert code == 1
    assert not (tmp_path / "outside-data").exists()

    # Existing output folder is refused.
    existing = tmp_path / "data/runs/already-there"
    existing.mkdir()
    with pytest.raises(CaptureError):
        evaluation.evaluate_dataset(
            dataset_dir=synthetic_env["dataset_dir"],
            detector="baseline",
            output_dir=existing,
            command=["l10n-eval"],
            build_requests_path=synthetic_env["build_requests"],
            unciv_fork=synthetic_env["fork"],
            inventories_dir=synthetic_env["inventories_dir"],
            references_dir=synthetic_env["references_dir"],
        )


def test_cli_end_to_end_exit_codes_and_preflight_before_provider(
    synthetic_env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data/runs").mkdir(parents=True)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    clean_name = synthetic_env["clean_name"]
    mut_name = synthetic_env["mut_name"]
    tsv_ok = make_tsv(
        [
            ("Bergbau", 100, 100, 200, 40),
            ("Schrift", 950, 100, 200, 40),
            ("Bogenschießen", 1800, 800, 200, 40),
        ]
    )
    fake_engine = MapOcrEngine(
        {
            clean_name: OcrOutput(tsv_ok, {"engine": "fake"}),
            mut_name: OcrOutput(tsv_ok, {"engine": "fake"}),
        }
    )
    monkeypatch.setattr(evaluation, "Tesseract", lambda **_: fake_engine)

    code_ok = eval_cli.main(
        [
            "--dataset",
            str(synthetic_env["dataset_dir"]),
            "--detector",
            "baseline",
            "--output-dir",
            "data/runs/cli-baseline-ok",
            "--build-requests",
            str(synthetic_env["build_requests"]),
            "--unciv-fork",
            str(synthetic_env["fork"]),
            "--inventories-dir",
            str(synthetic_env["inventories_dir"]),
            "--references-dir",
            str(synthetic_env["references_dir"]),
        ]
    )
    assert code_ok == 0
    assert (tmp_path / "data/runs/cli-baseline-ok/run.json").is_file()
    assert (tmp_path / "data/runs/cli-baseline-ok/per_image.json").is_file()

    # Preflight failure on vision must not initialize the provider.
    called = []
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        eval_cli,
        "make_provider",
        lambda *_: called.append(True) or None,
    )
    bad_dataset = tmp_path / "empty-dataset"
    bad_dataset.mkdir()
    code_err = eval_cli.main(
        [
            "--dataset",
            str(bad_dataset),
            "--detector",
            "vision",
            "--output-dir",
            "data/runs/cli-vision-preflight-fail",
            "--max-requests",
            "2",
            "--max-usd",
            "1.00",
        ]
    )
    assert code_err == 1
    assert called == []


def test_screen_texts_union_preserves_unique_text_region_invariance(synthetic_env):
    _, batch_sources, _ = evaluation.load_build_tables(
        synthetic_env["build_requests"],
        synthetic_env["fork"],
    )
    inv, _ = evaluation.load_screen_inventory(
        synthetic_env["inventories_dir"],
        "tech-picker",
        synthetic_env["base_commit"],
    )
    tables = evaluation.parse_batch_tables(
        batch_sources, synthetic_env["clean_batch_id"]
    )
    # "Bergbau" is in both reference_texts and inventory slots; it must remain
    # a single occurrence in screen_texts so unique-text region invariance holds.
    st = evaluation.build_screen_texts(
        ["Bergbau", "Bogenschießen"],
        inv,
        tables,
        "de",
        [],
    )
    assert st.count("Bergbau") == 1
    assert "Schrift" in st
