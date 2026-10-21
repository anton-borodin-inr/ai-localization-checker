"""The experiment must refuse a live request before either cap can be exceeded."""

import importlib
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.fixture
def check(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("issue45_check")


def test_last_request_allowed_but_one_hundred_and_first_refused(check):
    ledger = {"runs": [{"status": "recorded", "request_upper_bound": 99}]}
    check.check_budget(ledger)
    ledger["runs"][0]["request_upper_bound"] = 100
    with pytest.raises(ValueError, match="both task caps"):
        check.check_budget(ledger)


def test_unknown_failures_consume_dollar_budget(check):
    failed = {
        "status": "recorded",
        "request_upper_bound": 1,
        "unknown_cost_reserve_usd": str(check.MAX_REQUEST_USD),
    }
    ledger = {"runs": [dict(failed), dict(failed)]}
    check.check_budget(ledger)
    ledger["runs"].append(dict(failed))
    with pytest.raises(ValueError, match="both task caps"):
        check.check_budget(ledger)


def test_exact_usd_boundary_has_no_float_rounding(check):
    ledger = {
        "runs": [
            {
                "status": "recorded",
                "requests_sent": 1,
                "peak_usd": str(Decimal("1.00") - check.MAX_REQUEST_USD),
            }
        ]
    }
    check.check_budget(ledger)
    ledger["runs"][0]["peak_usd"] = str(
        Decimal(ledger["runs"][0]["peak_usd"]) + Decimal("0.00000001")
    )
    with pytest.raises(ValueError, match="both task caps"):
        check.check_budget(ledger)


@pytest.mark.parametrize("status", ["pending", "unreconciled"])
def test_interruption_blocks_following_requests(check, status):
    with pytest.raises(ValueError, match="interrupted request"):
        check.check_budget({"runs": [{"status": status, "request_upper_bound": 1}]})
