# insp_sitrep Roll-up Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent province/national roll-up rows in zone-level `insp_sitrep` data files from being broadcast across every health zone (which corrupted the dashboard's case markers), by failing them in QA and dropping the broadcast in the GeoJSON build.

**Architecture:** One shared predicate `requires_zone_only_noms(dataset, metric)` in `tools/lib/schema.py`, consumed by (1) `tools/qa.py::qa_vector` to hard-fail a PR that puts a province/national roll-up in a zone-level `insp_sitrep` file, and (2) `tools/build_geojson.py::_attach_vector` to skip the province/national broadcast (with a warning) for those files as defense in depth.

**Tech Stack:** Python 3.12, pytest. All logic reuses existing `schema.py` nom-resolution helpers (`is_province_rollup_nom`, `is_national_rollup_nom`, `is_non_geographic_nom`, `resolve_vector_nom`).

**Spec:** `docs/superpowers/specs/2026-08-04-insp-sitrep-rollup-guard-design.md`

**Environment note (this machine):** run Python via the prepared venv from the repo root, e.g.
`cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest ...`.
CI itself uses `python -m pytest tests/` and `python -m tools.qa`.

**Branch:** `harden-sitrep-rollup-guard` (already checked out, off `origin/main`).

---

## File Structure

- `tools/lib/schema.py` — **modify**: add the `requires_zone_only_noms` predicate (single source of truth for the rule).
- `tools/qa.py` — **modify**: add the roll-up check inside `qa_vector`.
- `tools/build_geojson.py` — **modify**: guard the broadcast blocks in `_attach_vector`.
- `tests/test_schema.py` — **modify**: unit-test the predicate.
- `tests/test_qa_vector_nom.py` — **modify**: QA fail/pass cases incl. the collision limitation.
- `tests/test_build_geojson_vector.py` — **modify**: build guard suppresses broadcast, preserves zone values, exempts `national_*`.

---

## Task 1: Shared predicate `requires_zone_only_noms`

**Files:**
- Modify: `tools/lib/schema.py` (insert after `resolve_vector_nom`, which ends at line 294)
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schema.py`:

```python
def test_requires_zone_only_noms():
    from tools.lib.schema import requires_zone_only_noms

    # Zone-level insp_sitrep metrics: guarded.
    assert requires_zone_only_noms("insp_sitrep", "cumulative_confirmed_cases") is True
    assert requires_zone_only_noms("insp_sitrep", "cumulative_confirmed_deaths") is True
    assert requires_zone_only_noms("insp_sitrep", "new_confirmed_cases") is True
    assert requires_zone_only_noms("insp_sitrep", "hospitalised") is True

    # National insp_sitrep metrics: exempt (they legitimately carry DRC).
    assert requires_zone_only_noms("insp_sitrep", "national_cumulative_confirmed_cases") is False

    # Other datasets: never guarded by this narrow rule.
    assert requires_zone_only_noms("public_health_response", "provincial_epidemiological_coordination") is False
    assert requires_zone_only_noms("flowminder", "inflow") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_schema.py::test_requires_zone_only_noms -v`
Expected: FAIL with `ImportError: cannot import name 'requires_zone_only_noms'`.

- [ ] **Step 3: Write minimal implementation**

In `tools/lib/schema.py`, insert this function immediately after `resolve_vector_nom` (after line 294, before `def zscode_to_canonical`):

```python
def requires_zone_only_noms(dataset: str, metric: str) -> bool:
    """True for insp_sitrep files that must contain no province/national roll-up
    noms.

    The insp_sitrep dataset keeps national totals in separate ``national_*``
    metrics, so a province- or national-keyed row in a non-``national_`` file is
    always a mistake: ``build_geojson._attach_vector`` would broadcast it across
    every zone in the province (or all zones, for national), clobbering real
    per-zone counts. Non-geographic placeholders (e.g. ``NA``) are unaffected —
    this only concerns province/national roll-ups.
    """
    return dataset == "insp_sitrep" and not metric.startswith("national_")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_schema.py::test_requires_zone_only_noms -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/user/Documents/work/BDBV2026-Data
git add tools/lib/schema.py tests/test_schema.py
git commit -m "schema: add requires_zone_only_noms predicate for insp_sitrep zone-level files"
```

---

## Task 2: QA hard-fail on roll-up rows in zone-level insp_sitrep files

**Files:**
- Modify: `tools/qa.py` (imports at 45-55; `qa_vector` at 123; insert check after the row loop, before `fatal = ...` at line 196)
- Test: `tests/test_qa_vector_nom.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_qa_vector_nom.py`:

```python
def _write(tmp_path, filename, body):
    processed = tmp_path / "insp_sitrep" / "processed"
    processed.mkdir(parents=True)
    path = processed / filename
    path.write_text(body, encoding="utf-8")
    parsed = parse_filename(path.name)
    assert parsed is not None
    return path, parsed


