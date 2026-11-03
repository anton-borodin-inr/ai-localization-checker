"""Offline CLI integration and side-effect boundaries."""

import importlib
import importlib.util
import socket
import subprocess
from pathlib import Path

import pytest
from test_mutation_plan import inputs, registry

from l10n_checker.screen_manifest import json_bytes


def api():
    assert importlib.util.find_spec("l10n_checker.mutation_cli") is not None, (
        "The offline mutation CLI is missing"
    )
    return importlib.import_module("l10n_checker.mutation_cli")


def arguments(kwargs, output):
    return [
        "plan",
        "--manifest",
        str(kwargs["manifest"]),
        "--recipes",
        str(kwargs["recipes"]),
        "--inventory",
        str(kwargs["inventory"]),
        "--split",
        "dev",
        "--seed",
        "59",
        "--output-dir",
        str(output),
    ]


def test_offline_cli_writes_identical_bundles_without_device_network_or_processes(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline planning attempted a process/device/network operation")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    kwargs = inputs(tmp_path)
    first, second = tmp_path / "first", tmp_path / "second"
    assert api().main(arguments(kwargs, first)) == 0
    assert api().main(arguments(kwargs, second)) == 0
    assert (first / "plan.json").read_bytes() == (second / "plan.json").read_bytes()
    assert (first / "build-requests.json").read_bytes() == (
        second / "build-requests.json"
    ).read_bytes()
    requests = json_bytes((first / "build-requests.json").read_bytes())
    clean = [r for r in requests["requests"] if r["role"] == "clean"]
    assert len(clean) == 1 and clean[0]["patches"] == []
    assert requests["source_commit"] == "b534a8ae67c390412984869c7a03b168d532c36c"
    assert all("version_code" not in r for r in requests["requests"])
    assert api().main(arguments(kwargs, first)) == 1


def test_cli_rejects_excluded_ids_before_creating_output(tmp_path):
    kwargs = inputs(tmp_path)
    output = tmp_path / "never-created"
    args = arguments(kwargs, output)
    start = args.index("--split")
    args[start : start + 2] = ["--screen-id", registry().holdout[0]]
    assert api().main(args) == 1
    assert not output.exists()


def test_cli_cannot_overwrite_source_files(tmp_path):
    kwargs = inputs(tmp_path)
    output = Path(__file__).resolve().parents[1] / "src/l10n_checker"
    assert api().main(arguments(kwargs, output)) == 1
