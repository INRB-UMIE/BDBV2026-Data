import csv
from types import SimpleNamespace

from tools import build_geojson
from tools.lib.schema import NATIONAL_ROLLUP_NOM


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
    monkeypatch.setattr(build_geojson, "resolve_vector_nom", lambda name: name)

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


def test_attach_vector_skips_non_geographic_nom(tmp_path, monkeypatch):
    folder = tmp_path / "insp_sitrep"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(processed / "insp_sitrep__metric__daily.csv", "w", encoding="utf-8") as fp:
        fp.write("nom,date,value\nBunia,2026-05-20,1\nSans Fiche,2026-05-20,99\n")

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    bunia_feat = {"properties": {}}
    attached = build_geojson._attach_vector(
        folder,
        "insp_sitrep__metric__daily.csv",
        SimpleNamespace(dataset="insp_sitrep", metric="metric"),
        {"Bunia": bunia_feat},
    )

    assert attached == 1
    assert "insp_sitrep" in bunia_feat["properties"]
    assert bunia_feat["properties"]["insp_sitrep"]["metric"]["value"] == 1


def test_attach_vector_broadcasts_drc_to_all_zones(tmp_path, monkeypatch):
    folder = tmp_path / "insp_sitrep"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(
        processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write(
            "nom,date,national_cumulative_confirmed_cases\n"
            f"{NATIONAL_ROLLUP_NOM},2026-05-20,100\n"
            f"{NATIONAL_ROLLUP_NOM},2026-05-24,121\n"
        )

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    bunia = {"properties": {}}
    goma = {"properties": {}}
    attached = build_geojson._attach_vector(
        folder,
        "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
        __import__("types").SimpleNamespace(
            dataset="insp_sitrep",
            metric="national_cumulative_confirmed_cases",
        ),
        {"Bunia": bunia, "Goma": goma},
    )

    assert attached == 2
    for feat in (bunia, goma):
        val = feat["properties"]["insp_sitrep"]["national_cumulative_confirmed_cases"]
        assert val["national_cumulative_confirmed_cases"] == 121
        assert val["_date"] == "2026-05-24"
