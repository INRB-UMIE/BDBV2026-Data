"""Configuration for process_shapefile.py"""

shapefile_path = "./GRID3_COD_health_zones_v8_0.shp"
expected_sha256 = "b332f7de52044e1aa3b8be9fb07887b25ec214d4b913244685f07420ef943b04"
expected_columns = [
    "pays",
    "iso3",
    "province",
    "prov_uid",
    "antenne",
    "zonesante",
    "zs_uid",
    "date",
    "edit_par",
    "source_acr",
    "grid3id",
    "sourceid",
]
rename_columns = {"zonesante": "Nom", "zs_uid": "ZSCode", "province": "PROVINCE"}
output_path = "./DRC_Health_zones.shp"
