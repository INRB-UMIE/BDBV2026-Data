# Quality assurance and testing

This folder holds **machine-readable QA logs** and **human-readable per-dataset reports** produced by the data pipeline. Together with the unit tests in `tests/`, these checks gate every pull request and every automated release before new `build/` artifacts are published.

The QA runner lives in [`tools/qa.py`](../tools/qa.py). The shared contract (zone names, filename grammar, metadata fields) is defined in [`tools/lib/schema.py`](../tools/lib/schema.py).

---

## Overview: two layers of checks

| Layer | Command | When it runs | What it validates |
|-------|---------|--------------|-------------------|
| **Unit tests** | `python -m pytest tests/ -v` | PR CI (`.github/workflows/qa.yml`); locally before opening a PR | Python helpers: schema parsing, QA edge cases, GeoJSON build behaviour, release/publish tooling, selected dataset `process.py` scripts |
| **Dataset QA** | `python -m tools.qa` | PR CI; release workflow; locally before opening a PR | Every folder under `data/` (except `shapefiles/`): `metadata.yaml`, processed CSVs, naming contract, zone resolution, matrix/vector structure |

Both must pass before a PR can merge. The release workflow runs QA again immediately before building GeoJSON and packing a release — a merge to `main` never ships stale or unchecked data.

```mermaid
flowchart TD
    PR[Contributor opens PR touching data/**] --> QA_WF[qa.yml: pytest + tools.qa]
    QA_WF -->|fail| BlockPR[PR blocked]
    QA_WF -->|pass| Merge[Admin merges to main]
    Merge --> Rel[release.yml]
    Rel --> Skip{Commit has<br/>[skip release]?}
    Skip -->|yes| End[No build]
    Skip -->|no| RunQA[tools.qa]
    RunQA -->|fail| FailRel[Release aborted]
    RunQA -->|pass| Build[tools.build_geojson]
    Build --> Pack[tools.release]
    Pack --> Commit[Commit build/ + qa/ + README]
    Commit --> Publish[tools.publish + dashboard dispatch]
```

---

## When QA runs

### Pull requests (merge gate)

Workflow: [`.github/workflows/qa.yml`](../.github/workflows/qa.yml)

Triggers on changes to `data/**`, `tools/**`, `tests/**`, or the workflow file itself (on PRs and on pushes to `main`).

Steps:

1. Checkout (with Git LFS)
2. `pip install -r tools/requirements.txt`
3. `python -m pytest tests/ -v`
4. `python -m tools.qa`
5. Upload `qa/` as a CI artifact (`qa-logs`) — useful when debugging a failing PR without cloning locally

**Exit code:** `tools.qa` returns `1` if any artifact has status `fail`. Warnings do not block CI.

### Releases (build gate)

Workflow: [`.github/workflows/release.yml`](../.github/workflows/release.yml)

Triggers when `data/**` changes on `main` (or via manual *Run workflow*).

After optional `[skip release]` check and description extraction from the merged PR:

1. `python -m tools.qa` — **must pass with zero failures**
2. `python -m tools.build_geojson` — consumes `qa/qa_log.csv`
3. `python -m tools.release` — preflight re-checks that `qa_log.csv` has no failures
4. Commit `build/`, `qa/qa_log.csv`, `qa/matrix_log.csv`, `qa/reports/`, and `README.md` back to `main`
5. `python -m tools.publish` — GitHub Release + dashboard rebuild dispatch

The release workflow's commit-back uses `[skip release][skip ci]` so it does not retrigger itself or the PR QA workflow.

---

## What `tools.qa` checks

For each dataset folder under `data/` (excluding `shapefiles/`):

### 1. Metadata (`metadata.yaml`)

Required fields (enforced by QA and documented in `tools/lib/schema.py`):

- `source`, `citation`, `source_url`, `retrieved_on`, `license`, `contact`, `runtime`

Additional rules:

- `runtime` must be one of `none`, `python`, `R`
- `retrieved_on` must be a valid ISO date (`YYYY-MM-DD`)

### 2. Folder structure

- Missing `processed/` → **warn** (placeholder dataset, e.g. `ACLED_conflict`)
- Empty `processed/` → **warn**

### 3. Filename contract

Every file in `processed/` must match:

```
<dataset>__<metric>__<resolution>[.matrix].csv
```

- `dataset`, `metric`: lowercase snake_case, starting with a letter
- `resolution`: `static`, `daily`, `weekly`, `monthly`, or `yearly`
- `.matrix.csv` suffix → matrix (origin–destination table)
- `.csv` suffix → vector (one row per zone, or per zone × date)

