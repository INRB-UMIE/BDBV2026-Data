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
  - `NON_GEOGRAPHIC_NOMS` / `resolve_vector_nom(name)`: sitrep labels that may
    appear in vector `nom` but are not shapefile zones (excluded from GeoJSON).
  - Province roll-ups: `nom` may be a canonical `PROVINCE` name (or alias in
    `data/province_aliases.csv`). QA passes; GeoJSON build broadcasts to all
    zones in that province (same pattern as national `DRC` rows).
    Three provinces — Kinshasa, Lualaba, Tshopo — share a name with one of
    their own health zones. Zone identity always wins on that collision, so a
    genuine province-wide roll-up for one of those three MUST use the
    `"<Province> (province)"` form (see `PROVINCE_ROLLUP_SUFFIX`) — a bare
    `"Tshopo"` always resolves to the health zone, never the province.
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
PROVINCE_ALIASES_CSV = REPO_ROOT / "data" / "province_aliases.csv"

VALID_RESOLUTIONS: frozenset[str] = frozenset(
    {"static", "daily", "weekly", "monthly", "yearly"}
)
LANGUAGE_SUFFIXES: tuple[str, ...] = ("_en", "_fr")
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

# Vector `nom` values that are not MoH health zones (e.g. INSP sitrep roll-ups).
# Allowed in processed CSVs; QA passes; GeoJSON build skips these rows.
NON_GEOGRAPHIC_NOMS: frozenset[str] = frozenset({"Sans Fiche", "NA"})

# Republic-wide roll-up row in `national_*` vector files (one row per date).
NATIONAL_ROLLUP_NOM: str = "DRC"

# Required for a province-wide roll-up whose province name collides with a
# health zone Nom (currently Kinshasa, Lualaba, Tshopo): write the `nom` value
# as f"{province}{PROVINCE_ROLLUP_SUFFIX}", e.g. "Tshopo (province)". Optional
# (but harmless) on any other province. See resolve_vector_nom.
PROVINCE_ROLLUP_SUFFIX: str = " (province)"


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
def canonical_provinces() -> frozenset[str]:
    return frozenset(z.province for z in load_zones())


@functools.lru_cache(maxsize=1)
def zones_by_province() -> dict[str, list[str]]:
    """Map shapefile PROVINCE -> canonical zone noms in that province."""
    by_prov: dict[str, list[str]] = {}
    for z in load_zones():
        by_prov.setdefault(z.province, []).append(z.canonical_nom)
    return by_prov


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


@functools.lru_cache(maxsize=1)
def _province_alias_index() -> dict[str, str]:
    """observed_name -> canonical PROVINCE, loaded from data/province_aliases.csv."""
    canon = canonical_provinces()
    index: dict[str, str] = {}
    if not PROVINCE_ALIASES_CSV.exists():
        return index
    with PROVINCE_ALIASES_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            observed = (row.get("observed_name") or "").strip()
            canonical = (row.get("canonical_province") or "").strip()
            if observed and canonical and canonical in canon:
                index[observed] = canonical
    return index


def to_canonical_province(name: str | None) -> str | None:
    """Resolve an observed province label to shapefile PROVINCE, or None."""
    if not name:
        return None
    label = name.strip()
    if label in canonical_provinces():
        return label
    return _province_alias_index().get(label)


def to_canonical(name: str | None) -> str | None:
    """Resolve an observed zone name to its canonical Nom, or None."""
    if not name:
        return None
    if name in canonical_noms():
        return name
    return _alias_index().get(name)


def is_non_geographic_nom(name: str | None) -> bool:
    """True if `name` is a permitted non-zone label (not embedded in GeoJSON)."""
    if not name:
        return False
    return name.strip() in NON_GEOGRAPHIC_NOMS


def is_national_rollup_nom(name: str | None) -> bool:
    """True if `name` is the national roll-up label (`DRC`)."""
    if not name:
        return False
    return name.strip() == NATIONAL_ROLLUP_NOM


def _province_rollup_candidate(label: str) -> str | None:
    """If `label` uses the explicit "<Province>{PROVINCE_ROLLUP_SUFFIX}" form,
    return the bit before the suffix (unresolved), else None."""
    if not label.endswith(PROVINCE_ROLLUP_SUFFIX):
        return None
    return label[: -len(PROVINCE_ROLLUP_SUFFIX)].strip()


