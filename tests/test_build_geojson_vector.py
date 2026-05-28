import csv
from types import SimpleNamespace

from tools import build_geojson


def test_attach_vector_ignores_empty_header(tmp_path, monkeypatch):
    """
    Checks that we're not including an empty header col in geoJSON output data if
    row.names were present from R CSV output
    """
    folder = tmp_path / "example"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(processed / "example__metric__static.csv", "w", encoding="utf-8") as fp:
        fp.write(",nom,value\n1,Rwampara,42\n")

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)
    monkeypatch.setattr(build_geojson, "to_canonical", lambda name: name)

    feature = {"properties": {}}
    attached = build_geojson._attach_vector(
        folder,
        "example__metric__static.csv",
        SimpleNamespace(dataset="example", metric="metric"),
        {"Rwampara": feature},
    )

    # Check that things were attached
    assert attached == 1

    # Check that long data is parsed correctly
    with open(long_dir / "example__metric.csv", newline="") as fp:
        reader = csv.DictReader(fp)
        assert reader.fieldnames is not None
        assert "" not in reader.fieldnames, "Empty col in long output"
    

    # Check geo features
    values = feature["properties"]["example"]["metric"]
    assert values == {"value": 42}
    assert "" not in values
