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
