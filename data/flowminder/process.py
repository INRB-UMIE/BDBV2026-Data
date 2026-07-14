"""Build April 2026 Flowminder relocation OD matrices from the HDX long table.

Convention
----------
Processed row/column labels MUST match the canonical health-zone names defined by
``data/shapefiles/DRC_Health_zones.shp`` (field ``Nom``), using the same rules as
``tools.lib.schema``:

  - unique ``Nom`` values are used as-is;
  - duplicate ``Nom`` across provinces are already disambiguated in the shapefile
    as ``Nom (Province)`` (e.g. ``Lubunga (Tshopo)``, ``Bili (Bas-Uele)``).

Name resolution for each Flowminder label:

  1. Strip the ``{prov_code} … Zone de Santé`` wrapper around ``from_hz_name`` /
     ``to_hz_name`` (e.g. ``tp Lubunga Zone de Santé`` → ``Lubunga``).
  2. Province-aware disambiguation for bare ``Lubunga`` / ``Bili`` using
     ``from_province_name`` / ``to_province_name``.
  3. Direct shapefile ``Nom`` match, then ``data/aliases.csv`` via ``to_canonical``
     (includes the 2026-07 shapefile spelling migration).
  4. Space ↔ hyphen structural variants.

Only ``est_flows_2026_04`` is written into the matrices. Companion
``est_flows_2026_04_LB`` / ``_UB`` columns are ignored. Cells that Flowminder
marks as ``redacted (count <15)`` are written as empty (missing), not zero.

Inputs (``raw/``):
  drc-estimated-relocations-2020_03-2026_04-v2.0-external.csv
  drc-estimated-relocations-2020_03-2026_04-v2.0-variable-list.csv  (column docs)

Outputs (``processed/``):
  flowminder__outflow_202604__static.matrix.csv   # origin → destination (April HDX)
  flowminder__inflow_202604__static.matrix.csv    # destination ← origin (transpose)

Also retained (not rewritten by this script):
  flowminder__outflow__static.matrix.csv          # March 2026 PDF provincial extract
  flowminder__inflow__static.matrix.csv

Run from the data repository root:
    python -m data.flowminder.process
or:
    python data/flowminder/process.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.lib.schema import canonical_noms, to_canonical  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PROCESSED = HERE / "processed"
SHAPEFILE_RENAME_CSV = (
    REPO_ROOT / "data" / "shapefiles" / "shapefilechange_oldnames_newnames.csv"
)

RAW_EXTERNAL = RAW / "drc-estimated-relocations-2020_03-2026_04-v2.0-external.csv"
FLOW_COL = "est_flows_2026_04"
METRIC_TAG = "202604"

# Bare duplicate noms → canonical Nom (Province), keyed by Flowminder province.
LUBUNGA_BY_PROVINCE: dict[str, str] = {
    "Tshopo": "Lubunga (Tshopo)",
    "Kasaï-Central": "Lubunga (Kasaï-Central)",
    "Kasai-Central": "Lubunga (Kasaï-Central)",
}
BILI_BY_PROVINCE: dict[str, str] = {
    "Bas-Uele": "Bili (Bas-Uele)",
    "Nord-Ubangi": "Bili (Nord-Ubangi)",
}

_ZONE_LABEL_RE = re.compile(
    r"^[a-z]{2}\s+(.+?)\s+Zone de Santé$",
    re.IGNORECASE,
)
_REDACTED_RE = re.compile(r"redacted", re.IGNORECASE)

# March 2026 PDF-extract matrices (kept alongside April HDX snapshots).
MARCH_PROCESSED = (
    "flowminder__inflow__static.matrix.csv",
    "flowminder__outflow__static.matrix.csv",
)


def _load_shapefile_rename_map() -> dict[str, str]:
    """old_nom → new_nom for imperfect matches after the 2026-07 shapefile update."""
    if not SHAPEFILE_RENAME_CSV.exists():
        return {}
    out: dict[str, str] = {}
    with SHAPEFILE_RENAME_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            old = (row.get("old_nom") or "").strip()
            new = (row.get("new_nom") or "").strip()
            if old and new and old != new:
                out[old] = new
    return out


def _strip_flowminder_label(label: str) -> str:
    text = label.strip()
    m = _ZONE_LABEL_RE.match(text)
    return m.group(1).strip() if m else text


def _structural_variants(label: str) -> list[str]:
    out: list[str] = []
    if " " in label:
        out.append(label.replace(" ", "-"))
    if "-" in label:
        out.append(label.replace("-", " "))
    # Arabic ↔ Roman numerals used in older extracts.
    for digit, roman in (("1", "I"), ("2", "II")):
        if label.endswith(f" {digit}"):
            base = label[: -len(digit) - 1]
            out.append(f"{base} {roman}")
            out.append(f"{base}-{roman}")
        if label.endswith(f" {roman}"):
            base = label[: -len(roman) - 1]
            out.append(f"{base} {digit}")
            out.append(f"{base}-{digit}")
    return out


class ZoneResolver:
    def __init__(self) -> None:
        self.canon = canonical_noms()
        self.rename = _load_shapefile_rename_map()
        for target in (
            *LUBUNGA_BY_PROVINCE.values(),
            *BILI_BY_PROVINCE.values(),
            *self.rename.values(),
        ):
            if target not in self.canon:
                raise ValueError(
                    f"flowminder: expected canonical Nom {target!r} missing from shapefile"
                )

    def resolve(self, raw_label: str, province: str) -> str | None:
        name = _strip_flowminder_label(raw_label)
        province = province.strip()

        if name == "Lubunga":
            target = LUBUNGA_BY_PROVINCE.get(province)
            if target is not None:
                return target
        if name == "Bili":
            target = BILI_BY_PROVINCE.get(province)
            if target is not None:
                return target

        candidates = [name]
        if name in self.rename:
            candidates.append(self.rename[name])
        candidates.extend(_structural_variants(name))

        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate in self.canon:
                return candidate
            matched = to_canonical(candidate)
            if matched is not None:
                return matched
        return None


def _parse_flow(raw: str) -> float | None:
    """Return a float flow, None for missing/redacted (empty matrix cell)."""
    text = (raw or "").strip()
    if not text or _REDACTED_RE.search(text):
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value < 0:
        raise ValueError(f"negative flow value: {value}")
    return value


def _write_matrix(
    path: Path,
    zones: list[str],
    cells: dict[tuple[str, str], float | None],
) -> None:
    """Write snapshot matrix; missing/redacted → empty cell, else number or 0."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nom"] + zones)
        for origin in zones:
            row: list[object] = [origin]
            for dest in zones:
                key = (origin, dest)
                if key not in cells:
                    row.append(0.0)
                elif cells[key] is None:
                    row.append("")
                else:
                    value = cells[key]
                    # Keep integers clean when Flowminder supplies whole counts.
                    row.append(int(value) if value == int(value) else value)
            w.writerow(row)


