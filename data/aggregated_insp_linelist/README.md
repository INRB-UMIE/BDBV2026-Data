# Aggregated INSP / INRB line list — province-level onset counts

Daily **confirmed-case counts by province and date of symptom onset**, derived from the operational MVE epidemic line list maintained jointly by the **Institut National de Santé Publique (INSP)** and the **Institut National de Recherche Biomédicale (INRB)**.

The underlying line list is **private and confidential**: it contains individual case reports and is not stored in this repository. Only **aggregated totals** are committed here, to support outbreak mapping and analytics without exposing patient-level data.

## What is published here

| Location | Contents |
|----|----|
| `raw/province_aggregated.csv` | Province-level extract copied from the linelist pipeline (`province`, `date_of_symptom_onset`, `total_positive`) |
| `processed/aggregated_insp_linelist__confirmed_cases_onset__daily.csv` | Contract-shaped province series (`nom`, `date`, `confirmed_cases_onset`) |
| `processed/aggregated_insp_linelist__national_confirmed_cases_onset__daily.csv` | National roll-up (`nom = DRC`, one row per onset date) |

Counts reflect **laboratory-confirmed cases** (`final_mve_result == "positive"`) grouped by symptom-onset date. This is **not** the same as INSP SitRep reporting dates in `data/insp_sitrep/` — sitreps report operational indicators by report date and often at health-zone grain.

## Provenance

-   **Source:** DHIS2 MVE line list export, cleaned and aggregated in the private [`BDBV2026-Linelist_Processing`](https://github.com/INRB-UMIE/BDBV2026-Linelist_Processing) repository
-   **Custodians:** INSP (`pierre.akilimali@insp.cd`) and INRB (`dav.ebengo@umie-inrb.org`)
-   **License:** Internal operational data; redistribution requires INSP/INRB approval

Do not republish raw line-list files or attempt to re-identify individual cases from these aggregates.

## Processing

### Automated sync from the linelist repository

The private [`BDBV2026-Linelist_Processing`](https://github.com/INRB-UMIE/BDBV2026-Linelist_Processing) repo exposes a **manual** GitHub Action (**Sync province aggregate to data repo**) that copies `province_aggregated.csv`, runs `process.R` here, pushes to `main`, and dispatches the data-repo release workflow (QA + GeoJSON build).

### Manual update

From the **BDBV2026-Data repo root**, after placing an updated `province_aggregated.csv` in `raw/`:

``` bash
Rscript data/aggregated_insp_linelist/process.R
```

`process.R` maps province names to canonical shapefile `PROVINCE` values (via `data/province_aliases.csv`), normalises dates to ISO `YYYY-MM-DD`, and writes the two processed files.

Then validate and rebuild:

``` bash
.venv/bin/python -m tools.qa aggregated_insp_linelist
.venv/bin/python -m tools.build_geojson
```

Province-level rows are **broadcast to all health zones in that province** during the GeoJSON build (same pattern as `public_health_response__provincial_*` files). National rows use `nom = DRC`.

## Related data

| Dataset | Grain | Date semantics |
|----|----|----|
| `data/insp_sitrep/` | Health zone (+ national banner) | SitRep report date |
| `data/aggregated_insp_linelist/` (this folder) | Province (+ national roll-up) | Date of symptom onset |
| `data/epi/` | Health zone | WHO external sitrep week |

Dashboard **Trends** charts are built separately from the linelist repo (`dashboard_plots/` SVGs), not from these contract CSVs.