Invalid names → **fail**.

### 4. Vector files (`.csv`, not `.matrix.csv`)

| Check | On failure |
|-------|------------|
| Readable UTF-8 CSV with a `nom` column | **fail** |
| Time-series resolution requires a date column (`date`, `week_start`, `month_start`, or `year`) | **fail** |
| Each `nom` resolves to a canonical health-zone name (via shapefile + `data/aliases.csv`), or is an allowed non-geographic label (`Sans Fiche`, `NA`) | **fail** |
| No duplicate keys: `nom` alone for `static`, `(nom, date)` for time-series | **fail** |
| Consistent row width | **fail** |
| Value column headers must **not** be canonical zone names (catches matrices misnamed as vectors) | **fail** |
| Empty column headers (typical R `write.csv` without `row.names=FALSE`) | **warn** |

National roll-up rows use `nom = DRC` (see `NATIONAL_ROLLUP_NOM` in schema). These pass QA; the GeoJSON builder broadcasts them to every zone feature.

Header-only CSVs (valid header, zero data rows) **pass** QA. The build step writes a placeholder long copy and attaches zero zones — useful for datasets that are wired up but not yet populated.

### 5. Matrix files (`.matrix.csv`)

**Snapshot** (`resolution = static`):

- Header: `nom, <dest_nom_1>, <dest_nom_2>, …`
- First column = origin zone; remaining columns = destination zones

**Time-series** (any other resolution):

- Header: `date, nom, <dest_nom_1>, …`
- First column = ISO date; second = origin zone

| Check | On failure |
|-------|------------|
| Origin and destination headers resolve to canonical zone names | **fail** |
| Present cells are non-negative numeric | **fail** |
| Missing cells (empty, `NA`, `NaN`, `NULL`, etc.) | **warn** (expected for unroutable OSRM pairs) |
| Snapshot matrices: unique canonical origins vs destination column count ("square") | reported in logs, not a hard fail |

Matrices are **never** embedded in `build/drc_health_zones.geojson`. QA-passing matrices are staged under `build/matrix/` and remain available under `data/<dataset>/processed/`; use `qa/matrix_log.csv` as a catalogue.

---

## Status semantics

| Status | Blocks PR merge? | Blocks release? | Included in GeoJSON build? | Listed in `matrix_log.csv`? |
|--------|------------------|-----------------|----------------------------|------------------------------|
| **pass** | No | No | Yes (vectors) | Yes (matrices) |
| **warn** | No | No | Yes (vectors) | Yes (matrices) |
| **fail** | Yes | Yes | No | No |

Warnings flag data-quality issues that are tolerated for now (empty R index columns, sparse matrix cells). Failures must be fixed before merge or release.

---

## Files in this folder

All files here are **generated**. Do not edit them by hand, and **do not commit them from feature branches** — CI refreshes them on `main` after each successful release. Including them in a PR causes merge conflicts.

### `qa_log.csv`

One row per checked artifact (metadata, structure, vector, or matrix). Columns:

| Column | Meaning |
|--------|---------|
| `dataset` | Folder name under `data/` |
| `file` | Filename or structural path (e.g. `processed/`) |
| `type` | `metadata`, `structure`, `vector`, or `matrix` |
| `status` | `pass`, `warn`, or `fail` |
| `n_rows` | Data rows in the CSV (when applicable) |
| `n_zones_covered` | Distinct canonical zones seen |
| `reasons` | Semicolon-separated explanation(s) |
| `checked_at` | UTC timestamp of the QA run |

This file is the **single source of truth** for what enters the GeoJSON build. [`tools/build_geojson.py`](../tools/build_geojson.py) reads it and attaches every **vector** row where `status != fail`. [`tools/release.py`](../tools/release.py) refuses to pack a release if any row has `status == fail`.

### `matrix_log.csv`

Subset of `qa_log.csv`: matrix files with status `pass` or `warn`. Columns include `resolution`, `n_rows`, `n_cols`, `square`, `date_range`, and `n_zones_covered`. Use this as a machine-readable index of downloadable matrix datasets.

### `reports/<dataset>.md`

Human-readable summary for one dataset folder: status counts, per-file row/zone counts, resolution, date range, and detailed reasons. Open the report for the dataset you changed when triaging CI failures.

Example excerpt:

```markdown
## `insp_sitrep__cumulative_confirmed_cases__daily.csv` (vector) — **pass**
- rows: 283
- zones covered: 29 / 519
- resolution: daily
```

The `zones covered: N / 519` denominator is the full MoH health-zone count from the shapefile. Partial coverage is normal for outbreak sitrep data that only reports affected zones.

---

