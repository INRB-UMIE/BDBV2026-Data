# Bundibugyo Ebola virus outbreak 2026

### Data for the 2026 Bundibugyo Ebolavirus (BDBV) outbreak.

![Logos for Project Lead Organizations: Institute National de Recherche Biomedicale (INRB), One Health Institute for Africa (INOHA), Institut National de Santé Publique (INSP), and Unité de Modélisation et Intelligence Epidémique (UMIE)](https://github.com/INRB-UMIE/BDBV2026-Epidemic_Dashboard/blob/main/Data/Branding/all_logos.png)

This work is led by the Institut National de Recherche Biomédicale (INRB) Kinshasa/One Health Institute for Africa (INOHA) Kinshasa (Dav Ebengo, Placide Mbala-Kingebeni and Tania Bishola), and the Institut National de Santé Publique (INSP) (Pierre Akilimali, Adelard Lofungola).

**Collaborating institutions and agencies**
- Institut National de Santé Publique (INSP)
- National Institute of Biomedical Research (INRB)
- Africa Centres for Disease Control and Prevention, Addis Ababa, Ethiopia
- World Health Organization, Geneva, Switzerland
- World Health Organization Country Office, Kinshasa, Democratic Republic of the Congo
- Northeastern University, United States
- University of Oxford, United Kingdom

### Statement on continuing work and analyses before publication
Please note that the epidemiological data presented here is based on work in progress and should be considered preliminary. Our analyses are ongoing, and a publication communicating our findings is in preparation. Contextual data are publicly accessible; please refer to the original license when re-using these data. If you intend to use the epidemiological data prior to our publication, or have other enquiries, please contact [Prof. Placide Mbala-Kingebeni](mailto:placide.mbala@inrb.cd) (INRB, DRC), [Prof. Dav Ebengo](mailto:dav.ebengo@umie-inrb.org) (INRB, DRC), and [Pierre Akilimali](mailto:pierre.akilimali@insp.cd) (INSP).

Last successful build: **9 June 2026, 07:35:06 (UTC)** — `build/` on `main` at commit [`60230f8`](https://github.com/INRB-UMIE/Ebola_DRC_2026/commit/60230f84b2372154d8b44ca2376d35a40e829cb3) (data snapshot [`60230f8`](https://github.com/INRB-UMIE/Ebola_DRC_2026/commit/60230f8), see `build/manifest.json`).

# Data sources
### Geospatial
-   **DRC health zones:** [Humanitarian Data Exchange](https://data.humdata.org/dataset/drc-health-data) (MoH zones de santé shapefile)

### Epidemiological
-   **Epidemiological data (INSP):** [Institut National de Santé Publique (INSP)](https://insp.cd/) SitRep MVE PDF series (`data/insp_sitrep/`, currently through **SitRep 023**) — daily case, death, and contact-tracing indicators by health zone **manually transcribed from the sitreps**
-   **Processed Linelists:** Following establishment of an epi data collection pipeline by INSP and INRB, aggregated linelist data will be housed in (`data/epi/`)
-   **Operational data (INSP):** [Institut National de Santé Publique (INSP)](https://insp.cd/) Contextual data on the public health response transcribed from SitRep MVE PDF series (`data/insp_sitrep/`, currently for **SitReps 020-023**, but backfilling is in progress) (`data/public_health_response`)
-   **Testing Capacity (AfricaCDC):** data on PCR machine and reagent availability (`data/testing_capacity`)

### Mobility
-   **Road travel times:** [OSRM](http://project-osrm.org/) public demo (`data/osrm/`, matrix outputs)
-   **Cross-border travel:** [Imperial College Report](https://www.imperial.ac.uk/mrc-global-infectious-disease-analysis/research-themes/preparedness-and-response-to-emerging-threats/report-ebola-18-05-2026/)
-   **Internal relocations:** International Organisation for Migrants ([IOM](https://dtm.iom.int))
-   **Mobile phone-based internal relocation estimates:** [Flowminder.org](https://www.flowminder.org/resources/publications-reports/drc-reports-publications) (`data/flowminder/` and `data/flowminder_short_trips/`)

### Demographic
-   **Conflicts and acts of violence:** [ACLED](https://acleddata.com) (`data/ACLED_conflict/`) - Not currently included in build 
-   **Population counts:** [WorldPop](https://www.worldpop.org/) (`data/worldpop/`)
-   **Health facilities (GRID3):** [GRID3 COD Health Facilities v8.0](https://data.grid3.org/datasets/GRID3::grid3-cod-health-facilities-v8-0/about) (`data/grid3_healthsites/`)
-   **Health facilities (OSM / crowdsourced):** [Healthsites.io](https://healthsites.io/) (`data/healthsites_io/`)
-   **Socioeconomic deprivation and inequality:** [Climate-Conflict Vulnerability Index](https://climate-conflict.org/www) (`data/ccvi/`)
-   **Degree of Urbanisation:** [FAO Land Classification System](https://cds.climate.copernicus.eu/datasets/satellite-land-cover?tab=overview) (`data/fao_lccs/`)
-   **GPD per capita:** [Kummu et. al](https://www.nature.com/articles/s41597-025-04487-x) (`data/gdp_pc/`)

For the latest BDBV genomic data, please visit [Pathoplexus](https://pathoplexus.org/ebola-bdbv/search).

## Pending data sources

We are tracking pending data sources over on the [issues tab](https://github.com/kraemer-lab/Ebola_DRC_2026/issues). If you want to request a specific publicly available dataset, raise an issue (although raising an issue does not guarantee that we will incorporate a dataset).

# Current build (2026-06-09)

The current build is committed on `main` and refreshed automatically by CI on every merge that touches `data/**` — see [Release internals](#release-internals). Run `python -m tools.build_geojson` locally only if you're working on a branch with un-merged data changes.

### What's New

<!-- whats-new:start -->
Integration of SITREP 24 data
<!-- whats-new:end -->

### Build contents

Per-layer catalogue for the current build:

- [Embedded in the GeoJSON](data/README.md#embedded-in-the-geojson) — vector layers merged into `build/drc_health_zones.geojson`
- [Matrix outputs](data/README.md#matrix-outputs) — origin–destination tables (not in the GeoJSON)

Full tables live in [`data/README.md`](data/README.md#current-build-outputs). Machine-readable index: `build/manifest.json`.

**Not in build:** `ACLED_conflict` — province-grain placeholder, no QA-passing output yet.

## Past releases

<!-- past-releases:start -->
| Tag | Date | Summary | Download |
|-----|------|---------|----------|
| [`build-2026-06-09-60230f8`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-09-60230f8) | 2026-06-09 | Integration of SITREP 24 data | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-09-60230f8) |
| [`build-2026-06-08-979a344`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-08-979a344) | 2026-06-08 | Adding Pillars od sitrep 21 | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-08-979a344) |
| [`build-2026-06-07-df291a5`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-07-df291a5) | 2026-06-07 | Update data of sitRep 23 from June 6, published on June 7 | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-07-df291a5) |
| [`build-2026-06-06-39fc6f0`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-06-39fc6f0) | 2026-06-06 | Addition of new data according to SitRep 22 | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-06-39fc6f0) |
| [`build-2026-06-05-628c054`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-05-628c054) | 2026-06-05 | Sitrep 21 Adding | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-05-628c054) |
| [`build-2026-06-04-169614d`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-04-169614d) | 2026-06-04 | Data sitrep020, updating for cumulative_confirme_cases, cumulative_confirme_deaths, Nation_cumulative_confirme_cases, Nation_cumulative_confirme_death, Nation_cumulative_isolation | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-04-169614d) |
| [`build-2026-06-03-8d24ff8`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-8d24ff8) | 2026-06-03 | Revised numbers of national cumulative suspected cases given latest reporting (see `data/insp_sitrep/reports/SitRep_MVE_019-2026.md`). | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-8d24ff8) |
| [`build-2026-06-03-06ffe1a`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-06ffe1a) | 2026-06-03 | SitRep 19 data added and digitisation report updated. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-06ffe1a) |
| [`build-2026-06-03-ea78c16`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-ea78c16) | 2026-06-03 | Added public health pillar data | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-03-ea78c16) |
| [`build-2026-06-02-32e9ebd`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-32e9ebd) | 2026-06-02 | Sitrep 18 added, national counts updated and healthzone level counts where reported. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-32e9ebd) |
| [`build-2026-06-02-f3b3051`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-f3b3051) | 2026-06-02 | Flowminder short trip data is now formatted to be visualised in the dashboard. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-f3b3051) |
| [`build-2026-06-02-125e4e0`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-125e4e0) | 2026-06-02 | Report added for Sitrep 17 describing digitisation process | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-125e4e0) |
| [`build-2026-06-02-d1ceb9c`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-d1ceb9c) | 2026-06-02 | Sitrep 17 Added | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-02-d1ceb9c) |
| [`build-2026-06-01-b4cafc9`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-01-b4cafc9) | 2026-06-01 | Updates to SitReps 15 and 16 | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-01-b4cafc9) |
| [`build-2026-06-01-0a87d65`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-01-0a87d65) | 2026-06-01 | \- National level tables now just take the nom 'DRC' | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-06-01-0a87d65) |
| [`build-2026-05-30-507a2a2`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-507a2a2) | 2026-05-30 | \- Added sitrep 14 (in reality fix some issues with sitrep 14, but those issues aborted the earlier release so this is the first release with sitrep 14 anyway | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-507a2a2) |
| [`build-2026-05-30-e125835`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-e125835) | 2026-05-30 | Latest release fixing a number of minor processing issues in past sitreps. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-e125835) |
| [`build-2026-05-30-5a34b18`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-5a34b18) | 2026-05-30 | An additional data folder `flowminder_short_trips/` is created. This contains updated Flowminder data for short trips for April 2026 (see report in `data/raw/` for details). QA tests show warnings in unrelated `data/**` folders. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-30-5a34b18) |
| [`build-2026-05-29-ff1e796`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-29-ff1e796) | 2026-05-29 | Sitrep 13 added. | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-29-ff1e796) |
| [`build-2026-05-28-bb8b7d5`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-28-bb8b7d5) | 2026-05-28 | Updated to allocate a new suspected case from Mabanga (not a healthzone) to the Mambasa healthzone. Team at INRB reviewed and decided this is the most accurate place to put it for now, but let's note that there may also be a place called Mabanga in Mangala | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-28-bb8b7d5) |
| [`build-2026-05-27-e40bc9e`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-e40bc9e) | 2026-05-27 | \- Healthzone level wpi data up to 26th May from INSP (The public sitrep did not have this data) | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-e40bc9e) |
| [`build-2026-05-27-059661a`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-059661a) | 2026-05-27 | \- Updated INSP Sitrep data with the new version of Sitrep 12 (Updated national suspected deaths) | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-059661a) |
| [`build-2026-05-27-af1f2b5`](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-af1f2b5) | 2026-05-27 | \- Added the updated DRC totals from SitRep 12 to a new metric for that dataset with prefix national\_\* | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-27-af1f2b5) |
| build-2026-05-26-683a564 | 2026-05-26 | INSP Sitrep data through report 010 | [release](https://github.com/INRB-UMIE/Ebola_DRC_2026/releases/tag/build-2026-05-26-683a564) |
| [`build-2026-05-22-12db0c2`](https://github.com/kraemer-lab/Ebola_DRC_2026/releases/tag/build-2026-05-22-12db0c2) | 2026-05-22 | 25 vector layers; INSP through SitRep 007 + GRID3 health facilities | [release](https://github.com/kraemer-lab/Ebola_DRC_2026/releases/tag/build-2026-05-22-12db0c2) |
| [`build-2026-05-22-9694d10`](https://github.com/kraemer-lab/Ebola_DRC_2026/releases/tag/build-2026-05-22-9694d10) | 2026-05-22 | First GitHub release (11 vector layers; pre-INSP / pre-GRID3) | [release](https://github.com/kraemer-lab/Ebola_DRC_2026/releases/tag/build-2026-05-22-9694d10) |
<!-- past-releases:end -->

# Repository layout

```         
data/
  README.md                  index of all dataset folders
  shapefiles/                source of truth for health-zone boundaries
  aliases.csv                observed_name -> canonical_nom mappings
  <dataset>/                 one folder per source
    raw/                     untouched source files
    process.{py,R}           script that produces files in processed/
    processed/               standardized contract-conformant outputs
    metadata.yaml            source, citation, retrieved_on, license, contact, runtime
    README.md                optional human notes
tools/
  lib/schema.py              canonical Noms, alias resolver, filename contract
  qa.py                      walks data/, validates, writes qa/qa_log.csv & qa/matrix_log.csv
  build_geojson.py           merges passing non-matrix outputs into build/drc_health_zones.geojson
  requirements.txt           pyshp, pyyaml, shapely
qa/
  qa_log.csv                 per-artifact QA results (all statuses)
  matrix_log.csv             catalog of QA-passing matrices
  reports/<dataset>.md       per-folder human-readable report
build/
  drc_health_zones.geojson   shapefile + latest per-zone values
  long/<dataset>__<metric>.csv  full long-format copy of each vector file
  manifest.json              sources + build timestamp
```

# Data contract

**Join key:** the canonical `Nom` from `data/shapefiles/DRC_Health_zones.shp`. The two natural collisions (`Bili`, `Lubunga`) are disambiguated with a province suffix, e.g. `Lubunga (Tshopo)`. Observed spellings that differ are listed in `data/aliases.csv`. Province roll-ups use `nom` = shapefile `PROVINCE` (aliases in `data/province_aliases.csv`); national roll-ups use `nom = DRC`.

**Processed-file naming:** `<dataset>__<metric>__<resolution>.{csv|matrix.csv}` - `<dataset>` and `<metric>` are lower_snake_case. - `<resolution>` ∈ {`static`, `daily`, `weekly`, `monthly`, `yearly`}. - Suffix is `.matrix.csv` for matrix outputs, `.csv` for vector (one-row-per-zone) outputs.

**Vector files** carry a `nom` column. Non-static resolutions also carry a `date` column (ISO 8601).

**Matrix files** (`.matrix.csv`): snapshot matrices have header `nom, <dest_nom_1>, ...`; time-series matrices have `date, nom, <dest_nom_1>, ...`. Present cells must be non-negative numeric; missing values may be empty or `NA` (e.g. unroutable OSRM pairs).

# Contributor flow

Contributors add or update data. PRs touch `data/**` (and `tests/**` and unrelated docs only) — never `build/`, `qa/`, `dist/`, or `README.md`'s build/release sections.

0.  One-time setup (anyone cloning):

    ```         
    git lfs install
    python -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
    ```

    LFS is required because binary raw blobs (`*.xlsx`, `*.zip`, `*.pdf`, `*.tif`, etc.) under `data/*/raw/` are stored via Git LFS — see `.gitattributes`.

1.  Create `data/<your_dataset>/` with `raw/`, `metadata.yaml`, and (when you have outputs) `process.{py,R}` + `processed/`.

2.  Make sure your processed filenames match the contract above. Add zone aliases to `data/aliases.csv` and province aliases to `data/province_aliases.csv` when needed.

3.  Sync with main:

    ```         
    git merge origin/main
    ```

4.  Run unit tests + QA locally:

    ```         
    .venv/bin/python -m pytest tests/
    .venv/bin/python -m tools.qa
    ```

5.  *(Optional)* Rebuild the merged GeoJSON locally to sanity-check your changes:

    ```         
    .venv/bin/python -m tools.build_geojson --skip-readme
    ```

    **Do not commit the resulting `build/`, `qa/qa_log.csv`, `qa/matrix_log.csv`, `qa/reports/`, or `README.md` updates.** Those land on `main` automatically when an admin merges your PR; including them in your PR causes merge conflicts and gets flagged in review.

6.  Open a PR. **Fill in the `## What's new` section** in the PR body (template provided) — that text becomes the GitHub Release description and the README "what's new" block when this PR is released. CI runs `pytest` + `tools.qa` and blocks merge on any failures.

7.  Wait for admin review and merge. You don't run a release — CI does that automatically.

# Admin flow

Admins (maintainers with write access to `main`) review PRs and merge.

1.  Review the PR: data diff, CI green, `## What's new` section populated and accurate, contributor checklist ticked.

2.  Merge to `main`. **That's it for the common case** — the release workflow takes over.

Escape hatches:

-   **Suppress release for a trivial change** (e.g. typo fix in a metadata file): include `[skip release]` in the merge commit message. CI will skip the release step.

-   **Force a release without a data change** (e.g. after fixing `tools/build_geojson.py`): go to the Actions tab → "Release on data merge" → "Run workflow", and supply a description via the manual input.

-   **Emergency local release** (CI is down): pull `main`, then run the same sequence the CI workflow runs:

    ```         
    .venv/bin/python -m tools.qa
    .venv/bin/python -m tools.build_geojson
    .venv/bin/python -m tools.release                   # interactive; packs dist/<tag>.tar.gz + updates README
    git add build/ qa/qa_log.csv qa/matrix_log.csv qa/reports/ README.md
    git commit -m "New build YYYY-MM-DD"
    git push
    .venv/bin/python -m tools.publish                   # creates the GitHub Release pointing at HEAD
    ```

    The publish step is separate from the pack step so the GitHub Release tag points at the commit that contains the build artifacts (the push above), not the pre-build merge commit.

Maintainers who will cut emergency local releases also need:

-   `gh` CLI installed and authenticated (`gh auth login`) — required by `tools.publish`, not by `tools.release`.
-   `$EDITOR` set (used by `tools.release` for the interactive description prompt).

# Release internals {#release-internals}

The release workflow (`.github/workflows/release.yml`) runs on `push` to `main` when `data/**` changes (and on manual `workflow_dispatch`).

What it does, in order:

1.  Bails if the HEAD commit message contains `[skip release]`.
2.  Extracts the `## What's new` section from the merge commit's PR body (via `gh api`).
3.  Runs `python -m tools.qa`.
4.  Runs `python -m tools.build_geojson`.
5.  Runs `python -m tools.release --description-file <tmp> --non-interactive`, which packs `build/` as `dist/<tag>.tar.gz`, persists the description as `dist/<tag>.description.md`, and updates the README. This step does NOT publish anything.
6.  Commits and pushes the resulting `build/`, `qa/`, and `README.md` back to `main` with `[skip release][skip ci]` in the commit message to prevent recursive triggering.
7.  Runs `python -m tools.publish`, which calls `gh release create <tag> dist/<tag>.tar.gz --target $(git rev-parse HEAD) ...`. Because this runs *after* the commit-back, the release tag points at the commit that contains the build artifacts in its tree — not at the pre-build merge commit. The release URL is determined by `<tag>` and matches what `tools.release` wrote into the README in step 5.
8.  Dispatches a dashboard rebuild to `BDBV2026-Epidemic_Dashboard` on `main`, using the commit SHA from step 6 (the build-artifact commit). Requires `DASHBOARD_DISPATCH_TOKEN` on this repo; skips with a warning if unset.

The pre-existing `qa.yml` workflow runs `pytest` + `tools.qa` on PRs as the merge gate; it does not trigger on `build/`, `qa/`, or `README.md` changes, so the release workflow's commit-back does not retrigger it. The separate *Trigger dashboard rebuild* workflow is manual-only (escape hatch); production dashboard updates come from step 8 above.

# Citation

Please cite the original data providers (links above) and this repository if any code or derived data is reused.

# License and warranty

The repository code is licensed under the terms in LICENSE. We do not claim ownership of or the right to license the third-party data or software tools used. Please pass forward any existing license/warranty/copyright information when redistributing.

*THE DATA AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT.*
