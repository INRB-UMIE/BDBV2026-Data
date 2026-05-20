# Province-grain support in the DRC data pipeline

**Date:** 2026-05-20
**Status:** Approved design, pending implementation plan
**Driver:** Some upstream sources (notably ACLED conflict aggregates) are only available at province (ADMIN1) grain, not at health-zone grain. Today these files cannot pass QA and cannot be merged into the build artifact, leaving the signal orphaned. This spec promotes province-grain to a first-class supported output of the pipeline.

## Goals

- Allow a contributor to add province-grain processed files to a dataset folder and have them validated by QA on the same footing as zone-grain files.
- Surface province-grain values inside the existing per-zone merged GeoJSON, with an explicit marker so consumers can tell true zone-resolution data from replicated province values.
- Do not break any existing zone-grain file, consumer, or build artifact.

## Non-goals

- Province-grain matrices. The filename slot `__province.matrix.csv` is reserved but not implemented; we will add it only when a real dataset needs it.
- Disaggregating province values down to zones with population weights or any other heuristic. Replication is the documented and only behavior.
- Replacing the ACLED placeholder with event-level data. That remains a separate future PR, tracked in `data/ACLED_conflict/metadata.yaml`.

## Data contract changes

### Filename pattern

Existing pattern:
```
<dataset>__<metric>__<resolution>.csv          (zone-grain vector)
<dataset>__<metric>__<resolution>.matrix.csv   (zone-grain matrix)
```

New pattern:
```
<dataset>__<metric>__<resolution>__province.csv   (province-grain vector)
```

The `__province` token is the trailing token before the `.csv` extension, mirroring how `.matrix.csv` extends the kind. Absence of the token implies zone-grain.

### File contents

A province-grain file:
- Uses a `province` column instead of `nom`.
- For non-static resolutions, carries the same date column as zone-grain files (one of `date`, `week_start`, `month_start`, `year`).
- Cells are non-negative numeric, same as today.
- Uniqueness: `(province)` for static, `(province, date)` for time-series.

`metadata.yaml` is unchanged — no new required field. The grain is fully determined by the filename.

## Canonical provinces & aliases

- **Canonical list:** the distinct values of the `PROVINCE` attribute in `data/shapefiles/DRC_Health_zones.shp`. Exposed via a new `tools.lib.schema.canonical_provinces()` function, parallel to `canonical_noms()`.
- **Alias file:** a new file `data/province_aliases.csv` with the same two-column shape as `data/aliases.csv` (`observed_name,canonical_province`). Used to resolve spelling variants like `Nord Kivu` vs `Nord-Kivu`.
- **Resolver:** new `tools.lib.schema.to_canonical_province(name) -> str | None`, mirroring `to_canonical()`.

## QA changes (`tools/qa.py`)

- `tools.lib.schema.parse_filename()` gains a new field `grain ∈ {"zone", "province"}` on its result object. Existing fields (`dataset`, `metric`, `resolution`, `kind`) are unchanged.
- `qa_folder()` dispatches to a new `qa_province()` function whenever `parsed.grain == "province"`. Existing dispatch to `qa_vector()` / `qa_matrix()` is unchanged for zone-grain files.
- `qa_province()` is structurally a copy of `qa_vector()` with two differences:
  1. Required join column is `province`, not `nom`.
  2. Each row's province is resolved via `to_canonical_province()`. Unresolved provinces produce the same `"N rows with unresolved province (sample: ...)"` reason pattern as the existing nom check.
- The `qa_log.csv` row shape is unchanged. `n_zones_covered` is reinterpreted as "n entities covered" for province-grain rows (i.e. number of distinct canonical provinces seen). The per-dataset markdown report will explicitly label the grain in the section header for each file.
- Matrix support: `parse_filename()` recognises `__province.matrix.csv` and returns `grain="province"`, but `qa_matrix()` will refuse it with `"province-grain matrices not yet supported"` until a real dataset needs it. Reserves the namespace cleanly.

## Build pipeline changes (`tools/build_geojson.py`)

- Zone→province lookup is built once from the shapefile during the initial pass that loads geometries.
- For each QA-passing province-grain vector file:
  1. Read the CSV; for each `(province, [date,] value_cols...)` row, look up the list of zones in that province.
  2. For each constituent zone, write the value dict into `feature.properties.<dataset>.<metric>`, with `_grain: "province"` added as a key inside that dict. Time-series files still get `_date: <ISO>` alongside.
- `build/long/<dataset>__<metric>.csv` for a province-grain file keeps a `province` column (no faked `nom` column). Consumers reading the long-form CSV see the true grain.
- `manifest.json` gains a per-file `grain` field, e.g.:
  ```json
  {"file": "acled_conflict__events__weekly__province.csv", "grain": "province", "resolution": "weekly", ...}
  ```

### Marker placement in the GeoJSON

The `_grain` key sits **per metric inside the property dict**, not per dataset and not per feature:

```jsonc
"acled_conflict": {
  "events": {"events": 5, "_grain": "province", "_date": "2026-05-02"}
}
```

- Absence of `_grain` means zone-grain (the default) — so all existing zone-grain consumers and outputs are unchanged.
- Per-metric placement allows a single dataset to mix grains (e.g. one feed at zone grain, another at province grain) without forcing a folder-level choice.

### Replication semantics, called out

Province values are **replicated**, not split. A consumer summing across zones in a province will double-count. This will be documented in:

- `README.md` (data-contract section).
- The per-dataset QA report for any folder that produces province-grain output.

## Out-of-scope clarifications

- The current ACLED placeholder is not promoted to a real output in this spec. It remains a placeholder. This spec creates the infrastructure that a future contributor can use to add real province-grain files to `data/ACLED_conflict/processed/` (or to a different dataset) without further pipeline changes.
- `tools/lib/schema.py` is currently missing from the repo (separate `lib/` gitignore issue, already fixed in `.gitignore` on 2026-05-20). Its creation is a precondition for this work; the implementation plan must handle it.

## Risks and trade-offs

- **Replication is honest only if consumers check `_grain`.** A naïve consumer treating `acled_conflict.events` as zone-resolution data will be misled. Mitigation: explicit documentation and per-property marker.
- **Two-source-of-truth risk for provinces.** The shapefile is authoritative; `data/province_aliases.csv` exists only to normalise observed spellings. If anyone adds a province name to `province_aliases.csv` that isn't in the shapefile's `PROVINCE` set, QA should surface that as a configuration error (tested at unit-test level).
- **Reserving `__province.matrix.csv` without implementing it.** This is a deliberate choice to keep the namespace clean. The risk is that the eventual matrix design ends up incompatible. Acceptable risk: the namespace is unambiguous, and changing later costs only one filename rename.

## Test plan (sketch)

- Unit tests: `parse_filename()` returns the correct `grain` for both zone-grain and province-grain filenames, including the matrix variant; `to_canonical_province()` resolves both canonical and alias spellings, returns None for garbage.
- QA tests: a fixture province-grain CSV with one valid row, one unresolved province, one duplicate `(province, date)` key — assert the QA result has the expected reasons.
- Build tests: a fixture province-grain CSV is replicated across all zones in each named province; output property dicts carry `_grain: "province"`; zone-grain files in the same build are unaffected.
