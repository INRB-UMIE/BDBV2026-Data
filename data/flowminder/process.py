"""Build a pairwise relocation matrix from the HDX Flowminder OD export.

Convention
----------
Processed row/column labels MUST match the canonical health-zone names defined by
``data/shapefiles/DRC_Health_zones.shp`` (field ``Nom``), using the same rules as
``tools.lib.schema``:

  - unique ``Nom`` values are used as-is (e.g. ``Bunia``, ``Goma``);
  - duplicate ``Nom`` across provinces are disambiguated as ``Nom (Province)``
    (e.g. ``Bili (Bas-Uele)``, ``Lubunga (Tshopo)``).

Resolution order for each raw Flowminder label:

  1. Strip HDX prefixes/suffixes (``kn Bunia Zone de Santé`` → ``Bunia``)
  2. ``data/aliases.csv`` (via ``to_canonical``) — shared repo aliases
  3. Structural variants — roman numerals (``Kalamu 1`` → ``Kalamu I``) and
     spaces → hyphens (``Kasa Vubu`` → ``Kasa-Vubu``)
  4. ``LOCAL_FIXUPS`` below — Flowminder typos / province disambiguation,
     each target verified against the shapefile at import time

Labels that still do not resolve are dropped; see ``zone_resolution_log.csv``.

Input (``raw/``):
  hdx_flowminder_relocations_march2026.csv

Output (``processed/``):
  flowminder__relocations__static.matrix.csv  (first column header ``nom``)

The matrix uses ``est_flows_2026_04`` — estimated relocations from 2026-03 to
2026-04 (latest month available in the HDX file at time of processing).

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
SHAPEFILE = REPO_ROOT / "data" / "shapefiles" / "DRC_Health_zones"
sys.path.insert(0, str(REPO_ROOT))

from tools.lib.schema import canonical_noms, to_canonical  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PROCESSED = HERE / "processed"

RAW_CSV = RAW / "hdx_flowminder_relocations_march2026.csv"
FLOW_COLUMN = "est_flows_2026_04"
OUTPUT_MATRIX = PROCESSED / "flowminder__relocations__static.matrix.csv"

# Province disambiguation for bare labels that collide in the shapefile.
DISAMBIGUATION: dict[str, str] = {
    "Lubunga": "Lubunga (Tshopo)",
    "Bili": "Bili (Bas-Uele)",
}

# HDX / Flowminder spelling variants verified against DRC_Health_zones.shp Nom.
TYPO_FIXUPS: dict[str, str] = {
    "Banzow Moke": "Banjow Moke",
    "Bena Tshadi": "Bena Tshiadi",
    "Bogosenubea": "Bogosenubia",
    "Busanga": "Bosanga",
    "Djalo Ndjeka": "Djalo Djeka",
    "Kabeya Kamwanga": "Kabeya Kamuanga",
    "Kimbao": "Kimbau",
    "Malemba Nkulu": "Malemba",
    "Mampoko": "Lolanga Mampoko",
    "Massa": "Masa",
    "Muanda": "Moanda",
    "Mweneditu": "Mwene Ditu",
    "Ruashi": "Rwashi",
    "Mongbwalu": "Mongbalu",
    "Makiso Kisangani": "Makiso-Kisangani",
    "Nia Nia": "Nia-Nia",
    "Kasa Vubu": "Kasa-Vubu",
    "Mont Ngafula 1": "Mont Ngafula I",
    "Mont Ngafula 2": "Mont Ngafula II",
    "Masina 1": "Masina I",
    "Masina 2": "Masina II",
    "Kalamu 1": "Kalamu I",
    "Kalamu 2": "Kalamu II",
    "Maluku 1": "Maluku I",
    "Maluku 2": "Maluku II",
    "Ngiri Ngiri": "Ngiri-Ngiri",
}

LOCAL_FIXUPS: dict[str, str] = {**DISAMBIGUATION, **TYPO_FIXUPS}

_ROMAN_RE = re.compile(r"^(.*) ([12])$")
_HDX_PREFIX_RE = re.compile(r"^[a-z]{2,3}\s+", re.IGNORECASE)
_HDX_SUFFIX_RE = re.compile(r"\s+Zone de Sant[eé]\s*$", re.IGNORECASE)
_HDX_DIGIT_ROMAN_RE = re.compile(r"\s+(\d)\s*$")
_REDACTED_RE = re.compile(r"^redacted\b", re.IGNORECASE)


def _validate_fixup_targets() -> None:
    canon = canonical_noms()
    for observed, target in LOCAL_FIXUPS.items():
        if target not in canon:
            raise ValueError(
                f"flowminder LOCAL_FIXUPS[{observed!r}] -> {target!r} "
                f"is not a canonical shapefile Nom (see {SHAPEFILE})"
            )


def strip_hdx_name(raw: str) -> str:
    """Normalize HDX health-zone labels to a bare zone name."""
    name = raw.strip()
    name = name.replace("Zone de SantÃ©", "Zone de Santé")
    name = _HDX_PREFIX_RE.sub("", name)
    name = _HDX_SUFFIX_RE.sub("", name)
    name = _HDX_DIGIT_ROMAN_RE.sub(
        lambda m: " " + ("I" if m.group(1) == "1" else "II"),
        name,
    )
    return name.strip()


def _structural_variants(label: str) -> list[str]:
    out: list[str] = []
    m = _ROMAN_RE.match(label)
    if m:
        base, digit = m.group(1), m.group(2)
        roman = "I" if digit == "1" else "II"
        out.append(f"{base} {roman}")
        out.append(f"{base}-{roman}")
    if " " in label:
        out.append(label.replace(" ", "-"))
    return out


def _resolve(label: str) -> str | None:
    stripped = label.strip()
    if not stripped:
        return None

    bare = strip_hdx_name(stripped)
    candidates = [bare, stripped]
    if bare in LOCAL_FIXUPS:
        candidates.insert(0, LOCAL_FIXUPS[bare])
    if stripped in LOCAL_FIXUPS:
        candidates.insert(0, LOCAL_FIXUPS[stripped])
    candidates.extend(_structural_variants(bare))

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        canonical = to_canonical(candidate)
        if canonical is not None:
            return canonical
    return None


def _parse_flow(value: str) -> float | None:
    text = value.strip()
    if not text or _REDACTED_RE.match(text):
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def build_matrix() -> tuple[Path, list[dict[str, str]]]:
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"flowminder: raw input not found: {RAW_CSV}")

    log: list[dict[str, str]] = []
    agg: dict[str, dict[str, float]] = {}
    zone_seen: set[str] = set()

    with RAW_CSV.open(newline="", encoding="utf-8-sig") as f_in:
        reader = csv.DictReader(f_in)
        if FLOW_COLUMN not in (reader.fieldnames or []):
            raise ValueError(f"flowminder: missing column {FLOW_COLUMN!r} in {RAW_CSV.name}")

        for row in reader:
            flow = _parse_flow(row.get(FLOW_COLUMN, ""))
            if flow is None:
                continue

            origin_raw = row.get("from_hz_name", "")
            dest_raw = row.get("to_hz_name", "")
            origin = _resolve(origin_raw)
            dest = _resolve(dest_raw)

            if origin is None:
                log.append(
                    {
                        "raw_label": origin_raw,
                        "role": "origin",
                        "action": "dropped",
                        "reason": "no shapefile Nom or alias match",
                    }
                )
                continue
            if dest is None:
                log.append(
                    {
                        "raw_label": dest_raw,
                        "role": "destination",
                        "action": "dropped",
                        "reason": "no shapefile Nom or alias match",
                    }
                )
                continue

            zone_seen.add(origin)
            zone_seen.add(dest)

            if origin not in agg:
                agg[origin] = {}
            agg[origin][dest] = agg[origin].get(dest, 0.0) + flow

    if not zone_seen:
        raise ValueError(f"flowminder: no relocations resolved from {RAW_CSV.name}")

    zone_order = sorted(zone_seen)
    for origin in list(agg.keys()):
        for zone in zone_order:
            agg[origin].setdefault(zone, 0.0)

    PROCESSED.mkdir(exist_ok=True)
    with OUTPUT_MATRIX.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["nom"] + zone_order)
        for origin in zone_order:
            row = agg.get(origin, {zone: 0.0 for zone in zone_order})
            writer.writerow([origin] + [row.get(dest, 0.0) for dest in zone_order])

    _assert_shapefile_convention(OUTPUT_MATRIX)
    return OUTPUT_MATRIX, log


def _assert_shapefile_convention(path: Path) -> None:
    """Every nom in a processed matrix must be a canonical shapefile label."""
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
    fields = ["raw_label", "role", "action", "reason"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(logs)
    return path


def main() -> int:
    _validate_fixup_targets()
    out, log = build_matrix()
    print(f"wrote {out.relative_to(REPO_ROOT)} ({out.stat().st_size} bytes)")
    if log:
        log_path = write_resolution_log(log)
        print(f"wrote {log_path.relative_to(REPO_ROOT)} ({len(log)} resolution events)")
    else:
        print("all raw labels resolved to shapefile canonical Nom")
    return 0


if __name__ == "__main__":
    sys.exit(main())
