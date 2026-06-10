# Archived WHO situation reports

Public **WHO Weekly External Situation Reports** on the 2026 Bundibugyo Ebola virus outbreak in the Democratic Republic of the Congo (DRC), stored as untouched PDFs under `raw/`.

This folder is where we keep relevant, publicly facing documents for posterity, even if they are not explicitly integrated into the GeoJSON build or part of a dataset we are tracking. There is **no** `process.py`, **no** `processed/` directory, and **no** QA contract outputs — only archived source PDFs.

Digitised case and death tables appear separately when extracted for the map build; this folder preserves the original reports as published.

------------------------------------------------------------------------

## Files

| File | Description |
|----|----|
| `raw/WHO_Wk_Ext_SitRep*.pdf` | Untouched WHO weekly external situation report PDFs |
| `metadata.yaml` | Provenance, licence, and archive notes |

**No `processed/` outputs** — see **Data quality and limitations** and `metadata.yaml`.

------------------------------------------------------------------------

## Raw documents

**Source:** [World Health Organization](https://www.who.int) — Weekly External Situation Reports on the 2026 Bundibugyo Ebola virus outbreak in DRC.

**Coverage (current archive):**

| File | Report | Data as of |
|----|----|----|
| `raw/WHO_Wk_Ext_SitRep01_18_05_2026.pdf` | SitRep 01 | 2026-05-18 |
| `raw/WHO_Wk_Ext_SitRep02_24_05_2026.pdf` | SitRep 02 | 2026-05-24 |
| `raw/WHO_Wk_Ext_SitRep03_31_05_2026.pdf` | SitRep 03 | 2026-05-31 |
| `raw/WHO_Wk_Ext_SitRep04_07_06_2026.pdf` | SitRep 04 | 2026-06-07 |

**Naming convention:** `WHO_Wk_Ext_SitRep<NN>_<DD>_<MM>_<YYYY>.pdf` — report number and the sitrep “data as of” date.

------------------------------------------------------------------------

## Method (current state)

1. **Download** — Obtain the published PDF from WHO when a new weekly external sitrep is released.
2. **Store** — Place the untouched file under `raw/` using the naming convention above.
3. **Update metadata** — Adjust `metadata.yaml` (`retrieved_on`, file list in `notes`) when adding reports.

There is no downstream processing in this folder.

**What this is not**

- Not a tracked dataset with contract-shaped CSV outputs.
- Not merged into `build/drc_health_zones.geojson`.
- Not a substitute for [`data/epi/`](../epi/) or [`data/insp_sitrep/`](../insp_sitrep/) where outbreak indicators are digitised for analysis.

------------------------------------------------------------------------

## Regenerating outputs

There is **no** `process.py` in this folder and no processed outputs to regenerate. To refresh the archive:

1. Download new or updated WHO weekly external sitrep PDFs.
2. Add them under `raw/` and update `metadata.yaml`.

------------------------------------------------------------------------

## Data quality and limitations

| Issue | Detail |
|----|----|
| **Archive only** | PDFs are stored for reference; contents are not automatically parsed or validated here. |
| **Not in build** | `metadata.yaml` sets `status: archive`; root and [`data/README.md`](../README.md) list this folder as outside the GeoJSON pipeline. |
| **Licence** | WHO open access. Reuse with attribution per [WHO copyright policy](https://www.who.int/about/policies/publishing/copyright). |

------------------------------------------------------------------------

## Provenance

- **Provider:** [World Health Organization](https://www.who.int)
- **Raw files:** `raw/WHO_Wk_Ext_SitRep*.pdf`
- **Metadata:** `metadata.yaml`

For project-wide data conventions, see [`data/README.md`](../README.md).
