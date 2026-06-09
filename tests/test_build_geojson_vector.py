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


def test_attach_vector_header_only_placeholder(tmp_path, monkeypatch):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(
        processed / "public_health_response__national_epidemiological_laboratory__daily.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write("nom,date,national_laboratory\n")

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    attached = build_geojson._attach_vector(
        folder,
        "public_health_response__national_epidemiological_laboratory__daily.csv",
        SimpleNamespace(
            dataset="public_health_response",
            metric="national_epidemiological_laboratory",
        ),
        {"Bunia": {"properties": {}}},
    )

    assert attached == 0
    with open(
        long_dir / "public_health_response__national_epidemiological_laboratory.csv",
        newline="",
        encoding="utf-8-sig",
    ) as fp:
        reader = csv.DictReader(fp)
        assert reader.fieldnames == ["nom", "date", "national_laboratory"]
        assert list(reader) == []


def test_attach_vector_broadcasts_province_to_zones_in_province(tmp_path, monkeypatch):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(
        processed / "public_health_response__provincial_epidemiological_coordination__daily.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write(
            "nom,date,provincial_coordination\n"
            "Ituri,2026-06-05,older\n"
            "Ituri,2026-06-06,latest ituri\n"
            "North-Kivu,2026-06-06,latest nord-kivu\n"
        )

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    bunia = {"properties": {}}
    beni = {"properties": {}}
    attached = build_geojson._attach_vector(
        folder,
        "public_health_response__provincial_epidemiological_coordination__daily.csv",
        SimpleNamespace(
            dataset="public_health_response",
            metric="provincial_epidemiological_coordination",
        ),
        {"Bunia": bunia, "Beni": beni},
    )

    assert attached == 2
    bunia_val = bunia["properties"]["public_health_response"][
        "provincial_epidemiological_coordination"
    ]
    beni_val = beni["properties"]["public_health_response"][
        "provincial_epidemiological_coordination"
    ]
    assert bunia_val["provincial_coordination"] == "latest ituri"
    assert bunia_val["_date"] == "2026-06-06"
    assert beni_val["provincial_coordination"] == "latest nord-kivu"
    assert beni_val["_date"] == "2026-06-06"
