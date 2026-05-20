"""Tests for the contract module: tools/lib/schema.py."""

from __future__ import annotations

import pytest

from tools.lib.schema import (
    VALID_RESOLUTIONS,
    canonical_noms,
    load_zones,
    parse_filename,
    to_canonical,
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
