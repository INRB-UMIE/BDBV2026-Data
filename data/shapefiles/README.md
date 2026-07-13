This directory contains health-zone level shapefiles for the Democratic Republic of the Congo. The shapefile naming convention is compatible with all other data files in this repository.

A pre-processing script verifies source SHA256 hashes and renames columns to maintain compatibility with the existing pipeline: `Nom` (health zone name), `PROVINCE` (province name) and `ZSCode` (unique code for the health zone). To run the processing, install `geopandas` and run `python process_shapefile.py` after updating [`config.py`](config.py).
