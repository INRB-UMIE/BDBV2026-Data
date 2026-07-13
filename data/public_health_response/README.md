# Public health response — INSP SitRep pillar narratives

Operational public-health-response pillar text (coordination, surveillance, case management, laboratory, infection prevention & control, logistics, security, community engagement, protection from sexual exploitation & abuse), manually extracted from INSP SitRep MVE PDFs in `raw/`.

## Grain and `nom`

Processed vectors are stored as `public_health_response__<pillar>__daily.csv` (`nom`, `date`, and a text value column with the reported activity), at three grains:

- **Health zone** — `nom` is the zone explicitly mentioned in the SitRep.
- **National** — `nom = DRC`, for activity reported without reference to a specific zone or province (`national_*` files).
- **Province** — `nom` is the shapefile `PROVINCE` name (English sitrep spellings mapped via `data/province_aliases.csv`), for activity reported at province level (`provincial_*` files). The GeoJSON build broadcasts each provincial row to every health zone in that province.

**Kinshasa, Lualaba, and Tshopo are each both a province and a health zone of the same name.** Zone identity always wins on that collision: a plain `nom = Tshopo` row is read as the health zone, not the province. If a `provincial_*` file ever needs a genuine province-wide row for one of these three, `nom` must be written as `"<Province> (province)"` — e.g. `Tshopo (province)` — otherwise the row silently attaches to the health zone instead of broadcasting across the province. See [`data/README.md`](../README.md), "Province roll-ups".

`nom` may contain `NA` when no valid geographic assignment can be made. Health zone names are normalised to canonical names during processing.

## Related data

Complements [`data/epi/`](../epi/) (WHO external sitrep) and [`data/insp_sitrep/`](../insp_sitrep/) (INSP quantitative indicators) — this dataset carries the narrative/operational side of the same SitRep series.