def is_province_rollup_nom(name: str | None) -> bool:
    """True if `name` is a province-wide roll-up label.

    Two forms:
      - A canonical shapefile PROVINCE that is NOT also a canonical zone Nom
        (the common case — e.g. "Ituri", "Nord-Kivu").
      - The explicit "<Province> (province)" disambiguation form, required
        when the province name collides with a zone Nom (Kinshasa, Lualaba,
        Tshopo — see resolve_vector_nom / PROVINCE_ROLLUP_SUFFIX).

    Zone identity wins on an unmarked collision — otherwise a dataset's
    per-zone row for e.g. the "Tshopo" health zone gets misread as a
    province-wide roll-up and its value is broadcast over every zone in
    Tshopo province, clobbering their real per-zone values.
    """
    if not name:
        return False
    label = name.strip()
    candidate = _province_rollup_candidate(label)
    if candidate is not None:
        return to_canonical_province(candidate) is not None
    return label in canonical_provinces() and label not in canonical_noms()


def province_name_from_rollup_nom(name: str) -> str | None:
    """Bare shapefile PROVINCE for a name that is_province_rollup_nom() has
    already confirmed is a roll-up (strips the disambiguation marker, and
    resolves province aliases, if present)."""
    label = name.strip()
    candidate = _province_rollup_candidate(label)
    return to_canonical_province(candidate if candidate is not None else label)


def counts_as_zone_coverage(resolved: str | None) -> bool:
    """True when a resolved vector `nom` is a health zone (for QA zone counts)."""
    if not resolved:
        return False
    return (
        not is_non_geographic_nom(resolved)
        and not is_national_rollup_nom(resolved)
        and not is_province_rollup_nom(resolved)
    )


def resolve_vector_nom(name: str | None) -> str | None:
    """Resolve `nom` for vector QA/build: zone, roll-up label, or None.

    The explicit "<Province> (province)" form is checked first and always
    resolves to a province roll-up (see PROVINCE_ROLLUP_SUFFIX). Otherwise,
    zone identity is checked before province: Kinshasa, Lualaba, and Tshopo
    are each both a health zone and their own province's name, so a bare
    occurrence of one of those strings resolves to the specific zone, not a
    province-wide roll-up (see is_province_rollup_nom)."""
    if not name:
        return None
    label = name.strip()
    if label in NON_GEOGRAPHIC_NOMS or label == NATIONAL_ROLLUP_NOM:
        return label
    candidate = _province_rollup_candidate(label)
    if candidate is not None:
        province = to_canonical_province(candidate)
        return f"{province}{PROVINCE_ROLLUP_SUFFIX}" if province is not None else None
    zone = to_canonical(label)
    if zone is not None:
        return zone
    return to_canonical_province(label)


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


def split_language_suffix(metric: str) -> tuple[str, str | None]:
    """Return (base_metric, language) where language is 'en'/'fr' or None."""
    for suffix in LANGUAGE_SUFFIXES:
        if metric.endswith(suffix):
            return metric[: -len(suffix)], suffix[1:]
    return metric, None


def build_processed_filename(
    dataset: str,
    metric: str,
    resolution: str,
    *,
    kind: Literal["vector", "matrix"] = "vector",
    language: str | None = None,
) -> str:
    """Contract filename for a processed CSV (optional ``_en``/``_fr`` on metric)."""
    metric_part = f"{metric}_{language}" if language else metric
    matrix_part = ".matrix" if kind == "matrix" else ""
    return f"{dataset}__{metric_part}__{resolution}{matrix_part}.csv"


def language_variant_filenames(file_name: str) -> list[str]:
    """If ``file_name`` has no language suffix, return ``_en``/``_fr`` variants."""
    parsed = parse_filename(file_name)
    if parsed is None:
        return []
    base_metric, language = split_language_suffix(parsed.metric)
    if language is not None:
        return []
    return [
        build_processed_filename(
            parsed.dataset,
            base_metric,
            parsed.resolution,
            kind=parsed.kind,
            language=lang,
        )
        for lang in ("en", "fr")
    ]


def resolve_processed_paths(folder: Path, file_name: str) -> list[tuple[Path, str]]:
    """Resolve a QA-log filename to on-disk processed CSV(s).

    Returns one or more ``(path, filename)`` pairs. When the requested name is
    missing but ``_en``/``_fr`` suffixed siblings exist, both are returned so
    bilingual outputs can be embedded in GeoJSON.
    """
    processed = folder / "processed"
    exact = processed / file_name
    if exact.is_file():
        return [(exact, file_name)]
    found: list[tuple[Path, str]] = []
    for variant in language_variant_filenames(file_name):
        candidate = processed / variant
        if candidate.is_file():
            found.append((candidate, variant))
    return found
