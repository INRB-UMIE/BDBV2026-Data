"""Build merged GeoJSON + manifest from QA-passing non-matrix outputs.

Outputs:
  build/drc_health_zones.geojson  — shapefile geometry merged with latest
                                     per-zone values from every passing vector file.
                                     Property layout:
                                       feature.properties.nom        canonical Nom
                                       feature.properties.zscode     shapefile ZSCode
                                       feature.properties.province   shapefile PROVINCE
                                       feature.properties.<dataset>.<metric> = {
                                         <value_col_1>: ..., <value_col_2>: ...,
                                         _date: <ISO date>     (time-series only)
                                       }
                                     <dataset> here is the filename's lower_snake_case
                                     token (e.g. "cross_border", "idp"), not the folder
                                     name. See manifest.json for the folder<->token map.
  build/long/<dataset>__<metric>.csv — full long-format copy of each vector file.
  build/matrix/<file>.matrix.csv — copies of QA-passing matrix files (not embedded in
                                     the GeoJSON; packaged with the release archive).
  build/manifest.json — what's in the build, per-folder source metadata, build timestamp.

Matrices are deliberately NOT embedded in the GeoJSON; consumers fetch them from
``build/matrix/`` (or ``data/<dataset>/processed/``) using qa/matrix_log.csv as the
catalog.

Geometry is simplified (shapely, tolerance SIMPLIFY_TOL) and coordinates
rounded (COORD_DECIMALS) before being embedded, regardless of the source
shapefile's own vertex density — see the comment above SIMPLIFY_TOL for why.

Run from repo root:
    python -m tools.build_geojson

On success, updates the ``Last successful build`` line in ``README.md`` from
``build/manifest.json`` (use ``--skip-readme`` to disable).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import shapefile  # pyshp
import yaml
from shapely.geometry import mapping, shape
from shapely.validation import make_valid

from tools.lib.release import (
    format_last_build_line,
    replace_current_build_heading,
    replace_last_build_line,
)
from tools.lib.schema import (
    NATIONAL_ROLLUP_NOM,
    REPO_ROOT,
    SHAPEFILE,
    is_non_geographic_nom,
    is_province_rollup_nom,
    load_zones,
    parse_filename,
    province_name_from_rollup_nom,
    requires_zone_only_noms,
    resolve_processed_paths,
    resolve_vector_nom,
    zones_by_province,
)

README = REPO_ROOT / "README.md"

DATA_DIR = REPO_ROOT / "data"
QA_LOG = REPO_ROOT / "qa" / "qa_log.csv"
BUILD_DIR = REPO_ROOT / "build"
LONG_DIR = BUILD_DIR / "long"
MATRIX_DIR = BUILD_DIR / "matrix"
GEOJSON_OUT = BUILD_DIR / "drc_health_zones.geojson"
MANIFEST_OUT = BUILD_DIR / "manifest.json"

DATE_COLUMN_CANDIDATES = ("date", "week_start", "month_start", "year")

# Geometry simplification applied to every shapefile feature before it's
# embedded in GeoJSON. Matches the tolerance the dashboard build already
# applies on its own end (Scripts/build_dashboard_public.py's SIMPLIFY_TOL),
# so this isn't introducing a new visual fidelity trade-off — it's just
# doing, once, at the source, the same simplification every downstream
# consumer already needs and was previously repeating (or, in this build's
# own case, not doing at all). Shapefiles vary wildly in vertex density
# depending on how they were digitized; without this, a swap to a more
# detailed source shapefile silently balloons build/drc_health_zones.geojson
# (a 2026-07 shapefile update took it from ~31 MB to ~170 MB with no change
# in the underlying data, only in coordinate precision nobody downstream
# uses). Simplifying here keeps output size stable and predictable no
# matter how detailed the source shapefile is.
SIMPLIFY_TOL = 0.001  # ~110 m at the equator; ~10x fewer vertices than raw
COORD_DECIMALS = 5  # ~1 m precision at the equator; plenty for zone polygons


def _round_coords(coords):
    """Recursively round a GeoJSON coordinate array to COORD_DECIMALS."""
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(c, COORD_DECIMALS) for c in coords]
    return [_round_coords(c) for c in coords]


def _simplify_geometry(geo_interface: dict) -> dict:
    """Simplify + round a raw shapefile geometry for GeoJSON output.

    Falls back to the unsimplified (but still rounded) geometry if
    simplification collapses a feature to nothing, so no zone can ever be
    silently dropped from the build.
    """
    geom = make_valid(shape(geo_interface))
    if SIMPLIFY_TOL > 0:
        simplified = geom.simplify(SIMPLIFY_TOL, preserve_topology=True)
        if not simplified.is_empty:
            geom = simplified
    gdict = mapping(geom)
    coords = gdict.get("coordinates")
    if coords:
        gdict["coordinates"] = _round_coords(list(coords))
    return gdict


def _coerce(value: str):
    """int -> float -> str fallback. Empty -> None."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _read_qa_log() -> list[dict]:
    with QA_LOG.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_metadata(folder: Path) -> dict:
    p = folder / "metadata.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _load_features() -> tuple[list[dict], dict[str, dict]]:
    reader = shapefile.Reader(str(SHAPEFILE))
    zones = load_zones()
    features: list[dict] = []
    by_nom: dict[str, dict] = {}
    for zone, sh in zip(zones, reader.shapes()):
        feat = {
            "type": "Feature",
            "geometry": _simplify_geometry(sh.__geo_interface__),
            "properties": {
                "nom": zone.canonical_nom,
                "zscode": zone.zscode,
                "province": zone.province,
            },
        }
        features.append(feat)
        # Multiple shapefile features can share the same canonical Nom in
        # principle (none currently do after disambiguation), so map by zscode-
        # keyed dict to avoid collision. For attaching dataset values we still
        # key by canonical Nom because dataset outputs use Nom only.
        by_nom[zone.canonical_nom] = feat
    return features, by_nom


