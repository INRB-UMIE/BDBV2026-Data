# Guard against province/national roll-up rows in zone-level `insp_sitrep` files

**Date:** 2026-08-04
**Repo:** BDBV2026-Data
**Status:** Approved design, pending implementation plan

## Problem

SitRep 80 (PR #133) added four rows keyed by **province name** to two files that
are supposed to hold **health-zone** rows only:

```
data/insp_sitrep/processed/insp_sitrep__cumulative_confirmed_cases__daily.csv
  Nord-Kivu,2026-08-02,414   Haut-Uele,2026-08-02,61   Sud-Kivu,...,3   Tshopo,...,7
data/insp_sitrep/processed/insp_sitrep__cumulative_confirmed_deaths__daily.csv
  Nord-Kivu,2026-08-02,285   Haut-Uele,2026-08-02,34   Sud-Kivu,...,1   Tshopo,...,5
```

`tools/build_geojson.py::_attach_vector` **broadcasts** any province-roll-up row
to every health zone in that province (and any national `DRC` row to every zone).
That broadcast is correct for *intensive* province/national metrics, but for
*extensive* counts like cumulative confirmed cases it makes every zone in the
province inherit the province total. Result: the outbreak map jumped from 50 to
115 case markers, and every zone in Haut-Uele / Nord-Kivu / Sud-Kivu displayed
its province's total (e.g. Dungu = 61 confirmed / 34 deaths) instead of "—".

The bad data was corrected upstream in PR #134. This design prevents recurrence.

### Why existing QA did not catch it

The vector contract in `tools/qa.py` intentionally accepts province roll-ups and
national `DRC` as valid `nom` values (`resolve_vector_nom` + `province_aliases.csv`),
because many datasets legitimately carry province/national rows for broadcast.
So a `nom=Nord-Kivu` row passed QA. The danger is specific to the zone-level
`insp_sitrep` count files, where national totals already live in *separate*
`national_*` files and a province row therefore has no legitimate place.

## The rule

> In the `insp_sitrep` dataset, every processed file whose metric name does **not**
> start with `national_` is zone-level and must contain **no province-roll-up and
> no national (`DRC`) noms**. Non-geographic placeholder noms (e.g. `NA`) remain
> allowed, exactly as today.

Rationale for the wording:
- The `insp_sitrep` dataset separates national metrics by a `national_*` filename
  prefix, so the prefix cleanly distinguishes the (exempt) national files from the
  zone-level ones.
- The rule targets **only** the broadcast-dangerous noms (province + national).
  It deliberately does **not** forbid non-geographic placeholders like `NA`, which
  the build already skips via `is_non_geographic_nom` (never attached, never
  broadcast). Forbidding `NA` would flag three currently-valid files and change
  behavior — the opposite of the goal.
- Collision noms (`Tshopo`, `Kinshasa`, `Lualaba` — each both a zone and a
  province) resolve to the **zone** when written bare, so a legitimate bare
  zone row is not flagged; only pure province names (`Nord-Kivu`, `Haut-Uele`)
  and the explicit `"<Province> (province)"` form are.

## Design

### 1. Shared predicate (single source of truth)

Add to `tools/lib/schema.py`:

```python
def requires_zone_only_noms(dataset: str, metric: str) -> bool:
    """insp_sitrep zone-level files must not carry province/national roll-ups;
    national totals live in the separate `national_*` metrics."""
    return dataset == "insp_sitrep" and not metric.startswith("national_")
```

Both the QA check and the build guard call this, so the scope is defined once.

### 2. QA check — fail fast at PR time (`tools/qa.py::qa_vector`)

When `requires_zone_only_noms(parsed.dataset, parsed.metric)` is true, resolve
each row's `nom`; collect any that resolve to a **province roll-up** or the
**national** label (`is_province_rollup_nom` / `is_national_rollup_nom`). If any
are found, add a **fatal** reason, e.g.:

```
2 roll-up noms in a zone-level insp_sitrep file (province/national rows belong
in the national_* files): ['Haut-Uele', 'Nord-Kivu']
```

`NA` and other non-geographic placeholders are **not** flagged. QA runs on every
`data/**` PR, so a PR like #133 fails before merge with a message pointing at the
offending rows.

### 3. Build guard — defense in depth at release time (`tools/build_geojson.py::_attach_vector`)

When `requires_zone_only_noms(...)` is true, skip the province-roll-up and
national broadcast blocks entirely (apply zone rows only). If any roll-up rows
were present, `print` a warning naming them. Even if a bad row bypasses QA
(force-merge / direct push), it can never be fanned across zones again — it is
simply ignored. The `national_*` files are unaffected and keep broadcasting.

### 4. Tests

- Extend `tests/test_qa_vector_nom.py`:
  - a zone-level `insp_sitrep` file containing a `Nord-Kivu` row → QA **fail**;
  - the same file with only zone rows + an `NA` row → QA **pass** (no false positive);
  - a `national_*` file with a `DRC` row → QA **pass** (exempt).
- Add a `build_geojson` test: a province row in a zone-level `insp_sitrep` file is
  **not** broadcast to that province's zones (those zones keep their own value / stay absent),
  while a `national_*` `DRC` row still broadcasts.

## Strictness

- **QA:** hard fail (non-zero exit) — blocks the PR. Consistent with existing
  `fail` statuses.
- **Build guard:** skip + warn (does not fail the release). QA is the real gate;
  the build guard is a safety net that prevents amplification without breaking
  releases.

## Verification (no-op on current data)

Scanned all 31 `insp_sitrep` processed files on `origin/main` (post-fix) with the
repo's own resolution helpers:

- Non-`national_` files contain only zone noms plus `NA` in three files
  (`cumulative_confirmed_cases`, `cumulative_confirmed_deaths`, `new_confirmed_cases`).
- No province roll-ups exist in any non-`national_` file; `DRC` appears only in
  the exempt `national_*` files.

Therefore, on correct data: QA stays green, the GeoJSON output is byte-identical
(national broadcast preserved, `NA` still skipped, no province rows to skip), and
long-format CSVs are unchanged. The guard changes output only when the corruption
pattern is present.

## Out of scope / non-goals

- No change to the dashboard repo (it already renders absent zones as "—").
- No general per-metric metadata flag for "extensive counts"; the narrow,
  `insp_sitrep`-scoped rule covers the file that actually broke (YAGNI).
- No change to the intended province/national broadcast behavior for other datasets.