def _assert_shapefile_convention(path: Path) -> None:
    canon = canonical_noms()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        bad = [label for label in header if label != "nom" and label not in canon]
        for row in reader:
            if row and row[0] not in canon:
                bad.append(row[0])
    if bad:
        sample = ", ".join(sorted(set(bad))[:10])
        raise ValueError(
            f"flowminder: {path.name} contains non-canonical zone names: {sample}"
        )


def write_resolution_log(logs: list[dict[str, str]]) -> Path:
    path = HERE / "zone_resolution_log.csv"
    fields = ["raw_label", "province", "role", "action", "resolved_nom", "reason"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(logs)
    return path


def build_april_2026_matrices(
    resolver: ZoneResolver,
) -> tuple[Path, Path, list[dict[str, str]], dict[str, int]]:
    if not RAW_EXTERNAL.exists():
        raise FileNotFoundError(f"Missing raw input: {RAW_EXTERNAL}")

    outflow: dict[tuple[str, str], float | None] = {}
    zones_seen: set[str] = set()
    logs: list[dict[str, str]] = []
    stats = {
        "rows": 0,
        "numeric": 0,
        "redacted_or_empty": 0,
        "dropped_unresolved": 0,
    }

    with RAW_EXTERNAL.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or FLOW_COL not in reader.fieldnames:
            raise ValueError(
                f"flowminder: expected column {FLOW_COL!r} in {RAW_EXTERNAL.name}"
            )
        for row in reader:
            stats["rows"] += 1
            from_raw = (row.get("from_hz_name") or "").strip()
            to_raw = (row.get("to_hz_name") or "").strip()
            from_prov = (row.get("from_province_name") or "").strip()
            to_prov = (row.get("to_province_name") or "").strip()

            origin = resolver.resolve(from_raw, from_prov)
            dest = resolver.resolve(to_raw, to_prov)

            if origin is None:
                stats["dropped_unresolved"] += 1
                logs.append(
                    {
                        "raw_label": from_raw,
                        "province": from_prov,
                        "role": "origin",
                        "action": "dropped",
                        "resolved_nom": "",
                        "reason": "no shapefile Nom or alias match",
                    }
                )
                continue
            if dest is None:
                stats["dropped_unresolved"] += 1
                logs.append(
                    {
                        "raw_label": to_raw,
                        "province": to_prov,
                        "role": "destination",
                        "action": "dropped",
                        "resolved_nom": "",
                        "reason": "no shapefile Nom or alias match",
                    }
                )
                continue

            zones_seen.add(origin)
            zones_seen.add(dest)
            value = _parse_flow(row.get(FLOW_COL, ""))
            key = (origin, dest)
            if value is None:
                stats["redacted_or_empty"] += 1
                # Keep an explicit redacted marker unless a numeric value arrives later.
                if key not in outflow:
                    outflow[key] = None
                continue

            stats["numeric"] += 1
            existing = outflow.get(key)
            if key not in outflow or existing is None:
                outflow[key] = value
            else:
                outflow[key] = existing + value

    zones = sorted(zones_seen)
    inflow = {(dest, origin): value for (origin, dest), value in outflow.items()}

    PROCESSED.mkdir(parents=True, exist_ok=True)
    outflow_path = PROCESSED / f"flowminder__outflow_{METRIC_TAG}__static.matrix.csv"
    inflow_path = PROCESSED / f"flowminder__inflow_{METRIC_TAG}__static.matrix.csv"
    _write_matrix(outflow_path, zones, outflow)
    _write_matrix(inflow_path, zones, inflow)
    _assert_shapefile_convention(outflow_path)
    _assert_shapefile_convention(inflow_path)

    stats["n_zones"] = len(zones)
    stats["n_directed_edges_stored"] = len(outflow)
    return outflow_path, inflow_path, logs, stats


def main() -> int:
    resolver = ZoneResolver()
    for name in MARCH_PROCESSED:
        path = PROCESSED / name
        if not path.exists():
            print(
                f"warning: March PDF matrix missing at {path.relative_to(REPO_ROOT)}; "
                "restore from git if it should ship alongside April outputs",
                file=sys.stderr,
            )
    outflow_path, inflow_path, logs, stats = build_april_2026_matrices(resolver)
    for path in (outflow_path, inflow_path):
        print(f"wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size} bytes)")
    print(
        "april 2026 stats: "
        f"rows={stats['rows']} numeric={stats['numeric']} "
        f"redacted_or_empty={stats['redacted_or_empty']} "
        f"dropped={stats['dropped_unresolved']} "
        f"zones={stats['n_zones']} edges={stats['n_directed_edges_stored']}"
    )
    if logs:
        log_path = write_resolution_log(logs)
        print(
            f"wrote {log_path.relative_to(REPO_ROOT)} "
            f"({len(logs)} unresolved label events)"
        )
    else:
        print("all raw labels resolved to shapefile canonical Nom")
        stale = HERE / "zone_resolution_log.csv"
        if stale.exists():
            stale.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
