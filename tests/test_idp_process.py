"""Tests for data/IDP/process.py label resolution.

Covers the two paths in _label_to_canonical:
  - normal ZSCode lookup against the shapefile
  - fallback to title-case trailing name when the ZSCode isn't current
    (the known case: the legacy 'CD5401ZS01 | BUNIA' phantom that the current
    MoH shapefile merges into CD5402ZS02).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_idp_module():
    """Import data/IDP/process.py with its hyphen-free folder name handling."""
    spec = importlib.util.spec_from_file_location(
        "_idp_process_under_test",
        REPO_ROOT / "data" / "IDP" / "process.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_label_resolves_via_zscode():
    idp = _load_idp_module()
    assert idp._label_to_canonical("CD5402ZS02 | BUNIA") == "Bunia"
    assert idp._label_to_canonical("CD6101ZS01 | GOMA") == "Goma"


def test_label_resolves_phantom_via_name_fallback():
    # ZSCode CD5401ZS01 is absent from the current shapefile; the trailing
    # name 'BUNIA' title-cases to canonical 'Bunia', so the fallback must hit.
    idp = _load_idp_module()
    assert idp._label_to_canonical("CD5401ZS01 | BUNIA") == "Bunia"


def test_label_rejects_unresolvable():
    idp = _load_idp_module()
    with pytest.raises(ValueError):
        # Made-up ZSCode AND a non-existent name; both lookups must fail.
        idp._label_to_canonical("CD9999ZS99 | NOWHERE")


def test_label_requires_pipe_format():
    idp = _load_idp_module()
    with pytest.raises(ValueError):
        idp._label_to_canonical("just a name")
