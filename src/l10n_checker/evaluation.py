"""Dataset evaluation for baseline and vision detectors (Stage 6, l10n-eval)."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from l10n_checker.baseline import (
    DEFAULT_PREPROCESSING,
    SETTINGS,
    TRANSLATIONS,
    BaselineError,
    Inventory,
    OcrEngine,
    Tesseract,
    detect,
    git_file,
    parse_tsv,
)
from l10n_checker.capture import LANGUAGES, REPO_ROOT, CaptureError, png_size
from l10n_checker.deepseek import MAX_TOKENS, TARIFF
from l10n_checker.deepseek import estimate_cost as deepseek_estimate_cost
from l10n_checker.matching import (
    DEFAULT_CONFIG,
    Label,
    MatchingConfig,
    load_labels,
    match_screen,
    normalize_text,
)
from l10n_checker.metrics import score_screen, score_screens
from l10n_checker.mutation_catalog import apply_patches
from l10n_checker.text_dump import canonical_bytes
from l10n_checker.unciv_text import RenderingError, TranslationTable
from l10n_checker.vision import (
    PROMPT_TEMPLATE,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    CheckResult,
    RequestBudget,
    VisionProvider,
    redact,
    result_schema_version,
    run_check,
    screenshot_language,
)

CLASSES = ("overflow", "wrong_language", "truncated_text", "other")
# Published 1M context limit for DeepSeek Flash (docs/evidence/45/budget-policy.json).
CONSERVATIVE_INPUT_TOKENS = 1_048_576
DEFAULT_BUILD_REQUESTS = REPO_ROOT / "fixtures/stage3/dev-build-requests.json"
DEFAULT_INVENTORIES_DIR = REPO_ROOT / "fixtures/baseline"
DEFAULT_REFERENCES_DIR = REPO_ROOT / "docs/evidence/47/reference-confirmation"
DEFAULT_UNCIV_FORK = (
    REPO_ROOT.parent / "Unciv-fork"
    if (REPO_ROOT.parent / "Unciv-fork").is_dir()
    else Path.home() / "PycharmProjects/Unciv-fork"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git_head_commit(repo: Path = REPO_ROOT) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        return out if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def _reasoning_tokens(usage: dict) -> int | None:
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict):
        val = details.get("reasoning_tokens")
        if type(val) is int and val >= 0:
            return val
    return None


def worst_case_request_reserve_usd(provider: VisionProvider) -> Decimal:
    """Per-request worst-case peak USD reserve (#45 budget policy)."""
    reserve_fn = getattr(provider, "worst_case_reserve_usd", None)
    if callable(reserve_fn):
        reserve = Decimal(str(reserve_fn()))
        if reserve <= 0:
            raise ValueError("Worst-case per-request USD reservation must be positive")
        return reserve
    max_tokens = provider.settings.get("max_tokens", MAX_TOKENS)
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError(f"Invalid provider max_tokens setting: {max_tokens!r}")
    worst_usage = {
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": CONSERVATIVE_INPUT_TOKENS,
        "completion_tokens": max_tokens,
    }
    estimate = provider.estimate_cost(worst_usage)
    if estimate is None:
        estimate = deepseek_estimate_cost(worst_usage)
    if not isinstance(estimate, dict) or "peak_usd" not in estimate:
        raise ValueError("Cannot determine worst-case per-request USD reservation")
    reserve = Decimal(str(estimate["peak_usd"]))
    if reserve <= 0:
        raise ValueError("Worst-case per-request USD reservation must be positive")
    return reserve


def load_build_tables(
    build_requests_path: Path,
    unciv_fork: Path,
) -> tuple[str, dict[str, dict], dict[str, dict]]:
    """Load and authenticate `--build-requests` patches against `--unciv-fork`."""
    raw = build_requests_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("requests_version") != 1:
        raise ValueError(f"Unsupported build-requests format in {build_requests_path}")
    source_commit = data.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("build-requests source_commit must be a 40-char commit SHA")
    requests = data.get("requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("build-requests must contain a non-empty 'requests' list")

    en_rel = TRANSLATIONS + "English.properties"
    de_rel = TRANSLATIONS + "German.properties"
    originals = {
        en_rel: git_file(unciv_fork, source_commit, en_rel),
        de_rel: git_file(unciv_fork, source_commit, de_rel),
    }

    batch_sources: dict[str, dict[str, str]] = {}
    batch_meta: dict[str, dict] = {}
    for entry in requests:
        if not isinstance(entry, dict):
            raise TypeError("Each build-requests entry must be an object")
        batch_id = entry.get("id")
        patches = entry.get("patches")
        patch_sha = entry.get("patch_set_sha256")
        if (
            not isinstance(batch_id, str)
            or not isinstance(patches, list)
            or not isinstance(patch_sha, str)
        ):
            raise TypeError("Invalid build-requests entry fields")
        expected_sha = sha256_bytes(canonical_bytes(patches))
        if patch_sha != expected_sha or batch_id != f"batch-{expected_sha[:16]}":
            raise ValueError(f"Batch ID or patch hash mismatch for {batch_id}")
        if batch_id in batch_sources:
            raise ValueError(f"Duplicate batch ID in build-requests: {batch_id}")
        patched = apply_patches(originals, patches)
        en_bytes = patched[en_rel]
        de_bytes = patched[de_rel]
        batch_sources[batch_id] = {
            "en": en_bytes.decode("utf-8"),
            "de": de_bytes.decode("utf-8"),
        }
        batch_meta[batch_id] = {
            "patch_set_sha256": patch_sha,
            "patch_count": len(patches),
            "en_sha256": sha256_bytes(en_bytes),
            "de_sha256": sha256_bytes(de_bytes),
        }
    return source_commit, batch_sources, batch_meta


def parse_batch_tables(
    batch_sources: dict[str, dict[str, str]],
    batch_id: str,
) -> dict[str, TranslationTable]:
    if batch_id not in batch_sources:
        raise BaselineError(f"Unknown batch variant in build-requests: {batch_id}")
    sources = batch_sources[batch_id]
    return {
        "en": TranslationTable.parse(sources["en"]),
        "de": TranslationTable.parse(sources["de"]),
    }


def load_reference_texts(references_dir: Path, screen: str, language: str) -> list[str]:
    ref_path = references_dir / f"{screen}__{language}" / "reference.json"
    if not ref_path.is_file():
        raise ValueError(
            f"Missing confirmed reference for {screen}__{language}: {ref_path}"
        )
    doc = json.loads(ref_path.read_text(encoding="utf-8"))
    if (
        doc.get("status") != "confirmed"
        or doc.get("screen") != screen
        or doc.get("language") != LANGUAGES[language]
        or not isinstance(doc.get("screen_texts"), list)
    ):
        raise ValueError(f"Invalid confirmed reference: {ref_path}")
    return [str(text) for text in doc["screen_texts"]]


def load_screen_inventory(
    inventories_dir: Path,
    screen: str,
    expected_base_commit: str,
) -> tuple[Inventory, str]:
    inv_path = inventories_dir / f"{screen}.json"
    if not inv_path.is_file():
        raise ValueError(f"Missing baseline inventory for {screen}: {inv_path}")
    raw = inv_path.read_bytes()
    inventory = Inventory.model_validate_json(raw)
    if inventory.screen != screen or inventory.base_commit != expected_base_commit:
        raise ValueError(
            f"Inventory {inv_path} does not match screen {screen!r} "
            f"or base_commit {expected_base_commit!r}"
        )
    return inventory, sha256_bytes(raw)


def build_screen_texts(
    reference_texts: list[str],
    inventory: Inventory,
    tables: dict[str, TranslationTable],
    language: str,
    labels: list[Label],
) -> list[str]:
    """Union of #47 reference texts, rendered inventory slots, and label text_seen.

    Preserves the #47 reference list (including genuine repeated occurrences on
    screen) and appends any additional normalized strings from rendered
    inventory slots and labels' `text_seen` once.
    """
    result = list(reference_texts)
    seen = {normalize_text(text) for text in result if normalize_text(text)}
    rendered_slots: list[str] = []
    for slot in inventory.slots:
        try:
            rendered_slots.append(tables[language].render(slot.request))
        except RenderingError:
            continue
    tables[language].lookups.clear()
    for text in (*rendered_slots, *(label.text_seen for label in labels)):
        norm = normalize_text(text)
        if norm and norm not in seen:
            result.append(text)
            seen.add(norm)
    return result


def prepare_dataset(
    dataset_dir: Path,
    *,
    build_requests_path: Path,
    unciv_fork: Path,
    inventories_dir: Path,
    references_dir: Path,
) -> tuple[list[dict], dict]:
    """Validate dataset files, labels, references, inventories, and build tables."""
    if not dataset_dir.is_dir():
        raise ValueError(f"Dataset directory does not exist: {dataset_dir}")
    pngs = sorted(dataset_dir.glob("*.png"))
    if not pngs:
        raise ValueError(f"No PNG screenshots in dataset folder: {dataset_dir}")

    label_files = {p.name for p in dataset_dir.glob("*.labels.json")}
    expected_label_files = {f"{p.stem}.labels.json" for p in pngs}
    missing_labels = sorted(expected_label_files - label_files)
    if missing_labels:
        raise ValueError(
            f"Missing .labels.json for screenshot(s): {', '.join(missing_labels)}"
        )
    extra_labels = sorted(label_files - expected_label_files)
    if extra_labels:
        raise ValueError(
            f"Orphan .labels.json without matching PNG: {', '.join(extra_labels)}"
        )

    source_commit, batch_sources, batch_meta = load_build_tables(
        build_requests_path, unciv_fork
    )

    inventories: dict[str, Inventory] = {}
    inventories_sha256: dict[str, str] = {}
    ref_cache: dict[tuple[str, str], list[str]] = {}
    items: list[dict] = []

    for png in pngs:
        lang = screenshot_language(png)
        screen, _, resolution, variant, version_code = png.stem.split("__")
        png_bytes = png.read_bytes()
        size = png_size(png_bytes)
        if resolution != f"{size[0]}x{size[1]}":
            raise ValueError(
                f"Screenshot resolution {resolution} does not match PNG size {size}: "
                f"{png.name}"
            )
        if not version_code.isdigit():
            raise ValueError(f"Invalid versionCode in filename: {png.name}")

        label_path = dataset_dir / f"{png.stem}.labels.json"
        label_raw = label_path.read_bytes()
        label_doc = json.loads(label_raw.decode("utf-8"))
        if label_doc.get("screenshot") != png.name or label_doc.get("language") != lang:
            raise ValueError(f"Label file identity mismatch: {label_path.name}")
        label_version, labels = load_labels(label_doc)

        if screen not in inventories:
            inv, inv_sha = load_screen_inventory(inventories_dir, screen, source_commit)
            inventories[screen] = inv
            inventories_sha256[screen] = inv_sha
        if (screen, lang) not in ref_cache:
            ref_cache[screen, lang] = load_reference_texts(references_dir, screen, lang)

        tables = parse_batch_tables(batch_sources, variant)
        screen_texts = build_screen_texts(
            ref_cache[screen, lang],
            inventories[screen],
            tables,
            lang,
            labels,
        )

        items.append(
            {
                "png": png,
                "png_sha256": sha256_bytes(png_bytes),
                "size": size,
                "screen": screen,
                "language": lang,
                "variant": variant,
                "version_code": int(version_code),
                "label_path": label_path,
                "label_sha256": sha256_bytes(label_raw),
                "label_schema_version": label_version,
                "labels": labels,
                "inventory": inventories[screen],
                "inventory_sha256": inventories_sha256[screen],
                "screen_texts": screen_texts,
            }
        )

    used_batches = sorted({item["variant"] for item in items})
    provenance = {
        "source_commit": source_commit,
        "build_requests_sha256": sha256_bytes(build_requests_path.read_bytes()),
        "inventories_sha256": dict(sorted(inventories_sha256.items())),
        "batches": {bid: batch_meta[bid] for bid in used_batches},
        "batch_sources": batch_sources,
    }
    return items, provenance


def _run_baseline_image(
    item: dict,
    batch_sources: dict[str, dict[str, str]],
    engine: OcrEngine,
    record_dir: Path | None,
) -> tuple[CheckResult, float]:
    started = time.monotonic()
    png: Path = item["png"]
    lang: str = item["language"]
    size: tuple[int, int] = item["size"]
    inventory: Inventory = item["inventory"]
    variant: str = item["variant"]

    metadata: dict = {
        "detector": "ocr-translation-baseline",
        "schema_version": 2,
        "settings": SETTINGS,
        "requests_sent": 0,
        "run_id": png.stem,
        "image": {"name": png.name, "sha256": item["png_sha256"], "size": list(size)},
        "version_code": item["version_code"],
        "variant": variant,
        "language": lang,
        "inventory_sha256": item["inventory_sha256"],
        "missing_rule_findings": [],
    }
    findings = []
    diagnostics = []
    reason = None
    tsv_text: str | None = None
    try:
        tables = parse_batch_tables(batch_sources, variant)
        output = engine.recognize(png, lang)
        metadata["ocr"] = output.metadata
        tsv_text = output.tsv
        words = parse_tsv(output.tsv, size)
        findings, diagnostics = detect(inventory, tables, lang, words, size)
        metadata["missing_rule_findings"] = [
            row["finding_index"] for row in diagnostics if row["rule"] == "missing"
        ]
    except (
        BaselineError,
        RenderingError,
        CaptureError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        reason = f"{type(exc).__name__}: {exc}"
        findings = []
        metadata["missing_rule_findings"] = []

    latency_s = round(time.monotonic() - started, 3)
    metadata["latency_s"] = latency_s
    result = CheckResult(
        status="not_checked" if reason else "checked",
        findings=findings,
        reason=reason,
        metadata=metadata,
    )
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=False)
        if tsv_text is not None:
            (record_dir / "ocr.tsv").write_text(tsv_text, encoding="utf-8")
        write_json(record_dir / "diagnostics.json", diagnostics)
        write_json(record_dir / "run.json", metadata)
        (record_dir / "result.json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return result, latency_s


def _not_checked_budget_result(
    item: dict,
    provider: VisionProvider,
    max_requests: int,
    reason: str,
    record_dir: Path | None,
) -> tuple[CheckResult, float]:
    png: Path = item["png"]
    width, height = item["size"]
    metadata = {
        "run_id": png.stem,
        "provider": provider.name,
        "model": provider.model,
        "model_version": None,
        "sdk_version": provider.sdk_version,
        "system_fingerprint": None,
        "schema_version": SCHEMA_VERSION,
        "readability": None,
        "unreadable_regions": None,
        "readability_reason": None,
        "language": item["language"],
        "prompt_version": PROMPT_VERSION,
        "prompt_template_sha256": sha256_bytes(PROMPT_TEMPLATE.encode()),
        "prompt_sha256": None,
        "wrapper_version": provider.wrapper_version,
        "sent_prompt_sha256": None,
        "settings": provider.settings,
        "image": {
            "path": str(png),
            "sha256": item["png_sha256"],
            "bytes": png.stat().st_size,
            "width": width,
            "height": height,
            "mime_type": "image/png",
        },
        "max_requests": max_requests,
        "requests_sent": 0,
        "attempts": [],
        "usage": None,
        "estimated_cost": None,
        "reasoning_content": None,
    }
    result = CheckResult(
        status="not_checked",
        findings=[],
        reason=reason,
        metadata=metadata,
    )
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=False)
        write_json(record_dir / "run.json", metadata)
        (record_dir / "result.json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return result, 0.0


def _per_class_summary(items: list[dict], screen_matches_list: list) -> dict[str, dict]:
    totals = {kind: 0 for kind in CLASSES}
    matched = {kind: 0 for kind in CLASSES}
    exact_type = {kind: 0 for kind in CLASSES}

    for item, sm in zip(items, screen_matches_list, strict=True):
        labels: list[Label] = item["labels"]
        for label in labels:
            totals[label.defect_type] += 1
        if sm.status == "not_checked":
            continue
        for pair in sm.matches:
            label = sm.labels[pair.label_index]
            finding = sm.findings[pair.finding_index]
            matched[label.defect_type] += 1
            if finding.defect_type == label.defect_type:
                exact_type[label.defect_type] += 1

    summary: dict[str, dict] = {}
    for kind in CLASSES:
        total = totals[kind]
        hit = matched[kind]
        summary[kind] = {
            "matched": hit,
            "exact_type": exact_type[kind],
            "total": total,
            "recall": hit / total if total else None,
        }
    return summary


def evaluate_dataset(
    *,
    dataset_dir: Path,
    detector: str,
    output_dir: Path,
    command: list[str],
    build_requests_path: Path = DEFAULT_BUILD_REQUESTS,
    unciv_fork: Path = DEFAULT_UNCIV_FORK,
    inventories_dir: Path = DEFAULT_INVENTORIES_DIR,
    references_dir: Path = DEFAULT_REFERENCES_DIR,
    preprocess: str = DEFAULT_PREPROCESSING,
    ocr_engine: OcrEngine | None = None,
    provider: VisionProvider | None = None,
    provider_factory: Callable[[], VisionProvider] | None = None,
    max_requests: int | None = None,
    max_usd: Decimal | None = None,
    keep_records: bool = False,
    matching_config: MatchingConfig = DEFAULT_CONFIG,
    secrets: tuple[str, ...] = (),
    retry_delay_s: float = 5.0,
) -> tuple[dict, list[dict]]:
    """Evaluate `detector` on every PNG in `dataset_dir` and write run records."""
    if detector not in ("baseline", "vision"):
        raise ValueError(f"Unknown detector: {detector!r}")
    if output_dir.exists():
        raise CaptureError(f"Output directory already exists: {output_dir}")
    if detector == "vision":
        if type(max_requests) is not int or max_requests < 1:
            raise ValueError("Vision detector requires --max-requests >= 1")
        if max_usd is None or max_usd <= 0:
            raise ValueError("Vision detector requires a positive --max-usd cap")
        if provider is None and provider_factory is None:
            raise ValueError("Vision detector requires an initialized provider")

    items, provenance = prepare_dataset(
        dataset_dir,
        build_requests_path=build_requests_path,
        unciv_fork=unciv_fork,
        inventories_dir=inventories_dir,
        references_dir=references_dir,
    )
    batch_sources = provenance.pop("batch_sources")

    engine: OcrEngine | None = None
    if detector == "baseline":
        engine = ocr_engine or Tesseract(preprocessing=preprocess)
        reserve_usd = Decimal(0)
    else:
        if provider is None:
            assert provider_factory is not None
            provider = provider_factory()
        reserve_usd = worst_case_request_reserve_usd(provider)

    output_dir.mkdir(parents=True, exist_ok=False)
    records_root = output_dir / "records" if keep_records else None
    if records_root is not None:
        records_root.mkdir()

    total_requests_sent = 0
    known_peak_usd = Decimal(0)
    known_off_peak_usd = Decimal(0)
    unknown_reserve_usd = Decimal(0)
    token_totals: dict[str, int] = {}
    has_usage = False
    model_versions: set[str] = set()

    screen_matches_list = []
    per_image_rows: list[dict] = []
    tp_observed_total = tp_missing_total = 0
    fp_observed_total = fp_missing_total = 0
    empty_label_fp = empty_label_fp_observed = empty_label_fp_missing = 0

    for item in items:
        png: Path = item["png"]
        labels: list[Label] = item["labels"]
        is_empty_labels = len(labels) == 0
        record_dir = records_root / png.stem if records_root is not None else None

        if detector == "baseline":
            assert engine is not None
            result, latency_s = _run_baseline_image(
                item, batch_sources, engine, record_dir
            )
        else:
            assert provider is not None
            assert max_requests is not None and max_usd is not None
            accounted_upper = known_peak_usd + unknown_reserve_usd
            if total_requests_sent + 1 > max_requests:
                result, latency_s = _not_checked_budget_result(
                    item,
                    provider,
                    max_requests,
                    f"request_cap_reached: dataset cap of {max_requests} reached",
                    record_dir,
                )
            elif accounted_upper + reserve_usd > max_usd:
                result, latency_s = _not_checked_budget_result(
                    item,
                    provider,
                    max_requests,
                    (
                        f"usd_cap_reached: next request worst-case reserve "
                        f"{reserve_usd} USD would exceed max_usd {max_usd} USD "
                        f"(accounted upper bound: {accounted_upper} USD)"
                    ),
                    record_dir,
                )
            else:
                with tempfile.TemporaryDirectory(prefix="l10n-eval-") as tmp_runs:
                    result, tmp_run_dir = run_check(
                        provider,
                        png,
                        Path(tmp_runs),
                        RequestBudget(1),
                        secrets=secrets,
                        retry_delay_s=retry_delay_s,
                    )
                    if record_dir is not None:
                        shutil.copytree(tmp_run_dir, record_dir)
                attempts = result.metadata.get("attempts") or []
                latency_s = round(sum(a.get("latency_s", 0.0) for a in attempts), 3)

            sent = int(result.metadata.get("requests_sent", 0))
            total_requests_sent += sent
            mv = result.metadata.get("model_version")
            if isinstance(mv, str) and mv:
                model_versions.add(mv)
            usage = result.metadata.get("usage")
            if isinstance(usage, dict):
                for key, val in usage.items():
                    if type(val) is int and val >= 0:
                        token_totals[key] = token_totals.get(key, 0) + val
                        has_usage = True
                reasoning_tok = _reasoning_tokens(usage)
                if reasoning_tok is not None:
                    token_totals["reasoning_tokens"] = (
                        token_totals.get("reasoning_tokens", 0) + reasoning_tok
                    )
                    has_usage = True
            cost = result.metadata.get("estimated_cost")
            if isinstance(cost, dict) and "peak_usd" in cost:
                known_peak_usd += Decimal(str(cost["peak_usd"]))
                if "off_peak_usd" in cost:
                    known_off_peak_usd += Decimal(str(cost["off_peak_usd"]))
            elif sent > 0:
                unknown_reserve_usd += reserve_usd * sent

        result_version = result_schema_version(result.metadata)
        sm = match_screen(
            labels,
            result.findings,
            item["screen_texts"],
            result.status,
            matching_config,
            label_schema_version=item["label_schema_version"],
            result_schema_version=result_version,
        )
        screen_matches_list.append(sm)
        image_metrics = score_screen(sm)

        missing_set = set(result.metadata.get("missing_rule_findings") or [])
        img_tp_miss = sum(1 for m in sm.matches if m.finding_index in missing_set)
        img_tp_obs = len(sm.matches) - img_tp_miss
        img_fp_miss = sum(
            1 for idx in sm.unmatched_finding_indices if idx in missing_set
        )
        img_fp_obs = len(sm.unmatched_finding_indices) - img_fp_miss

        tp_observed_total += img_tp_obs
        tp_missing_total += img_tp_miss
        fp_observed_total += img_fp_obs
        fp_missing_total += img_fp_miss
        if is_empty_labels:
            empty_label_fp += image_metrics.fp
            empty_label_fp_observed += img_fp_obs
            empty_label_fp_missing += img_fp_miss

        cost = result.metadata.get("estimated_cost")
        per_image_rows.append(
            {
                "image": png.name,
                "sha256": item["png_sha256"],
                "screen": item["screen"],
                "language": item["language"],
                "variant": item["variant"],
                "version_code": item["version_code"],
                "empty_labels": is_empty_labels,
                "label_count": len(labels),
                "status": result.status,
                "reason": result.reason,
                "readability": result.metadata.get("readability"),
                "findings_count": len(result.findings),
                "findings": [f.model_dump() for f in result.findings],
                "missing_rule_findings": sorted(missing_set),
                "tp": image_metrics.tp,
                "tp_observed": img_tp_obs,
                "tp_missing": img_tp_miss,
                "fp": image_metrics.fp,
                "fp_observed": img_fp_obs,
                "fp_missing": img_fp_miss,
                "fn": image_metrics.fn,
                "fn_on_not_checked": image_metrics.fn_on_not_checked,
                "precision": image_metrics.precision,
                "recall_checked": image_metrics.recall_checked,
                "recall_all": image_metrics.recall_all,
                "duplicates_collapsed": image_metrics.duplicates_collapsed,
                "hallucinations": image_metrics.hallucinations,
                "matches": [asdict(m) for m in sm.matches],
                "unmatched_finding_indices": list(sm.unmatched_finding_indices),
                "unmatched_label_indices": list(sm.unmatched_label_indices),
                "duplicate_finding_indices": list(sm.duplicate_finding_indices),
                "hallucination_indices": list(sm.hallucination_indices),
                "requests_sent": int(result.metadata.get("requests_sent", 0)),
                "model_version": result.metadata.get("model_version"),
                "usage": result.metadata.get("usage"),
                "estimated_cost": cost,
                "reasoning_content": result.metadata.get("reasoning_content"),
                "latency_s": latency_s,
            }
        )

    overall = score_screens(screen_matches_list)
    per_class = _per_class_summary(items, screen_matches_list)
    empty_label_count = sum(1 for item in items if not item["labels"])

    metrics_dict = {
        **overall.to_dict(),
        "tp_observed": tp_observed_total,
        "tp_missing": tp_missing_total,
        "fp_observed": fp_observed_total,
        "fp_missing": fp_missing_total,
        "empty_label_images": empty_label_count,
        "empty_label_fp": empty_label_fp,
        "empty_label_fp_observed": empty_label_fp_observed,
        "empty_label_fp_missing": empty_label_fp_missing,
        "clean_fp": empty_label_fp,
        "per_class_recall": per_class,
    }

    config_record: dict = {
        "dataset": str(dataset_dir),
        "detector": detector,
        "image_count": len(items),
        "empty_label_images": empty_label_count,
        "mutated_images": len(items) - empty_label_count,
        "label_count": sum(len(item["labels"]) for item in items),
        "build_requests": str(build_requests_path),
        "inventories_dir": str(inventories_dir),
        "references_dir": str(references_dir),
        "screen_texts_sources": [
            "docs/evidence/47/reference-confirmation",
            "rendered_baseline_inventories",
            "labels_text_seen",
        ],
        "matching_config": asdict(matching_config),
        "keep_records": keep_records,
        **provenance,
    }
    if detector == "baseline":
        config_record["baseline_settings"] = {
            **SETTINGS,
            "preprocessing": getattr(engine, "preprocessing", preprocess),
        }
        token_usage_record: dict = {}
        estimated_cost_record = {
            "peak_usd": "0",
            "off_peak_usd": "0",
            "unknown_cost_reserve_usd": "0",
            "accounted_peak_upper_bound_usd": "0",
        }
        estimated_cost_usd = "0"
    else:
        assert provider is not None
        provider_tariff = getattr(provider, "tariff", TARIFF)
        sorted_versions = sorted(model_versions)
        config_record["vision"] = {
            "provider": provider.name,
            "model": provider.model,
            "model_version": sorted_versions[0] if len(sorted_versions) == 1 else None,
            "model_versions": sorted_versions,
            "sdk_version": provider.sdk_version,
            "schema_version": SCHEMA_VERSION,
            "prompt_version": PROMPT_VERSION,
            "prompt_template_sha256": sha256_bytes(PROMPT_TEMPLATE.encode()),
            "wrapper_version": provider.wrapper_version,
            "settings": provider.settings,
            "max_requests": max_requests,
            "max_usd": str(max_usd),
            "per_request_reserve_usd": str(reserve_usd),
            "tariff": provider_tariff,
        }
        token_usage_record = token_totals if has_usage else {}
        accounted_upper = known_peak_usd + unknown_reserve_usd
        estimated_cost_record = {
            "peak_usd": str(known_peak_usd),
            "unknown_cost_reserve_usd": str(unknown_reserve_usd),
            "accounted_peak_upper_bound_usd": str(accounted_upper),
        }
        if "off_peak_multiplier" in provider_tariff:
            estimated_cost_record["off_peak_usd"] = str(known_off_peak_usd)
        else:
            estimated_cost_record["usd"] = str(known_peak_usd)
        estimated_cost_usd = str(accounted_upper)

    run_record = {
        "run_id": output_dir.name,
        "detector": detector,
        "commit": git_head_commit(),
        "command": [redact(arg, secrets) for arg in command],
        "seed": None,
        "requests_sent": total_requests_sent,
        "token_usage": token_usage_record,
        "estimated_cost": estimated_cost_record,
        "estimated_cost_usd": estimated_cost_usd,
        "config": config_record,
        "metrics": metrics_dict,
    }

    write_json(output_dir / "per_image.json", per_image_rows)
    write_json(output_dir / "run.json", run_record)
    return run_record, per_image_rows
