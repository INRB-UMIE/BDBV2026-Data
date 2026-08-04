"""Vector QA: non-geographic nom labels (INSP sitrep)."""

from pathlib import Path

from tools.qa import qa_vector
from tools.lib.schema import parse_filename


def test_qa_vector_accepts_sans_fiche_and_na(tmp_path):
    folder = tmp_path / "insp_sitrep"
    processed = folder / "processed"
    processed.mkdir(parents=True)
    path = processed / "insp_sitrep__cases__daily.csv"
    path.write_text(
        "nom,date,cases\n"
        "Bunia,2026-05-20,1\n"
        "Sans Fiche,2026-05-20,2\n"
        "NA,2026-05-20,3\n",
        encoding="utf-8",
    )
    parsed = parse_filename(path.name)
    assert parsed is not None
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"
    assert result.n_zones_covered == 1


def test_qa_vector_accepts_province_rollups(tmp_path):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    processed.mkdir(parents=True)
    path = processed / (
        "public_health_response__provincial_epidemiological_coordination__daily.csv"
    )
    path.write_text(
        "nom,date,provincial_coordination\n"
        "Ituri,2026-06-06,Provincial note\n"
        "North-Kivu,2026-06-06,Other note\n"
        "Bunia,2026-06-06,Zone note\n",
        encoding="utf-8",
    )
    parsed = parse_filename(path.name)
    assert parsed is not None
    result = qa_vector("public_health_response", path, parsed)
    assert result.status == "pass"
    assert result.n_zones_covered == 1


def test_qa_vector_rejects_unknown_province(tmp_path):
    folder = tmp_path / "public_health_response"
    processed = folder / "processed"
    processed.mkdir(parents=True)
    path = processed / (
        "public_health_response__provincial_epidemiological_coordination__daily.csv"
    )
    path.write_text(
        "nom,date,provincial_coordination\n"
        "Fake Province,2026-06-06,Note\n",
        encoding="utf-8",
    )
    parsed = parse_filename(path.name)
    assert parsed is not None
    result = qa_vector("public_health_response", path, parsed)
    assert result.status == "fail"


def _write(tmp_path, filename, body):
    processed = tmp_path / "insp_sitrep" / "processed"
    processed.mkdir(parents=True)
    path = processed / filename
    path.write_text(body, encoding="utf-8")
    parsed = parse_filename(path.name)
    assert parsed is not None
    return path, parsed


def test_qa_vector_rejects_province_rollup_in_zone_level_sitrep(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Nord-Kivu,2026-08-02,414\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "fail"
    assert any("roll-up" in r for r in result.reasons)


def test_qa_vector_rejects_explicit_province_form_in_zone_level_sitrep(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Tshopo (province),2026-08-02,7\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "fail"


def test_qa_vector_allows_bare_collision_zone_in_sitrep(tmp_path):
    # KNOWN LIMITATION: bare "Tshopo" resolves to the Tshopo *zone*, so it is
    # NOT flagged (see spec "Known limitation"). Locks in that documented gap.
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "Tshopo,2026-08-02,7\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"


def test_qa_vector_allows_na_placeholder_in_zone_level_sitrep(tmp_path):
    # The guard must not flag non-geographic placeholders (NA) — only
    # province/national roll-ups. Explicit lock for the no-false-positive case.
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__cumulative_confirmed_cases__daily.csv",
        "nom,date,cumulative_confirmed_cases\n"
        "Bunia,2026-08-02,914\n"
        "NA,2026-08-02,3\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"


def test_qa_vector_national_file_allows_drc(tmp_path):
    path, parsed = _write(
        tmp_path,
        "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-08-02,3800\n",
    )
    result = qa_vector("insp_sitrep", path, parsed)
    assert result.status == "pass"