def _attach_vector(
    src: Path,
    file_name: str,
    parsed,
    features_by_nom: dict[str, dict],
) -> int:
    with src.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = [k for k in (reader.fieldnames or []) if k != ""]
        rows = [{k: v for k, v in row.items() if k != ""} for row in reader]

    dataset_token = parsed.dataset
    metric = parsed.metric

    # Header-only placeholders pass QA but carry no attachable values yet.
    if not rows:
        LONG_DIR.mkdir(parents=True, exist_ok=True)
        dst = LONG_DIR / f"{dataset_token}__{metric}.csv"
        with dst.open("w", encoding="utf-8-sig") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()
        return 0

    date_col = next((c for c in DATE_COLUMN_CANDIDATES if c in fieldnames), None)
    value_cols = [c for c in fieldnames if c and c != "nom" and c != date_col]

    # For time-series: pick latest row per canonical nom.
    latest_per_nom: dict[str, dict] = {}
    for r in rows:
        canonical = resolve_vector_nom(r["nom"])
        if canonical is None or is_non_geographic_nom(canonical):
            continue
        if date_col:
            existing = latest_per_nom.get(canonical)
            # Lexical string comparison is safe here because the contract
            # requires ISO 8601 dates (YYYY-MM-DD or YYYY), which sort
            # correctly as strings. Don't relax this without parsing.
            if existing is None or r[date_col] > existing[date_col]:
                latest_per_nom[canonical] = r
        else:
            latest_per_nom[canonical] = r

    attached = 0

    def _apply_row(nom: str, r: dict) -> None:
        nonlocal attached
        feat = features_by_nom.get(nom)
        if feat is None:
            return
        ds_bucket = feat["properties"].setdefault(dataset_token, {})
        value_obj = {c: _coerce(r[c]) for c in value_cols}
        if date_col:
            value_obj["_date"] = r[date_col]
        ds_bucket[metric] = value_obj
        attached += 1

    national_row = latest_per_nom.pop(NATIONAL_ROLLUP_NOM, None)
    province_rows: dict[str, dict] = {}
    zone_rows: dict[str, dict] = {}
    for nom, r in latest_per_nom.items():
        if is_province_rollup_nom(nom):
            province_rows[nom] = r
        else:
            zone_rows[nom] = r

    for nom, r in zone_rows.items():
        _apply_row(nom, r)

    # Defense in depth: zone-level insp_sitrep files must not broadcast
    # province/national roll-ups across zones — that clobbers real per-zone
    # counts (QA fails such a PR; this catches anything that bypasses QA).
    if requires_zone_only_noms(dataset_token, metric) and (
        province_rows or national_row is not None
    ):
        offenders = sorted(province_rows)
        if national_row is not None:
            offenders.append(NATIONAL_ROLLUP_NOM)
        print(
            f"  WARNING: {file_name}: dropped {len(offenders)} province/national "
            f"roll-up row(s) {offenders} — zone-level file must not carry them",
            file=sys.stderr,
        )
    else:
        by_province = zones_by_province()
        for prov, r in province_rows.items():
            # `prov` may carry the "(province)" disambiguation marker (see
            # PROVINCE_ROLLUP_SUFFIX) — strip it to get the bare shapefile
            # PROVINCE key that zones_by_province() is keyed by.
            bare_prov = province_name_from_rollup_nom(prov)
            for zone_nom in by_province.get(bare_prov, []):
                _apply_row(zone_nom, r)

        if national_row is not None:
            value_obj = {c: _coerce(national_row[c]) for c in value_cols}
            if date_col:
                value_obj["_date"] = national_row[date_col]
            for feat in features_by_nom.values():
                ds_bucket = feat["properties"].setdefault(dataset_token, {})
                ds_bucket[metric] = dict(value_obj)
                attached += 1

    # Long-format copy.
    LONG_DIR.mkdir(parents=True, exist_ok=True)
    dst = LONG_DIR / f"{dataset_token}__{metric}.csv"

    with dst.open("w", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writerows(rows)

    return attached


def _git_head_shas() -> tuple[str, str]:
    """Return (full_sha, short_sha). Empty strings if not in a git tree."""
    try:
        full = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        short = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return full, short
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "", ""


def _current_short_sha() -> str:
    return _git_head_shas()[1]


def _stamp_readme(manifest: dict) -> None:
    """Update README build timestamp lines from a fresh manifest."""
    if not README.exists():
        print(f"README not found at {README}; skipping stamp.", file=sys.stderr)
        return
    built_at = manifest["built_at"]
    commit_short = manifest["commit"]
    head_full, _ = _git_head_shas()
    last_build_line = format_last_build_line(
        built_at=built_at,
        commit_short=commit_short,
        head_full_sha=head_full,
    )
    build_date = built_at.split("T", 1)[0]
    readme = README.read_text(encoding="utf-8")
    readme = replace_last_build_line(readme, last_build_line)
    readme = replace_current_build_heading(readme, build_date)
    README.write_text(readme, encoding="utf-8")
    try:
        label = str(README.relative_to(REPO_ROOT))
    except ValueError:
        label = str(README)
    print(f"stamped {label} (Last successful build)")


def _build_manifest(qa_rows: list[dict], attached_counts: dict[tuple[str, str], int]) -> dict:
    # Include every folder that passed metadata QA so placeholders are visible
    # in the index, even when they have no outputs yet.
    by_folder: dict[str, list[dict]] = defaultdict(list)
    folders_with_passing_meta: set[str] = set()
    for row in qa_rows:
        if row["status"] == "fail":
            continue
        if row["type"] == "metadata" and row["status"] == "pass":
            folders_with_passing_meta.add(row["dataset"])
        elif row["type"] in ("vector", "matrix"):
            by_folder[row["dataset"]].append(row)
    for folder_name in folders_with_passing_meta:
        by_folder.setdefault(folder_name, [])

    datasets: list[dict] = []
    for folder_name in sorted(by_folder):
        folder = DATA_DIR / folder_name
        meta = _read_metadata(folder)
        outputs: list[dict] = []
        for row in sorted(by_folder[folder_name], key=lambda r: r["file"]):
            parsed = parse_filename(row["file"])
            if parsed is None:
                continue
            entry = {
                "file": row["file"],
                "type": row["type"],
                "dataset_token": parsed.dataset,
                "metric": parsed.metric,
                "resolution": parsed.resolution,
            }
            if row["type"] == "vector":
                entry["in_geojson"] = True
                entry["zones_with_values"] = attached_counts.get(
                    (folder_name, row["file"]), 0
                )
                entry["long_csv"] = f"build/long/{parsed.dataset}__{parsed.metric}.csv"
            else:
                entry["in_geojson"] = False
                entry["matrix_csv"] = f"build/matrix/{row['file']}"
                entry["matrix_log"] = "qa/matrix_log.csv"
            outputs.append(entry)
        datasets.append({
            "folder": folder_name,
            "source": meta.get("source"),
            "citation": meta.get("citation"),
            "source_url": meta.get("source_url"),
            "retrieved_on": str(meta.get("retrieved_on")) if meta.get("retrieved_on") else None,
            "license": meta.get("license"),
            "contact": meta.get("contact"),
            "status": meta.get("status", "active"),
            "outputs": outputs,
        })
    return {
        "shapefile": "data/shapefiles/DRC_Health_zones.shp",
        "n_features": len(load_zones()),
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "commit": _current_short_sha(),
        "datasets": datasets,
    }


def _stage_matrices(qa_rows: list[dict]) -> int:
    """Copy QA-passing matrix CSVs into build/matrix/ for the release archive.

    Replaces the directory contents each run so renamed/removed matrices do not
    linger from a prior build.
    """
    if MATRIX_DIR.exists():
        shutil.rmtree(MATRIX_DIR)
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)

    staged = 0
    for row in qa_rows:
        if row["status"] == "fail" or row["type"] != "matrix":
            continue
        folder = DATA_DIR / row["dataset"]
        resolved = resolve_processed_paths(folder, row["file"])
        if not resolved:
            print(
                f"skip matrix {row['file']}: no matching processed file "
                f"(checked language variants)",
                file=sys.stderr,
            )
            continue
        for src, resolved_name in resolved:
            dst = MATRIX_DIR / resolved_name
            shutil.copy2(src, dst)
            staged += 1
            print(f"staged matrix {resolved_name}")
    return staged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build merged GeoJSON and manifest from QA-passing vector outputs.",
    )
    parser.add_argument(
        "--skip-readme",
        action="store_true",
        help="Do not update the Last successful build line in README.md",
    )
    args = parser.parse_args(argv)

    if not QA_LOG.exists():
        print(f"qa log not found at {QA_LOG}; run tools/qa.py first.", file=sys.stderr)
        return 2

    qa_rows = _read_qa_log()
    features, features_by_nom = _load_features()

    attached_counts: dict[tuple[str, str], int] = {}
    for row in qa_rows:
        if row["status"] == "fail" or row["type"] != "vector":
            continue
        parsed = parse_filename(row["file"])
        if parsed is None:
            continue
        folder = DATA_DIR / row["dataset"]
        resolved = resolve_processed_paths(folder, row["file"])
        if not resolved:
            print(
                f"skip {row['file']}: no matching processed file "
                f"(checked language variants)",
                file=sys.stderr,
            )
            continue
        total = 0
        for src, resolved_name in resolved:
            resolved_parsed = parse_filename(resolved_name) or parsed
            count = _attach_vector(src, resolved_name, resolved_parsed, features_by_nom)
            attached_counts[(row["dataset"], resolved_name)] = count
            total += count
            print(f"attached {resolved_name}: {count} zones")
        attached_counts[(row["dataset"], row["file"])] = total

    BUILD_DIR.mkdir(exist_ok=True)
    n_matrices = _stage_matrices(qa_rows)
    geo = {"type": "FeatureCollection", "features": features}
    GEOJSON_OUT.write_text(json.dumps(geo), encoding="utf-8")

    manifest = _build_manifest(qa_rows, attached_counts)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print(
        f"wrote {GEOJSON_OUT.relative_to(REPO_ROOT)} "
        f"({len(features)} features, {GEOJSON_OUT.stat().st_size // 1024} KB)"
    )
    print(f"wrote {MANIFEST_OUT.relative_to(REPO_ROOT)}")
    print(f"staged {n_matrices} matrix file(s) under {MATRIX_DIR.relative_to(REPO_ROOT)}")

    if not args.skip_readme:
        try:
            _stamp_readme(manifest)
        except ValueError as exc:
            print(f"README stamp failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
