# Flowminder short-trip destination proportions (Bunia / Mongbalu / Rwampara cohort)

Proportion of mobile subscribers observed in **Bunia, Mongbwalu, or Rwampara** during 3–23 April 2026 who were later seen in other DRC health zones, from Flowminder Annex A in the May 2026 Ebola movement brief.

Unlike `data/flowminder/` (full provincial OD matrices in persons), this folder holds **five snapshot proportion matrices** at D+7 … D+31, plus matching **long-format vector** files for dashboard / GeoJSON use.

------------------------------------------------------------------------

## Files

| File | Description |
|------|-------------|
| `raw/Population_movements_Ebola_28_May_2026_Flowminder_Final.pdf` | Source report |
| `raw/short_trips_destination_rankings.csv` | Extracted ranked table (pages 8–11) |
| `processed/flowminder_short_trips__outflow_20260524__static.matrix.csv` | Example matrix (D+31 / 24 May); four other dates alongside |
| `processed/flowminder_short_trips__outflow_20260524__static.csv` | Example long vector (`nom`, `outflow_20260524`); one per snapshot |
| `extract_pdf_annex.py` | PDF → raw CSV |
| `process.py` | Raw CSV → matrices + long vectors |
| `zone_resolution_log.csv` | Dropped / merged zone labels during canonicalisation |
| `metadata.yaml` | Provenance |

**Processed layout** (same pattern as `flowminder__outflow__static.matrix.csv`):

- First column: `nom` (origin) — only **Bunia**, **Mongbalu**, **Rwampara**
- Remaining columns: canonical destination zone names from the annex table
- Cell values: percentage proportion for that snapshot date (identical across the three origin rows)

**Long vectors** (`flowminder_short_trips__outflow_<YYYYMMDD>__static.csv`):

- `nom` — destination health zone (matrix column headers, excluding the origin `nom` column)
- `outflow_<YYYYMMDD>` — proportion (%) from the first origin data row (cohort values are identical for Bunia, Mongbalu, Rwampara)

**Snapshot files**

| File suffix | PDF column | Observation date |
|-------------|------------|------------------|
| `_20260430` | D+7 | 30 Apr 2026 |
| `_20260507` | D+14 | 7 May 2026 |
| `_20260514` | D+21 | 14 May 2026 |
| `_20260521` | D+28 | 21 May 2026 |
| `_20260524` | D+31 | 24 May 2026 |

------------------------------------------------------------------------

## Regenerating outputs

From the repo root (requires `pdfplumber` in the environment):

```bash
python data/flowminder_short_trips/extract_pdf_annex.py
python data/flowminder_short_trips/process.py
.venv/bin/python -m tools.qa flowminder_short_trips
```

**Maps** (requires `matplotlib`, `numpy`, `shapely`, `pyshp`):

```bash
python data/flowminder_short_trips/plot_short_trips_maps.py
```

Writes `short_trips_outflow_maps.png` — five choropleth panels (Ituri, Nord-Kivu, north Sud-Kivu); cohort zones in one colour, destinations graded by proportion (%).

------------------------------------------------------------------------

## Provenance

See `metadata.yaml`. Destination names are resolved with the same rules as `data/flowminder/process.py` and `data/aliases.csv`.
