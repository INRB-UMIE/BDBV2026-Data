"""Tests for data/cross-border-movements/process.py column resolution.

The raw CSV has long, irregularly-cased headers. _resolve_columns must match
them via normalised (lowercased, whitespace-collapsed) form and fail with a
clear message when an expected column is absent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_cb_module():
    spec = importlib.util.spec_from_file_location(
        "_cross_border_process_under_test",
        REPO_ROOT / "data" / "cross-border-movements" / "process.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_columns_handles_real_headers():
    cb = _load_cb_module()
    headers = [
        "Province",
        "Point of Entry (PoE)",
        "Number of sitreps with an observation",
        "mean reported weekly passengers entering uganda through this PoE",
        "Mean daily passengers",
    ]
    cols = cb._resolve_columns(headers)
    assert cols["poe"] == "Point of Entry (PoE)"
    assert cols["weekly"] == "mean reported weekly passengers entering uganda through this PoE"
    assert cols["daily"] == "Mean daily passengers"


def test_resolve_columns_tolerates_cosmetic_changes():
    cb = _load_cb_module()
    # Cased differently, extra interior whitespace — all normalised away.
    headers = [
        "  point of entry (POE)  ",
        "MEAN REPORTED WEEKLY PASSENGERS ENTERING UGANDA THROUGH THIS POE",
        "mean   daily   passengers",
    ]
    cols = cb._resolve_columns(headers)
    assert cols["poe"] == "  point of entry (POE)  "
    assert "weekly" in cols
    assert "daily" in cols


def test_resolve_columns_missing_raises_with_clear_message():
    cb = _load_cb_module()
    headers = ["Province", "Point of Entry (PoE)", "Mean daily passengers"]
    with pytest.raises(KeyError) as excinfo:
        cb._resolve_columns(headers)
    msg = str(excinfo.value)
    # The error should name what's missing in normalised form for grep-ability.
    assert "weekly" in msg.lower()
