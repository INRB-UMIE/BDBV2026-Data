# QA report: osrm

_Checked: 2026-08-27T14:09:22+00:00_

**Status counts:** {'pass': 1, 'warn': 2}

## `metadata.yaml` (metadata) — **pass**

## `osrm__road_distance__static.matrix.csv` (matrix) — **warn**
- rows: 519
- cols: 519
- zones covered: 519 / 519
- resolution: static
- square: True
- reasons:
  - 2070 missing cells (empty/NA) (warn)

## `osrm__travel_time__static.matrix.csv` (matrix) — **warn**
- rows: 519
- cols: 519
- zones covered: 519 / 519
- resolution: static
- square: True
- reasons:
  - 2070 missing cells (empty/NA) (warn)
