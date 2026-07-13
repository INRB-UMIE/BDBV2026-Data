# genomic_surveillance

Counts of BDBV 2026 whole-genome sequences per DRC health zone, aggregated from the reconciled consensus sequence metadata to the canonical health-zone (`Nom`) grain.

## What the raw data is

`raw/bia_fasta_metadata_consensus_v0.1.tsv` is the consensus metadata table produced by the `BDBV2026-Phylogenetic-analyses` repository. It has **one row per sequenced genome** (`taxa`), with a single reconciled value per field:

| Column | Meaning |
|--------|---------|
| `taxa` | FASTA sequence name |
| `lab_location` | Sequencing lab (Bunia / Kinshasa) |
| `match_scope` | Which linelists the sequence matched (`both`, `lab_only`, `dhis_only`, `none`) |
| `province` | Consensus province |
| `health_zone` | Consensus health zone |
| `collection_date` | Consensus collection date |
| `sex` | Consensus sex |
| `age` | Consensus age |

Each `health_zone` was reconciled across the FASTA header and the lab / DHIS2 linelists upstream; where sources disagreed, the health zone was resolved to the FASTA header value (see the upstream `bia_fasta_metadata_ambiguities_v0.1.tsv` log). As a result every sequence carries a health zone in this snapshot.

## How `process.py` aggregates to health zones

1. Reads `raw/bia_fasta_metadata_consensus_v0.1.tsv`.
2. Resolves each row's consensus `health_zone` to a canonical shapefile `Nom` via `data/aliases.csv` (`tools.lib.schema.to_canonical`).
3. Counts sequences per resolved zone and writes `processed/genomic_surveillance__sequence_count__static.csv` with columns `nom, sequence_count`.
4. Writes `process_log.csv` — one row per sequence (`taxa, health_zone, province, resolved_nom, status`) as an audit trail. `status` is `assigned` (resolved to a zone), `unresolved` (health zone did not map to a `Nom`), or `no_zone` (blank / `TBD`).

The current run assigns **all 139 sequences** across **16 health zones**, with **0 unresolved** and **0 without a zone**.

## Caveats for users of the processed data

- **Count of sequenced genomes, not cases.** `sequence_count` reflects how many genomes were sequenced and located to a zone; it is not a case count and is subject to sampling and sequencing-capacity bias.
- **Geography is Ituri-dominated.** 138 of 139 sequences are in Ituri and 1 in Nord-Kivu; the largest zones are `Bunia` (52) and `Rwampara` (45).
- **Health zones are the consensus value.** Where the source linelists disagreed, the health zone was resolved to the FASTA header value upstream. The full conflict log lives in the phylogenetics repo (`bia_fasta_metadata_ambiguities_v0.1.tsv`).
- **Static resolution.** The processed file is a snapshot. Collection dates are available per sequence in the raw table but are not aggregated into a time series here.
- **Build pipeline join.** The processed file conforms to the data contract: it carries a `nom` column with canonical zone names, so it will be merged into `build/drc_health_zones.geojson` by `tools/build_geojson.py` as `feature.properties.genomic_surveillance.sequence_count`.

## Reproducing

From the repo root, with the project venv active:

```
python data/genomic_surveillance/process.py     # writes processed/ and process_log.csv
```

To refresh the raw input, re-copy the latest consensus table from
`BDBV2026-Phylogenetic-analyses/data/processed/fasta_linelist_matching/bia_fasta_metadata_consensus_v0.1.tsv`
into `raw/` and re-run the script.
