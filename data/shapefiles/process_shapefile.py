# pyright: reportUnknownMemberType=none

import hashlib
from pathlib import Path
from collections.abc import Mapping, Sequence
import geopandas as gpd

import config  # pyright: ignore[reportImplicitRelativeImport]


def _sha256_for_path(path: Path) -> str:
    """
    If path is a .shp file, hash the whole shapefile bundle
    (all sibling files sharing the same stem, e.g. .shp/.shx/.dbf/.prj/.cpg).
    Otherwise, hash the file itself.
    """
    if path.suffix.lower() == ".shp":
        bundle = sorted(
            (p for p in path.parent.glob(f"{path.stem}.*") if p.is_file()),
            key=lambda p: p.suffix.lower(),
        )

        if not bundle:
            raise FileNotFoundError(f"No shapefile components found for {path}")
        hasher = hashlib.sha256()
        for component in bundle:
            hasher.update(component.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(component.read_bytes())
        return hasher.hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_shapefile(
    shapefile_path: str | Path,
    expected_sha256: str,
    expected_columns: Sequence[str],
    rename_columns: Mapping[str, str],
) -> gpd.GeoDataFrame:
    """
    Validate and transform a shapefile.

    Steps:
      1. Check SHA256.
      2. Check columns match `expected_columns` (non-geometry columns, order ignored).
      3. Rename columns according to `rename_columns`.
    Parameters
    ----------
    shapefile_path:
        Path to the .shp file (or another file to hash directly).
    expected_sha256:
        Expected SHA256 hex digest.
    expected_columns:
        Expected non-geometry column names before any transformation.
    deduplicate_column:
        Column to deduplicate.
    deduplicate_column_with:
        Secondary column used to make `deduplicate_column` unique when needed.
    rename_columns:
        Mapping of old column names -> new column names.
    output_path:
        Optional path to write the transformed shapefile.
    Returns
    -------
    geopandas.GeoDataFrame
        The validated and transformed GeoDataFrame.
    """
    shapefile_path = Path(shapefile_path)
    if not shapefile_path.exists():
        raise FileNotFoundError(f"File not found: {shapefile_path}")
    actual_sha256 = _sha256_for_path(shapefile_path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            f"SHA256 mismatch for {shapefile_path}:\n"
            + f"  expected: {expected_sha256}\n"
            + f"  actual:   {actual_sha256}"
        )
    gdf = gpd.read_file(shapefile_path)
    geometry_col = gdf.geometry.name
    actual_columns = [c for c in gdf.columns if c != geometry_col]
    if set(actual_columns) != set(expected_columns):
        raise ValueError(
            "Column mismatch.\n"
            + f"  expected: {list(expected_columns)}\n"
            + f"  actual:   {actual_columns}"
        )
    gdf = gdf.rename(columns=dict(rename_columns))
    # Guard against accidental duplicate column names after renaming.
    renamed_non_geom = [c for c in gdf.columns if c != geometry_col]
    if len(renamed_non_geom) != len(set(renamed_non_geom)):
        raise ValueError("Renaming introduced duplicate column names.")
    return gdf


if __name__ == "__main__":
    gdf = process_shapefile(
        config.shapefile_path,
        config.expected_sha256,
        config.expected_columns,
        config.rename_columns,
    )
    gdf.to_file(config.output_path)
    print("Wrote", config.output_path)
