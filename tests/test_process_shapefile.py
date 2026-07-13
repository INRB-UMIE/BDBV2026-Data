"""Tests for data/shapefiles/process_shapefile.py"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

REPO_ROOT = Path(__file__).resolve().parents[1]
SHAPEFILES_DIR = REPO_ROOT / "data" / "shapefiles"


def _load_module():
    # config.py lives alongside process_shapefile.py; add the dir so the
    # top-level `import config` inside the module resolves correctly.
    sys.path.insert(0, str(SHAPEFILES_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "_process_shapefile_under_test",
            SHAPEFILES_DIR / "process_shapefile.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


_ps = _load_module()
_sha256_for_path = _ps._sha256_for_path
process_shapefile = _ps.process_shapefile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_shapefile(tmp_path: Path, columns: dict[str, list], stem: str = "test") -> Path:
    data = dict(columns)
    data["geometry"] = [Point(0, 0), Point(1, 1)]
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    shp_path = tmp_path / f"{stem}.shp"
    gdf.to_file(shp_path)
    return shp_path


def _bundle_sha256(shp_path: Path) -> str:
    bundle = sorted(
        (p for p in shp_path.parent.glob(f"{shp_path.stem}.*") if p.is_file()),
        key=lambda p: p.suffix.lower(),
    )
    hasher = hashlib.sha256()
    for component in bundle:
        hasher.update(component.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(component.read_bytes())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# _sha256_for_path
# ---------------------------------------------------------------------------


def test_sha256_non_shp_hashes_file_directly(tmp_path):
    f = tmp_path / "data.txt"
    f.write_bytes(b"hello")
    assert _sha256_for_path(f) == hashlib.sha256(b"hello").hexdigest()


def test_sha256_non_shp_changes_with_content(tmp_path):
    f = tmp_path / "data.txt"
    f.write_bytes(b"v1")
    h1 = _sha256_for_path(f)
    f.write_bytes(b"v2")
    h2 = _sha256_for_path(f)
    assert h1 != h2


def test_sha256_shp_matches_bundle_hash(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"], "value": [1, 2]})
    assert _sha256_for_path(shp_path) == _bundle_sha256(shp_path)


def test_sha256_shp_is_deterministic(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"]})
    assert _sha256_for_path(shp_path) == _sha256_for_path(shp_path)


def test_sha256_shp_no_bundle_raises(tmp_path):
    ghost = tmp_path / "ghost.shp"  # path ends in .shp but no sibling files exist
    with pytest.raises(FileNotFoundError):
        _sha256_for_path(ghost)


# ---------------------------------------------------------------------------
# process_shapefile
# ---------------------------------------------------------------------------


def test_process_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        process_shapefile(tmp_path / "missing.shp", "a" * 64, [], {})


def test_process_sha256_mismatch(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"]})
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        process_shapefile(shp_path, "0" * 64, ["name"], {})


def test_process_sha256_case_insensitive(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"]})
    sha = _bundle_sha256(shp_path).upper()
    gdf = process_shapefile(shp_path, sha, ["name"], {})
    assert isinstance(gdf, gpd.GeoDataFrame)


def test_process_column_mismatch(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"], "value": [1, 2]})
    sha = _bundle_sha256(shp_path)
    with pytest.raises(ValueError, match="Column mismatch"):
        process_shapefile(shp_path, sha, ["name", "wrong_col"], {})


def test_process_success_no_rename(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"], "value": [1, 2]})
    sha = _bundle_sha256(shp_path)
    gdf = process_shapefile(shp_path, sha, ["name", "value"], {})
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert set(["name", "value"]).issubset(gdf.columns)
    assert len(gdf) == 2


def test_process_rename_columns(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"], "value": [1, 2]})
    sha = _bundle_sha256(shp_path)
    gdf = process_shapefile(shp_path, sha, ["name", "value"], {"name": "label"})
    assert "label" in gdf.columns
    assert "name" not in gdf.columns
    assert "value" in gdf.columns


def test_process_rename_collision_raises(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"], "value": [1, 2]})
    sha = _bundle_sha256(shp_path)
    with pytest.raises(ValueError, match="duplicate"):
        process_shapefile(shp_path, sha, ["name", "value"], {"name": "value"})


def test_process_geometry_preserved(tmp_path):
    shp_path = _make_shapefile(tmp_path, {"name": ["a", "b"]})
    sha = _bundle_sha256(shp_path)
    gdf = process_shapefile(shp_path, sha, ["name"], {})
    assert gdf.geometry is not None
    assert not gdf.geometry.is_empty.any()
