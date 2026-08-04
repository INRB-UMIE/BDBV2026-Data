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
        processed / "example__metric__static.csv",
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
        processed / "insp_sitrep__metric__daily.csv",
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
        processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
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
        processed / "public_health_response__national_epidemiological_laboratory__daily.csv",
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
        processed / "public_health_response__provincial_epidemiological_coordination__daily.csv",
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


def test_attach_vector_broadcasts_marked_province_rollup_for_colliding_province(
    tmp_path, monkeypatch
):
    """A genuine province-wide roll-up for Tshopo (which collides with the
    Tshopo health zone) must use the "Tshopo (province)" marker to broadcast,
    since a bare "Tshopo" now always means the specific zone."""
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
            "Tshopo (province),2026-06-06,tshopo province update\n"
        )

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    tshopo_zone_feat = {"properties": {}}  # the "Tshopo" health zone itself
    other_zone_feat = {"properties": {}}   # another zone in Tshopo province
    attached = build_geojson._attach_vector(
        processed / "public_health_response__provincial_epidemiological_coordination__daily.csv",
        "public_health_response__provincial_epidemiological_coordination__daily.csv",
        SimpleNamespace(
            dataset="public_health_response",
            metric="provincial_epidemiological_coordination",
        ),
        {"Tshopo": tshopo_zone_feat, "Bafwagbogbo": other_zone_feat},
    )

    assert attached == 2
    for feat in (tshopo_zone_feat, other_zone_feat):
        val = feat["properties"]["public_health_response"][
            "provincial_epidemiological_coordination"
        ]
        assert val["provincial_coordination"] == "tshopo province update"


def test_attach_vector_zone_province_collision_not_broadcast(tmp_path, monkeypatch):
    """Tshopo is both a health zone and its own province's name. A per-zone row
    for "Tshopo" must attach only to the Tshopo zone feature, not broadcast to
    every zone in Tshopo province (regression test for that exact bug)."""
    folder = tmp_path / "ccvi"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(
        processed / "ccvi__socioeconomic_deprivation__static.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write(
            "nom,socioeconomic_deprivation\n"
            "Tshopo,0.5\n"
            "Bafwagbogbo,0.9\n"
        )

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    tshopo_feat = {"properties": {}}
    other_zone_feat = {"properties": {}}
    attached = build_geojson._attach_vector(
        processed / "ccvi__socioeconomic_deprivation__static.csv",
        "ccvi__socioeconomic_deprivation__static.csv",
        SimpleNamespace(dataset="ccvi", metric="socioeconomic_deprivation"),
        {"Tshopo": tshopo_feat, "Bafwagbogbo": other_zone_feat},
    )

    assert attached == 2
    assert tshopo_feat["properties"]["ccvi"]["socioeconomic_deprivation"] == {
        "socioeconomic_deprivation": 0.5
    }
    assert other_zone_feat["properties"]["ccvi"]["socioeconomic_deprivation"] == {
        "socioeconomic_deprivation": 0.9
    }


def test_attach_vector_resolves_language_variants(tmp_path, monkeypatch):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)

    with open(
        processed / "public_health_response__epidemiological_community_engagement_en__daily.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write("nom,date,community_engagement_en\nBunia,2026-06-06,en value\n")
    with open(
        processed / "public_health_response__epidemiological_community_engagement_fr__daily.csv",
        "w",
        encoding="utf-8",
    ) as fp:
        fp.write("nom,date,community_engagement_fr\nBunia,2026-06-06,fr value\n")

    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    bunia = {"properties": {}}
    for suffix in ("en", "fr"):
        src = processed / (
            f"public_health_response__epidemiological_community_engagement_{suffix}__daily.csv"
        )
        build_geojson._attach_vector(
            src,
            src.name,
            SimpleNamespace(
                dataset="public_health_response",
                metric=f"epidemiological_community_engagement_{suffix}",
            ),
            {"Bunia": bunia},
        )

    phr = bunia["properties"]["public_health_response"]
    assert phr["epidemiological_community_engagement_en"]["community_engagement_en"] == "en value"
    assert phr["epidemiological_community_engagement_fr"]["community_engagement_fr"] == "fr value"


def test_attach_vector_drops_province_rollup_for_zone_level_sitrep(tmp_path, monkeypatch):
    """A province roll-up row in a zone-level insp_sitrep file must NOT be
    broadcast, and must NOT clobber a real per-zone value."""
    processed = tmp_path / "insp_sitrep" / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)
    fname = "insp_sitrep__cumulative_confirmed_cases__daily.csv"
    (processed / fname).write_text(
        "nom,date,cumulative_confirmed_cases\n"
        "Beni,2026-08-02,10\n"          # real per-zone value
        "Nord-Kivu,2026-08-02,414\n",   # province roll-up (must be dropped)
        encoding="utf-8",
    )
    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    beni = {"properties": {}}
    butembo = {"properties": {}}  # another Nord-Kivu zone, no row of its own
    build_geojson._attach_vector(
        processed / fname, fname,
        SimpleNamespace(dataset="insp_sitrep", metric="cumulative_confirmed_cases"),
        {"Beni": beni, "Butembo": butembo},
    )

    # Beni keeps its own value, not the province total.
    assert beni["properties"]["insp_sitrep"]["cumulative_confirmed_cases"]["cumulative_confirmed_cases"] == 10
    # Butembo never received the broadcast.
    assert "insp_sitrep" not in butembo["properties"]


def test_attach_vector_national_sitrep_still_broadcasts(tmp_path, monkeypatch):
    """national_* insp_sitrep files are exempt: DRC still broadcasts to all zones."""
    processed = tmp_path / "insp_sitrep" / "processed"
    long_dir = tmp_path / "long"
    processed.mkdir(parents=True)
    fname = "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    (processed / fname).write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        f"{NATIONAL_ROLLUP_NOM},2026-08-02,3800\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_geojson, "LONG_DIR", long_dir)

    beni = {"properties": {}}
    butembo = {"properties": {}}
    build_geojson._attach_vector(
        processed / fname, fname,
        SimpleNamespace(dataset="insp_sitrep", metric="national_cumulative_confirmed_cases"),
        {"Beni": beni, "Butembo": butembo},
    )

    for feat in (beni, butembo):
        val = feat["properties"]["insp_sitrep"]["national_cumulative_confirmed_cases"]
        assert val["national_cumulative_confirmed_cases"] == 3800
