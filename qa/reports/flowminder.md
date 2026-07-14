# QA report: flowminder

_Checked: 2026-07-14T10:51:26+00:00_

**Status counts:** {'pass': 3, 'warn': 2}

## `metadata.yaml` (metadata) — **pass**

## `flowminder__inflow_202604__static.matrix.csv` (matrix) — **warn**
- rows: 467
- cols: 467
- zones covered: 467 / 519
- resolution: static
- square: True
- reasons:
  - 57339 missing cells (empty/NA) (warn)

## `flowminder__inflow__static.matrix.csv` (matrix) — **pass**
- rows: 437
- cols: 437
- zones covered: 437 / 519
- resolution: static
- square: True

## `flowminder__outflow_202604__static.matrix.csv` (matrix) — **warn**
- rows: 467
- cols: 467
- zones covered: 467 / 519
- resolution: static
- square: True
- reasons:
  - 57339 missing cells (empty/NA) (warn)

## `flowminder__outflow__static.matrix.csv` (matrix) — **pass**
- rows: 437
- cols: 437
- zones covered: 437 / 519
- resolution: static
- square: True
