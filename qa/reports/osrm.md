# QA report: osrm

_Checked: 2026-05-21T11:44:06+00:00_

**Status counts:** {'pass': 1, 'fail': 2}

## `metadata.yaml` (metadata) — **pass**

## `osrm__road_distance__static.matrix.csv` (matrix) — **fail**
- rows: 519
- cols: 519
- zones covered: 519 / 519
- resolution: static
- square: True
- reasons:
  - 20 destination headers unresolved (sample: ['Seke Banza', 'Boko Kivulu', 'Mbanza Ngungu', 'Kwilu Ngongo', 'Masi Manimba'])
  - 1036 non-numeric or negative cells

## `osrm__travel_time__static.matrix.csv` (matrix) — **fail**
- rows: 519
- cols: 519
- zones covered: 519 / 519
- resolution: static
- square: True
- reasons:
  - 20 destination headers unresolved (sample: ['Seke Banza', 'Boko Kivulu', 'Mbanza Ngungu', 'Kwilu Ngongo', 'Masi Manimba'])
  - 1036 non-numeric or negative cells
