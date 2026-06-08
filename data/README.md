# Data directory

All outbreak-related sources in this repository are harmonised to the same **519 MoH health zones** (`shapefiles/DRC_Health_zones.shp`). Each source lives in its own folder; processing scripts turn `raw/` inputs into contract-shaped files in `processed/`. The merged map product is `build/drc_health_zones.geojson`. See [Current build outputs](#current-build-outputs) below for the per-layer catalogue; release history and what's new are in the [root README](../README.md).

## How folders are organised

Every dataset folder follows the same layout:

```
<dataset>/
  raw/              # untouched downloads (many files tracked with Git LFS)
  processed/        # outputs ready for QA and GeoJSON build
  metadata.yaml     # source, citation, license, retrieved_on, contact
  process.{py,R}    # optional; regenerates processed/
  README.md         # optional notes (provenance, quirks, plots)
  README_FR.md      # optional French translation; link from README.md header
```

**Join key:** canonical zone name `nom`, matching the shapefile attribute `Nom`. Spellings that differ from the shapefile are listed in [`aliases.csv`](aliases.csv) (including disambiguation of duplicate names such as `Bili` and `Lubunga` with a province suffix).

**Filenames:** `<dataset>__<metric>__<resolution>.csv` for per-zone tables, or `.matrix.csv` for origin–destination tables between zones. Full rules are in the root README *Data contract* section.

**Vectors vs matrices:** vector files have one row per zone (plus `date` for daily/weekly series). Matrix files are zone×zone tables (OSRM, IOM IDP, Flowminder); they are QA-catalogued but not embedded in the GeoJSON.

## Datasets

| Folder | Kind | In GeoJSON build | Notes |
|--------|------|------------------|-------|
| [`shapefiles/`](shapefiles/) | geometry | (base layer) | Source of truth for boundaries and `Nom` |
| [`epi/`](epi/) | vector | yes | WHO weekly external sitrep |
| [`insp_sitrep/`](insp_sitrep/) | vector (daily) | yes | INSP SitRep MVE 001–012 (003 missing); 28 metrics; zone + national totals |
| [`cross-border-movements/`](cross-border-movements/) | vector | yes | Imperial College POE passenger estimates |
| [`worldpop/`](worldpop/) | vector | yes | GRID3/Kummu-style population count & density |
| [`gdp_pc/`](gdp_pc/) | vector | yes | GDP per capita (PPP) |
| [`ccvi/`](ccvi/) | vector | yes | Climate Conflict Vulnerability Index |
| [`fao_lccs/`](fao_lccs/) | vector | yes | Urban land-cover fraction ([FR](fao_lccs/README_FR.md)) |
| [`grid3_healthsites/`](grid3_healthsites/) | vector | yes | GRID3 COD health facilities v8.0 |
| [`healthsites_io/`](healthsites_io/) | vector | yes | OSM / Healthsites.io subset |
| [`refugee_sites/`](refugee_sites/) | vector | yes | UNHCR refugee sites per zone |
| [`osrm/`](osrm/) | matrix | no | Car travel time & road distance (OSRM) |
| [`IDP/`](IDP/) | matrix | no | IOM DTM displacement flows (Ituri round) |
| [`flowminder/`](flowminder/) | matrix | no | Phone-based inflow/outflow estimates |
| [`ACLED_conflict/`](ACLED_conflict/) | — | no | Placeholder; province-level raw data only |

Folders with a **README** go deeper on provenance and processing. `metadata.yaml` is the machine-readable record used by `tools.qa` and `tools.build_geojson`.

**Bilingual docs:** GitHub only auto-renders `README.md` in a folder. Where `README_FR.md` exists (e.g. `fao_lccs/`), a **Language / Langue** line at the top of both files links between English and French — there is no built-in toggle on github.com.

## Current build outputs

Reflects the build committed on `main` as of **2026-06-08** (`build/manifest.json`). The root [README](../README.md) summarises release history and what's new.

### Embedded in the GeoJSON

Each per-zone vector output appears under `feature.properties.<dataset>.<metric>` (matrices are excluded; see below). Daily series use the latest `date` per zone in the build snapshot:

| Folder | Output | Retrieved | Status |
|------------------|------------------|------------------|------------------|
| ccvi | `ccvi__socioeconomic_deprivation__static.csv` | 2026-05-20 | active |
| ccvi | `ccvi__socioeconomic_inequality__static.csv` | 2026-05-20 | active |
| cross-border-movements | `cross_border__poe_passengers__static.csv` | 2026-05-18 | active |
| epi | `epi__cases__weekly.csv` | 2026-05-18 | active |
| epi_mve_inrb_app | `epi_mve_inrb_app__recorded_cases__daily.csv` | 2026-05-28 | active |
| fao_lccs | `fao_lccs__urban_fraction__static.csv` | 2026-05-20 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260430__static.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260507__static.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260514__static.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260521__static.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260524__static.csv` | 2026-05-28 | active |
| gdp_pc | `gdp_pc__gdp_pc__static.csv` | 2026-05-20 | active |
| grid3_healthsites | `grid3_healthsites__healthsite_count__static.csv` | 2026-05-20 | active |
| grid3_healthsites | `grid3_healthsites__healthsite_density__static.csv` | 2026-05-20 | active |
| healthsites_io | `healthsites_io__healthsite_count__static.csv` | 2026-05-20 | active |
| healthsites_io | `healthsites_io__healthsite_density__static.csv` | 2026-05-20 | active |
| insp_sitrep | `insp_sitrep__contacts_seen__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_confirmed_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_confirmed_deaths__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_contacts_isolated__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_contacts_traced__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_suspected_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__cumulative_suspected_deaths__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__hosp_escaped__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__hospitalised__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__in_bed_previous_day__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_cumulative_confirmed_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_cumulative_confirmed_deaths__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_cumulative_suspected_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_cumulative_suspected_deaths__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_suspected_cases_in_isolation__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__national_suspected_cases_under_investigation__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_confirmed_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_contacts_isolated__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_contacts_listed__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_hosp_admissions__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_hosp_detainees__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_hosp_other__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_suspected_cases__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__new_suspected_deaths__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_hand_washing__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_passed__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_refused_hand_washing__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_refused_screening__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_sanitised__daily.csv` | 2026-06-06 | active |
| insp_sitrep | `insp_sitrep__total_poe_screened__daily.csv` | 2026-06-06 | active |
| public_health_response | `public_health_response__epidemiological_community_engagement__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_coordination__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_infection_prevention_controle__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_laboratory__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_logistics__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_management__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_monitoring__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_protection_sexual_exploitation_abuse__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__epidemiological_security__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_community_engagement__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_coordination__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_infection_prevention_controle__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_laboratory__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_logistics__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_management__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_monitoring__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_protection_sexual_exploitation_abuse__daily.csv` | 2026-06-01 | active |
| public_health_response | `public_health_response__national_epidemiological_security__daily.csv` | 2026-06-01 | active |
| refugee_sites | `refugee_sites__sites__static.csv` | 2026-05-20 | active |
| testing_capacity | `testing_capacity__pcr_machines__static.csv` | 2026-05-26 | active |
| testing_capacity | `testing_capacity__pcr_tests__static.csv` | 2026-05-26 | active |
| worldpop | `worldpop__pop_count__static.csv` | 2026-05-20 | active |
| worldpop | `worldpop__pop_density__static.csv` | 2026-05-20 | active |

### Matrix outputs

Large origin–destination tables (519×519 for national sources). Not merged into `build/drc_health_zones.geojson`; use the files under `data/<dataset>/processed/` or the catalogue in [`qa/matrix_log.csv`](../qa/matrix_log.csv).

| Folder | Output | Retrieved | Status |
|--------|--------|-----------|--------|
| osrm | `osrm__travel_time__static.matrix.csv` | 2026-03-17 | active |
| osrm | `osrm__road_distance__static.matrix.csv` | 2026-03-17 | active |
| IDP | `idp__individuals__static.matrix.csv` | 2026-01-31 | active |
| IDP | `idp__individuals__weekly.matrix.csv` | 2026-01-31 | active |
| IDP | `idp__individuals__monthly.matrix.csv` | 2026-01-31 | active |
| flowminder | `flowminder__inflow__static.matrix.csv` | 2026-05-20 | active |
| flowminder | `flowminder__outflow__static.matrix.csv` | 2026-05-20 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260430__static.matrix.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260507__static.matrix.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260514__static.matrix.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260521__static.matrix.csv` | 2026-05-28 | active |
| flowminder_short_trips | `flowminder_short_trips__outflow_20260524__static.matrix.csv` | 2026-05-28 | active |

**Notes:** `grid3_healthsites` and `healthsites_io` both supply facility count/density — GRID3 is the MoH/partner master list. OSRM matrices may contain `NA` for unroutable pairs (QA warn). **`public_health_response`** pillar text is embedded in the GeoJSON for the dashboard Context tab but is not exposed as numeric map layers.

**Not in build:** [`ACLED_conflict/`](ACLED_conflict/) — province-grain placeholder, no QA-passing output yet.

## Working with this tree

From the repo root (after `git lfs install` and a venv with `tools/requirements.txt`):

```bash
.venv/bin/python -m tools.qa              # validate all processed outputs
.venv/bin/python -m tools.build_geojson   # refresh build/drc_health_zones.geojson
```

To add or refresh a source: update `raw/`, run that folder’s `process.py` or `process.R`, check `metadata.yaml`, run QA, then rebuild. Contributor steps are in the [root README](../README.md#contributor-flow).

## Root-level files

| File | Role |
|------|------|
| [`aliases.csv`](aliases.csv) | Maps observed zone labels → canonical `nom` |
| [`shapefiles/`](shapefiles/) | `DRC_Health_zones.*` — do not rename zones here without updating aliases and reprocessing dependents |
