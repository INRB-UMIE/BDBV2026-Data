"""Map cross-border PoEs to DRC health zones and aggregate passenger volumes.

Reads:
  raw/cross-border.csv       Province, PoE, sitreps, mean_weekly_passengers, mean_daily_passengers
  poe_coordinates.csv        hand-curated lat/lon per PoE (Uganda-side OSM points)

Writes:
  processed/cross_border__poe_passengers__static.csv  nom, n_poes, mean_daily_passengers,
                                                       mean_weekly_passengers, poe_names

Each PoE is mapped to the DRC health zone whose polygon is *nearest* in WGS84
degrees (most PoE coords here are on the Uganda side of the border, so nearest-zone
correctly picks the DRC zone the crossing serves). Aggregation is sum-per-zone.

Run from repo root:
    python data/cross-border-movements/process.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import shapefile  # pyshp  # noqa: E402
from shapely.geometry import Point, shape  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from tools.lib.schema import SHAPEFILE, load_zones  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW_CSV = HERE / "raw" / "cross-border.csv"
POE_CSV = HERE / "poe_coordinates.csv"
OUT_CSV = HERE / "processed" / "cross_border__poe_passengers__static.csv"


def _load_zone_geometries() -> list[tuple[str, "shape"]]:
    reader = shapefile.Reader(str(SHAPEFILE))
    zones = load_zones()
    geoms: list[tuple[str, "shape"]] = []
    for zone, sh in zip(zones, reader.shapes()):
        geom = shape(sh.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        geoms.append((zone.canonical_nom, geom))
    return geoms


def _nearest_zone(point: Point, geoms: list[tuple[str, "shape"]], tree: STRtree) -> str:
    candidate_idxs = tree.query_nearest(point, exclusive=False)
    best_nom = None
    best_dist = float("inf")
    for idx in candidate_idxs:
        nom, geom = geoms[idx]
        dist = point.distance(geom)
        if dist < best_dist:
            best_dist = dist
            best_nom = nom
    if best_nom is None:
        raise RuntimeError(f"No zone found near {point}")
    return best_nom


def _load_poe_coords() -> dict[str, tuple[float, float]]:
    coords: dict[str, tuple[float, float]] = {}
    with POE_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            coords[row["poe_name"].strip()] = (float(row["latitude"]), float(row["longitude"]))
    return coords


def _resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    """Map our internal keys to the real header names in raw/cross-border.csv.

    Source headers have inconsistent casing, parenthesised tokens, and a
    sentence-long passenger column. Match on a normalised (lowercased,
    whitespace-collapsed) form so upstream cosmetic tweaks don't silently
    break the build; if a column genuinely disappears, fail with a clear
    message naming what we expected to find.
    """
    norm = {" ".join(h.lower().split()): h for h in fieldnames}
    needed = {
        "poe": "point of entry (poe)",
        "weekly": "mean reported weekly passengers entering uganda through this poe",
        "daily": "mean daily passengers",
    }
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for key, normalised_name in needed.items():
        if normalised_name in norm:
            resolved[key] = norm[normalised_name]
        else:
            missing.append(normalised_name)
    if missing:
        raise KeyError(
            f"cross-border: raw/cross-border.csv is missing expected columns "
            f"(normalised): {missing}. Available: {list(fieldnames)}"
        )
    return resolved


def _load_passengers() -> list[dict]:
    with RAW_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = _resolve_columns(reader.fieldnames or [])
        return [
            {
                "poe": r[cols["poe"]].strip(),
                "weekly": float(r[cols["weekly"]]),
                "daily": float(r[cols["daily"]]),
            }
            for r in reader
        ]


def main() -> int:
    coords = _load_poe_coords()
    rows = _load_passengers()

    geoms = _load_zone_geometries()
    tree = STRtree([g for _, g in geoms])

    per_zone: dict[str, dict] = defaultdict(lambda: {
        "n_poes": 0,
        "mean_daily_passengers": 0.0,
        "mean_weekly_passengers": 0.0,
        "poe_names": [],
    })
    unmatched: list[str] = []
    for r in rows:
        poe = r["poe"]
        if poe not in coords:
            unmatched.append(poe)
            continue
        lat, lon = coords[poe]
        nom = _nearest_zone(Point(lon, lat), geoms, tree)
        per_zone[nom]["n_poes"] += 1
        per_zone[nom]["mean_daily_passengers"] += r["daily"]
        per_zone[nom]["mean_weekly_passengers"] += r["weekly"]
        per_zone[nom]["poe_names"].append(poe)
    if unmatched:
        raise RuntimeError(f"PoEs missing from poe_coordinates.csv: {unmatched}")

    OUT_CSV.parent.mkdir(exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nom", "n_poes", "mean_daily_passengers", "mean_weekly_passengers", "poe_names"])
        for nom in sorted(per_zone):
            d = per_zone[nom]
            w.writerow([
                nom, d["n_poes"],
                f"{d['mean_daily_passengers']:.0f}",
                f"{d['mean_weekly_passengers']:.0f}",
                "|".join(d["poe_names"]),
            ])
    print(f"wrote {OUT_CSV.relative_to(REPO_ROOT)} ({len(per_zone)} zones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
