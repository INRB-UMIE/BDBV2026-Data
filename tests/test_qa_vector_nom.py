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
