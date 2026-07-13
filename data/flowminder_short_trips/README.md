# Flowminder short-trip destination mobility (Bunia / Mongbalu / Rwampara and NK cohorts)

Mobile-subscriber mobility snapshots for the BDBV 2026 outbreak area, from Flowminder Annex A (May 2026 report) and HDX cohort subscriber-day extracts (8 Jun 2026).

Unlike `data/flowminder/` (full provincial OD matrices in persons), this folder holds **static snapshot matrices** (origin rows × destination columns) plus matching **long-format vector** files for dashboard / GeoJSON use.

------------------------------------------------------------------------

## Files

| File | Description |
|------|-------------|
| `raw/Population_movements_Ebola_28_May_2026_Flowminder_Final.pdf` | Source report (Annex A) |
| `raw/short_trips_destination_rankings.csv` | Extracted ranked proportion table (pages 8–11) |
| `raw/drc-bvd_ituri-cohort_subscriber-days-2026_06_08-v1.0-external.csv` | HDX Ituri cohort subscriber-day averages |
| `raw/drc-bvd_nk-cohort_subscriber-days-2026_06_08-v1.0-external.csv` | HDX Nord-Kivu cohort subscriber-day averages |
| `raw/metadata-drc-bvd_*-cohort_subscriber-days-*.csv` | HDX resource metadata sidecars |
| `processed/flowminder_short_trips__outflow_20260524__static.matrix.csv` | Example annex proportion matrix (D+31 / 24 May) |
| `processed/flowminder_short_trips__ituri_subscriber_days_followup_20260608__static.matrix.csv` | Example HDX cohort matrix (Ituri follow-up) |
| `extract_pdf_annex.py` | PDF → annex raw CSV |
| `process.py` | Raw inputs → matrices + long vectors |
| `zone_resolution_log.csv` | Dropped / merged zone labels during canonicalisation |
| `metadata.yaml` | Provenance |

**Processed layout** (same pattern as `flowminder__outflow__static.matrix.csv`):

- First column: `nom` (origin health zones for the cohort)
- Remaining columns: canonical destination zone names
- Cell values: annex proportions (%) or average subscriber presence days (HDX cohorts)
- Origin rows carry identical destination profiles per snapshot (cohort-level aggregate)

**Long vectors** (`flowminder_short_trips__<metric>__static.csv`):

- `nom` — destination health zone
- `<metric>` — value from the first origin data row

------------------------------------------------------------------------

## Annex A proportion snapshots

| File suffix | PDF column | Observation date |
|-------------|------------|------------------|
| `_outflow_20260430` | D+7 | 30 Apr 2026 |
| `_outflow_20260507` | D+14 | 7 May 2026 |
| `_outflow_20260514` | D+21 | 14 May 2026 |
| `_outflow_20260521` | D+28 | 21 May 2026 |
| `_outflow_20260524` | D+31 | 24 May 2026 |

Origins: **Bunia**, **Mongbalu**, **Rwampara**.

------------------------------------------------------------------------

## HDX cohort subscriber-day snapshots

| Metric suffix | Window | End date | Origins |
|---------------|--------|----------|---------|
| `ituri_subscriber_days_prior_20260503` | 21-day look-back | 3 May 2026 | Bunia, Mongbalu, Rwampara, Nyankunde |
| `ituri_subscriber_days_followup_20260608` | 21-day follow-up | 8 Jun 2026 | Bunia, Mongbalu, Rwampara, Nyankunde |
| `nk_subscriber_days_prior_20260503` | 21-day look-back | 3 May 2026 | Beni, Butembo, Katwa |
| `nk_subscriber_days_followup_20260608` | 21-day follow-up | 8 Jun 2026 | Beni, Butembo, Katwa |

Cohort presence definition and continuity model are documented in the HDX metadata sidecars and resource descriptions on [HDX](https://data.humdata.org/dataset/86326534-8dea-4c8b-aca2-13c3e6d386ac).

------------------------------------------------------------------------

## Regenerating outputs

From the repo root (requires `pdfplumber` in the environment):

```bash
python data/flowminder_short_trips/extract_pdf_annex.py
python data/flowminder_short_trips/process.py
.venv/bin/python -m tools.qa flowminder_short_trips
```

**Maps** (annex proportion snapshots only; requires `matplotlib`, `numpy`, `shapely`, `pyshp`):

```bash
python data/flowminder_short_trips/plot_short_trips_maps.py
```

Writes `short_trips_outflow_maps.png` — five choropleth panels (Ituri, Nord-Kivu, north Sud-Kivu); cohort zones in one colour, destinations graded by proportion (%).

------------------------------------------------------------------------

## Provenance

See `metadata.yaml`. Destination names are resolved with the same rules as `data/flowminder/process.py` and `data/aliases.csv`.