def test_qa_vector_rejects_province_rollup_in_zone_level_sitrep(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Nord-Kivu,2026-08-02,414\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "fail"
    assert any("roll-up" in r for r in result.reasons)


def test_qa_vector_rejects_explicit_province_form_in_zone_level_sitrep(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Tshopo (province),2026-08-02,7\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "fail"


def test_qa_vector_allows_bare_collision_zone_in_sitrep(tmp_path):
    # KNOWN LIMITATION: bare "Tshopo" resolves to the Tshopo *zone*, so it is
    # NOT flagged (see spec "Known limitation"). Locks in that documented gap.
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Tshopo,2026-08-02,7\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"


def test_qa_vector_national_file_allows_drc(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-08-02,3800\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"
```

Note: `test_qa_vector_accepts_sans_fiche_and_na` already exists in this file and covers the `NA`/`Sans Fiche` no-false-positive case (it uses metric `cases`, which is also a guarded zone-level insp_sitrep metric) — no new NA test needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_qa_vector_nom.py -v`
Expected: the two `rejects_*` tests FAIL (status is `pass`, not `fail`); `allows_bare_collision_zone` and `national_file_allows_drc` PASS already; pre-existing tests PASS.

- [ ] **Step 3: Add the schema imports**

In `tools/qa.py`, replace the import block at lines 45-55:

```python
from tools.lib.schema import (
    REPO_ROOT,
    REQUIRED_METADATA_FIELDS,
    VALID_RUNTIMES,
    canonical_noms,
    counts_as_zone_coverage,
    is_non_geographic_nom,
    parse_filename,
    resolve_vector_nom,
    to_canonical,
)
```

with:

```python
from tools.lib.schema import (
    REPO_ROOT,
    REQUIRED_METADATA_FIELDS,
    VALID_RUNTIMES,
    canonical_noms,
    counts_as_zone_coverage,
    is_national_rollup_nom,
    is_non_geographic_nom,
    is_province_rollup_nom,
    parse_filename,
    requires_zone_only_noms,
    resolve_vector_nom,
    to_canonical,
)
```

- [ ] **Step 4: Add the roll-up check in `qa_vector`**

In `tools/qa.py::qa_vector`, the current code around lines 194-197 is:

```python
    dup = [k for k, c in Counter(keys).items() if c > 1]
    if dup:
        reasons.append(f"{len(dup)} duplicate keys (sample: {dup[:3]})")

    fatal = [r for r in reasons if not r.endswith("(warn)")]
```

Insert the roll-up check between the `dup` block and the `fatal =` line, so it reads:

```python
    dup = [k for k, c in Counter(keys).items() if c > 1]
    if dup:
        reasons.append(f"{len(dup)} duplicate keys (sample: {dup[:3]})")

    # Zone-level insp_sitrep files must not carry province/national roll-ups:
    # build_geojson broadcasts them across a whole province, clobbering real
    # per-zone counts (see requires_zone_only_noms). Checked over all rows
    # independently of the width-mismatch skip above so a roll-up in a
    # malformed-width row is still caught. NA / non-geographic placeholders and
    # bare collision-zone names (e.g. "Tshopo") are intentionally not flagged.
    if requires_zone_only_noms(dataset, parsed.metric):
        rollups = []
        for r in rows:
            if len(r) <= nom_i:
                continue
            resolved = resolve_vector_nom(r[nom_i])
            if resolved is not None and (
                is_province_rollup_nom(resolved) or is_national_rollup_nom(resolved)
            ):
                rollups.append(r[nom_i])
        if rollups:
            sample = sorted(set(rollups))[:5]
            reasons.append(
                f"{len(rollups)} province/national roll-up nom(s) in a zone-level "
                f"insp_sitrep file (province/national totals belong in the "
                f"national_* files): {sample}"
            )

    fatal = [r for r in reasons if not r.endswith("(warn)")]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_qa_vector_nom.py -v`
Expected: all tests PASS (both `rejects_*` now fail the file as intended; `allows_*` still pass).

- [ ] **Step 6: Commit**

```bash
cd /Users/user/Documents/work/BDBV2026-Data
git add tools/qa.py tests/test_qa_vector_nom.py
git commit -m "qa: fail zone-level insp_sitrep files that carry province/national roll-up rows"
```

---

## Task 3: Build guard — drop the broadcast for zone-level insp_sitrep files

**Files:**
- Modify: `tools/build_geojson.py` (imports at 59-71; `_attach_vector` at 179; broadcast blocks at 235-264)
- Test: `tests/test_build_geojson_vector.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_build_geojson_vector.py`:

```python
def test_attach_vector_drops_province_rollup_for_zone_level_sitrep(tmp_path, monkeypatch):
    """A province roll-up row in a zone-level insp_sitrep file must NOT be
    broadcast, and must NOT clobber a real per-zone value."""
    processed = tmp_path / "insp_sitrep" / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)
    fname = "insp_sitrep__cumulative_confirmed_cases__daily.csv"
    (processed / fname).write_text(
        "nom,date,cumulative_confirmed_cases\n"
        "Beni,2026-08-02,10\n"          # real per-zone value
        "Nord-Kivu,2026-08-02,414\n",   # province roll-up (must be dropped)
        encoding="utf-8",
    )
    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    beni = {"properties": {}}
    butembo = {"properties": {}}  # another Nord-Kivu zone, no row of its own
    build_geojson._attach_vector(
        processed / fname, fname,
        SimpleNamespace(dataset="insp_sitrep", metric="cumulative_confirmed_cases"),
        {"Beni": beni, "Butembo": butembo},
    )

    # Beni keeps its own value, not the province total.
    assert beni["properties"]["insp_sitrep"]["cumulative_confirmed_cases"]["cumulative_confirmed_cases"] == 10
    # Butembo never received the broadcast.
    assert "insp_sitrep" not in butembo["properties"]


def test_attach_vector_national_sitrep_still_broadcasts(tmp_path, monkeypatch):
    """national_* insp_sitrep files are exempt: DRC still broadcasts to all zones."""
    processed = tmp_path / "insp_sitrep" / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)
    fname = "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    (processed / fname).write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        f"{NATIONAL_ROLLUP_NOM},2026-08-02,3800\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    beni = {"properties": {}}
    butembo = {"properties": {}}
    build_geojson._attach_vector(
        processed / fname, fname,
        SimpleNamespace(dataset="insp_sitrep", metric="national_cumulative_confirmed_cases"),
        {"Beni": beni, "Butembo": butembo},
    )

    for feat in (beni, butembo):
        val = feat["properties"]["insp_sitrep"]["national_cumulative_confirmed_cases"]
        assert val["national_cumulative_confirmed_cases"] == 3800
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_build_geojson_vector.py -v`
Expected: `test_attach_vector_drops_province_rollup_for_zone_level_sitrep` FAILS (Beni is clobbered to 414 and/or Butembo receives the broadcast); `test_attach_vector_national_sitrep_still_broadcasts` PASSES already.

- [ ] **Step 3: Add the schema import**

In `tools/build_geojson.py`, replace the import block at lines 59-71:

```python
from tools.lib.schema import (
    NATIONAL_ROLLUP_NOM,
    REPO_ROOT,
    SHAPEFILE,
    is_non_geographic_nom,
    is_province_rollup_nom,
    load_zones,
    parse_filename,
    province_name_from_rollup_nom,
    resolve_processed_paths,
    resolve_vector_nom,
    zones_by_province,
)
```

with (adds `requires_zone_only_noms`):

```python
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
```

- [ ] **Step 4: Guard the broadcast blocks**

In `tools/build_geojson.py::_attach_vector`, the current code at lines 244-264 is:

```python
    for nom, r in zone_rows.items():
        _apply_row(nom, r)

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
```

Replace it with (zone rows still applied unconditionally; province/national broadcast skipped for guarded files):

```python
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
            f"roll-up row(s) {offenders} — zone-level file must not carry them"
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/test_build_geojson_vector.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/user/Documents/work/BDBV2026-Data
git add tools/build_geojson.py tests/test_build_geojson_vector.py
git commit -m "build_geojson: drop province/national broadcast for zone-level insp_sitrep files"
```

---

## Task 4: Full-suite + real-data no-op verification

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m pytest tests/ -v`
Expected: PASS — no regressions across all pre-existing tests plus the new ones.

- [ ] **Step 2: Run QA on the real data and confirm it stays green**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m tools.qa insp_sitrep`
Expected: summary shows no `FAIL` for `insp_sitrep` (the corrected data has no roll-up rows, so the new check adds zero failures). Exit code 0.

- [ ] **Step 3: Confirm the guard is a true no-op on the current GeoJSON**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && PYTHONPATH=. /tmp/bdbv_venv/bin/python -m tools.build_geojson`
Then confirm no `WARNING: ... dropped ... roll-up row(s)` line was printed for any `insp_sitrep` file (there are no roll-up rows in the corrected data). If the build writes `build/drc_health_zones.geojson`, `git diff --stat build/drc_health_zones.geojson` should show no change attributable to insp_sitrep zone values.
Expected: no roll-up warnings; insp_sitrep zone values unchanged.

- [ ] **Step 4: Final review of the branch**

Run: `cd /Users/user/Documents/work/BDBV2026-Data && git log --oneline origin/main..HEAD`
Expected: three implementation commits (Tasks 1-3) plus the two spec commits already on the branch.

---

## Self-Review

- **Spec coverage:** shared predicate (Task 1) ✓; QA hard-fail incl. explicit-province-form fail and bare-collision pass, and NA no-false-positive via existing test (Task 2) ✓; build guard with clobber-preservation + national exemption (Task 3) ✓; no-op verification on real data (Task 4) ✓; Known limitation locked in by `test_qa_vector_allows_bare_collision_zone_in_sitrep` ✓.
- **Placeholders:** none — every code step shows full code and exact commands.
- **Type/name consistency:** `requires_zone_only_noms(dataset, metric)` signature identical across schema definition, qa import/use (`parsed.metric`), and build import/use (`dataset_token`, `metric`). `is_province_rollup_nom` / `is_national_rollup_nom` names match `schema.py`. `NATIONAL_ROLLUP_NOM` reused from existing import.