## Relationship to the GeoJSON build

After QA succeeds, `python -m tools.build_geojson`:

1. Loads `qa/qa_log.csv`
2. For each **vector** with `status` not equal to `fail`:
   - Attaches latest per-zone values to `build/drc_health_zones.geojson` under `feature.properties.<dataset>.<metric>`
   - Writes a long-format copy to `build/long/<dataset>__<metric>.csv`
3. For each **matrix** with `status` not equal to `fail`:
   - Copies the processed file to `build/matrix/<file>` (still **not** embedded in the GeoJSON)
4. Writes `build/manifest.json` listing all datasets with passing metadata and their outputs (vectors marked `in_geojson: true` with `long_csv`; matrices marked `in_geojson: false` with `matrix_csv`)

Time-series vectors use the **latest date per zone** in the build snapshot (ISO date string comparison).

---

## Running checks locally

From the repository root, after one-time setup (`git lfs install`, virtualenv, `pip install -r tools/requirements.txt`):

```bash
# Full test suite
python -m pytest tests/ -v

# Validate all datasets
python -m tools.qa

# Validate one or more datasets only
python -m tools.qa insp_sitrep public_health_response

# Optional: sanity-check the merged GeoJSON (do not commit output on a PR branch)
python -m tools.qa && python -m tools.build_geojson --skip-readme
```

On failure, `tools.qa` prints a summary and lists every `FAIL` line. Inspect the matching file under `qa/reports/` for full detail.

---

## Unit test coverage (`tests/`)

The pytest suite complements `tools.qa` by locking in contract behaviour and build edge cases:

| Test module | Focus |
|-------------|-------|
| `test_schema.py` | Canonical zone list, alias resolution, filename parsing |
| `test_qa_matrix.py` | Matrix missing cells (warn) vs bad numeric values (fail) |
| `test_qa_vector_nom.py` | Non-geographic `nom` labels accepted by vector QA |
| `test_build_geojson_vector.py` | Empty R columns, national `DRC` roll-ups, header-only placeholders |
| `test_build_geojson_manifest.py` | Manifest structure after build |
| `test_build_geojson_readme.py` | README "Last successful build" stamping |
| `test_release_lib.py` / `test_release_orchestrator.py` | Release packing and QA preflight |
| `test_publish.py` | GitHub release creation |
| `test_extract_whats_new.py` | PR description → release notes extraction |
| `test_cross_border_process.py`, `test_idp_process.py` | Dataset-specific processing helpers |

Add or extend tests when you change QA rules or build behaviour — do not rely on manual inspection alone.

---

## Contributor checklist

Before opening a PR that touches `data/**`:

1. Processed filenames match the contract; add spelling variants to `data/aliases.csv` if needed.
2. `python -m pytest tests/` passes.
3. `python -m tools.qa` passes (zero `fail` rows).
4. Fill in the PR template **`## What's new`** section — it becomes the GitHub Release description.
5. Do **not** commit `build/`, `qa/qa_log.csv`, `qa/matrix_log.csv`, `qa/reports/`, or README build sections.

After merge, maintainers do not run a separate release step — CI handles QA, build, commit-back, publish, and dashboard dispatch automatically.

See also the [Contributor flow](../README.md#contributor-flow) and [Release internals](../README.md#release-internals) sections in the root README.

---

## Troubleshooting common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `missing 'nom' column` | Vector CSV lacks join key | Add `nom` column with canonical zone names |
| `unresolved nom` | Typo or new zone spelling | Add alias to `data/aliases.csv` or fix `process.py` |
| `duplicate keys` | Two rows for same zone (and date) | Deduplicate in processing script |
| `value column(s) resolve to canonical zone names` | Matrix saved as `.csv` instead of `.matrix.csv` | Rename to `.matrix.csv` and fix headers |
| `first column header must be 'date'` | Time-series matrix missing date column | Use `date, nom, …` header row |
| `non-numeric or negative cells` | Bad matrix cell | Fix source data or processing |
| `missing fields: [...]` in metadata | Incomplete `metadata.yaml` | Fill required fields |
| `filename does not match contract` | Wrong processed filename | Rename to `<dataset>__<metric>__<resolution>.csv` |
| Empty column header **warn** | R `write.csv()` default row names | Use `row.names=FALSE` in R exports |

Warnings about missing matrix cells (`NA`) in OSRM travel-time matrices are expected and do not block release.

---

## CI artifacts

When a PR fails QA in GitHub Actions, download the **`qa-logs`** artifact from the workflow run. It contains the same `qa/` outputs that would be committed on `main` after a successful release, including per-dataset markdown reports.
