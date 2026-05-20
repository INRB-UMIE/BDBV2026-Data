"""Canonical contract: zone identifiers, alias resolution, filename grammar.

Single source of truth shared by the QA runner, the GeoJSON builder, and every
dataset's process.py. Anything that needs to talk about a DRC health zone in
this repo flows through this module.

What lives here:
  - Paths to the repo root and the shapefile.
  - The list of canonical zone names (`Nom`) derived from the shapefile, with
    automatic disambiguation for any `Nom` that occurs in more than one
    province (currently `Bili` and `Lubunga`).
  - `to_canonical(name)`: resolves an observed name (canonical, alias, or
    unknown) to the canonical `Nom`, using `data/aliases.csv`.
  - `zscode_to_canonical(zscode)`: same idea, keyed by the shapefile's ZSCode.
  - `parse_filename(name)`: validates the contract for processed-file names of
    the form `<dataset>__<metric>__<resolution>[.matrix].csv`.
  - Enumerations used by QA: `VALID_RESOLUTIONS`, `VALID_RUNTIMES`,
    `REQUIRED_METADATA_FIELDS`.
"""

from __future__ import annotations

import csv
import functools
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import shapefile  # pyshp

REPO_ROOT = Path(__file__).resolve().parents[2]
SHAPEFILE = REPO_ROOT / "data" / "shapefiles" / "DRC_Health_zones"
ALIASES_CSV = REPO_ROOT / "data" / "aliases.csv"

VALID_RESOLUTIONS: frozenset[str] = frozenset(
    {"static", "daily", "weekly", "monthly", "yearly"}
)
VALID_RUNTIMES: frozenset[str] = frozenset({"none", "python", "R"})
REQUIRED_METADATA_FIELDS: tuple[str, ...] = (
    "source",
    "citation",
    "source_url",
    "retrieved_on",
    "license",
    "contact",
    "runtime",
)


@dataclass(frozen=True)
class Zone:
    canonical_nom: str
    zscode: str
    province: str
    raw_nom: str


@dataclass(frozen=True)
class ParsedFilename:
    dataset: str
    metric: str
    resolution: str
    kind: Literal["vector", "matrix"]


_FILENAME_RE = re.compile(
    r"^(?P<dataset>[a-z][a-z0-9_]*)"
    r"__(?P<metric>[a-z][a-z0-9_]*)"
    r"__(?P<resolution>" + "|".join(sorted(VALID_RESOLUTIONS)) + r")"
    r"(?P<matrix>\.matrix)?\.csv$"
)


@functools.lru_cache(maxsize=1)
def load_zones() -> list[Zone]:
    """Return one Zone per shapefile feature, in shapefile order.

    Build_geojson pairs this list element-wise with reader.shapes(), so the
    order MUST match the on-disk record order — don't sort.
    """
    reader = shapefile.Reader(str(SHAPEFILE))
    records = reader.records()
    nom_counts = Counter(rec["Nom"] for rec in records)
    zones: list[Zone] = []
    for rec in records:
        raw_nom = rec["Nom"]
        province = rec["PROVINCE"]
        canonical = raw_nom if nom_counts[raw_nom] == 1 else f"{raw_nom} ({province})"
        zones.append(
            Zone(
                canonical_nom=canonical,
                zscode=rec["ZSCode"],
                province=province,
                raw_nom=raw_nom,
            )
        )
    return zones


@functools.lru_cache(maxsize=1)
def canonical_noms() -> frozenset[str]:
    return frozenset(z.canonical_nom for z in load_zones())


@functools.lru_cache(maxsize=1)
def _zscode_index() -> dict[str, str]:
    return {z.zscode: z.canonical_nom for z in load_zones()}


@functools.lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    """observed_name -> canonical_nom, loaded from data/aliases.csv.

    Aliases whose canonical_nom is not in the current shapefile are dropped
    silently — they're a sign the shapefile changed under us, and surfacing
    them here would mask the real bug (data referring to a vanished zone).
    """
    canon = canonical_noms()
    index: dict[str, str] = {}
    if not ALIASES_CSV.exists():
        return index
    with ALIASES_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            observed = (row.get("observed_name") or "").strip()
            canonical = (row.get("canonical_nom") or "").strip()
            if observed and canonical and canonical in canon:
                index[observed] = canonical
    return index


def to_canonical(name: str | None) -> str | None:
    """Resolve an observed zone name to its canonical Nom, or None."""
    if not name:
        return None
    if name in canonical_noms():
        return name
    return _alias_index().get(name)


def zscode_to_canonical(zscode: str | None) -> str | None:
    if not zscode:
        return None
    return _zscode_index().get(zscode)


def parse_filename(name: str) -> ParsedFilename | None:
    m = _FILENAME_RE.match(name)
    if m is None:
        return None
    return ParsedFilename(
        dataset=m.group("dataset"),
        metric=m.group("metric"),
        resolution=m.group("resolution"),
        kind="matrix" if m.group("matrix") else "vector",
    )
