This directory contains health-zone level shapefiles for the Democratic Republic of the Congo. The shapefile naming convention is compatible with all other data files in this repository.

A pre-processing script verifies source SHA256 hashes and renames columns to maintain compatibility with the existing pipeline: `Nom` (health zone name), `PROVINCE` (province name) and `ZSCode` (unique code for the health zone). To run the processing, install `geopandas` and run `python process_shapefile.py` after updating [`config.py`](config.py).

# July 13th Shapefile Update
On July 13th we updated the shapefile that underpins this repo to one compatible with the INSP and WHO Sitreps: https://data.grid3.org/datasets/GRID3::grid3-cod-health-zones-v8-0/explore?location=1.709967%2C29.613338%2C8

This shapefile not only has name changes (which should be fully handled by the code and cause minimal issues), but has changes to the actual geometry as pointed out by issue #116. Any population or area denominated datasets on this repo have already been updated to reflect this, so modelling frameworks or analyses that leverage this data should automatically adapt; however this does result in an unavoidable meaningful barrier to compare model outputs from pre-change to post change, should they be based on these different shapefiles.
