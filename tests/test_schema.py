"""Tests for the contract module: tools/lib/schema.py."""

from __future__ import annotations

import pytest

from tools.lib.schema import (
    NATIONAL_ROLLUP_NOM,
    NON_GEOGRAPHIC_NOMS,
    VALID_RESOLUTIONS,
    build_processed_filename,
    canonical_noms,
    canonical_provinces,
    is_non_geographic_nom,
    is_province_rollup_nom,
    language_variant_filenames,
    load_zones,
    parse_filename,
    resolve_processed_paths,
    resolve_vector_nom,
    split_language_suffix,
    to_canonical,
    to_canonical_province,
    zones_by_province,
    zscode_to_canonical,
)


def test_canonical_noms_count_matches_zones():
    # 519 features should yield 519 unique canonical names after disambiguation.
    assert len(load_zones()) == 519
    assert len(canonical_noms()) == 519


@pytest.mark.parametrize(
    "name",
    [
        "Bili (Nord-Ubangi)",
        "Bili (Bas-Uele)",
        "Lubunga (Kasaï-Central)",
        "Lubunga (Tshopo)",
    ],
)
def test_disambiguated_collisions_present(name: str):
    assert name in canonical_noms()


def test_bare_collision_names_not_canonical():
    # Plain "Bili" / "Lubunga" must NOT leak in — that's the whole point of
    # disambiguation. Any data containing the bare form must declare context
    # (either via aliases.csv or in its own process script).
    assert "Bili" not in canonical_noms()
    assert "Lubunga" not in canonical_noms()


def test_to_canonical_passthrough():
    assert to_canonical("Bunia") == "Bunia"
    assert to_canonical("Goma") == "Goma"


def test_to_canonical_resolves_alias():
    # Seeded from flowminder/README.md spelling variants.
    assert to_canonical("Mongbwalu") == "Mongbalu"
    assert to_canonical("Nyankunde") == "Nyakunde"
    # Hyphen-vs-space variants added during flowminder retrofit.
    assert to_canonical("Nia Nia") == "Nia-Nia"
    assert to_canonical("Boma Mangbetu") == "Boma-Mangbetu"


def test_to_canonical_unknown_returns_none():
    assert to_canonical("NotAZone") is None
    assert to_canonical("") is None
    assert to_canonical(None) is None


def test_non_geographic_noms():
    assert NON_GEOGRAPHIC_NOMS == frozenset({"Sans Fiche", "NA"})
    assert is_non_geographic_nom("Sans Fiche")
    assert is_non_geographic_nom("NA")
    assert not is_non_geographic_nom("Bunia")
    assert resolve_vector_nom("Sans Fiche") == "Sans Fiche"
    assert resolve_vector_nom("NA") == "NA"
    assert resolve_vector_nom(NATIONAL_ROLLUP_NOM) == NATIONAL_ROLLUP_NOM
    assert resolve_vector_nom("Bunia") == "Bunia"
    assert resolve_vector_nom("NotAZone") is None


def test_canonical_provinces_from_shapefile():
    provinces = canonical_provinces()
    assert len(provinces) == 26
    assert "Ituri" in provinces
    assert "Nord-Kivu" in provinces
    assert "Sud-Kivu" in provinces


def test_to_canonical_province_and_aliases():
    assert to_canonical_province("Ituri") == "Ituri"
    assert to_canonical_province("North-Kivu") == "Nord-Kivu"
    assert to_canonical_province("North Kivu") == "Nord-Kivu"
    assert to_canonical_province("South-Kivu") == "Sud-Kivu"
    assert to_canonical_province("Fake Province") is None


def test_resolve_vector_nom_province_before_zone():
    assert resolve_vector_nom("North-Kivu") == "Nord-Kivu"
    assert is_province_rollup_nom("Nord-Kivu")
    assert not is_province_rollup_nom("North-Kivu")


def test_zones_by_province_includes_bunia_in_ituri():
    ituri = zones_by_province()["Ituri"]
    assert "Bunia" in ituri
    assert "Beni" in zones_by_province()["Nord-Kivu"]


def test_zscode_to_canonical_known_and_unknown():
    # Bunia's authoritative ZSCode in the current shapefile.
    assert zscode_to_canonical("CD5402ZS02") == "Bunia"
    # The legacy phantom MoH code used in IDP raw data is intentionally absent.
    assert zscode_to_canonical("CD5401ZS01") is None
    assert zscode_to_canonical("") is None


@pytest.mark.parametrize(
    "fname,dataset,metric,resolution,kind",
    [
        ("acled__events__weekly.csv", "acled", "events", "weekly", "vector"),
        ("flowminder__inflow__static.matrix.csv", "flowminder", "inflow", "static", "matrix"),
        ("idp__individuals__monthly.matrix.csv", "idp", "individuals", "monthly", "matrix"),
        ("epi__cases__daily.csv", "epi", "cases", "daily", "vector"),
    ],
)
def test_parse_filename_accepts_good(
    fname: str, dataset: str, metric: str, resolution: str, kind: str
):
    parsed = parse_filename(fname)
    assert parsed is not None
    assert parsed.dataset == dataset
    assert parsed.metric == metric
    assert parsed.resolution == resolution
    assert parsed.kind == kind


@pytest.mark.parametrize(
    "fname",
    [
        "ACLED__events__weekly.csv",        # uppercase dataset
        "acled-events-weekly.csv",          # wrong separator
        "acled__events.csv",                # missing resolution
        "acled__events__hourly.csv",        # invalid resolution
        "acled__events__weekly.tsv",        # wrong extension
        "acled__events__weekly.matrix.tsv",
        "_acled__events__weekly.csv",       # leading underscore
    ],
)
def test_parse_filename_rejects_bad(fname: str):
    assert parse_filename(fname) is None


def test_valid_resolutions_match_filename_pattern():
    # Sanity: every resolution we declare should parse.
    for res in VALID_RESOLUTIONS:
        assert parse_filename(f"d__m__{res}.csv") is not None


def test_split_language_suffix():
    assert split_language_suffix("epidemiological_coordination_en") == (
        "epidemiological_coordination",
        "en",
    )
    assert split_language_suffix("epidemiological_coordination") == (
        "epidemiological_coordination",
        None,
    )


def test_language_variant_filenames():
    logical = "public_health_response__epidemiological_community_engagement__daily.csv"
    variants = language_variant_filenames(logical)
    assert variants == [
        build_processed_filename(
            "public_health_response",
            "epidemiological_community_engagement",
            "daily",
            language="en",
        ),
        build_processed_filename(
            "public_health_response",
            "epidemiological_community_engagement",
            "daily",
            language="fr",
        ),
    ]
    suffixed = (
        "public_health_response__epidemiological_community_engagement_en__daily.csv"
    )
    assert language_variant_filenames(suffixed) == []


def test_resolve_processed_paths_language_variants(tmp_path):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    processed.mkdir(parents=True)
    en = build_processed_filename(
        "public_health_response",
        "epidemiological_community_engagement",
        "daily",
        language="en",
    )
    fr = build_processed_filename(
        "public_health_response",
        "epidemiological_community_engagement",
        "daily",
        language="fr",
    )
    (processed / en).write_text("nom,date,community_engagement_en\n", encoding="utf-8")
    (processed / fr).write_text("nom,date,community_engagement_fr\n", encoding="utf-8")

    logical = "public_health_response__epidemiological_community_engagement__daily.csv"
    resolved = resolve_processed_paths(folder, logical)
    assert [name for _, name in resolved] == [en, fr]

    exact = resolve_processed_paths(folder, en)
    assert [name for _, name in exact] == [en]
