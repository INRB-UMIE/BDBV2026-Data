"""Tests for INSP SitRep source discovery and extraction helpers."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
from pathlib import Path

from tools import insp_sitrep_sources as sources


VERIFIED_SHA = "a" * 64


SITREP13_TEXT = """
                    Rapport de Situation de la 17ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                            SitRep N°013/MVB_27/2026

Date de rapportage               27 mai 2026
Date de publication              28 mai 2026

    125                   17                   906*                   223                  70,1%                 8,7%                       1        ND

Cumul cas             Cumul décès           Cumul cas         Cumul Décès Taux d’occupation                Taux d’occupation                      Cumul cas
confirmés              parmi les             suspects          suspects   chez les suspects                chez les confirmés          Guéris
                                    * Le nombre de cas suspects a été revu à la baisse suite au retrait des non-cas et des cas confirmés.

 Tableau II. Répartition des cas, décès suspects et confirmés de maladie à virus Ebola dans les zones
                      de santé de la DPS Ituri, Nord-Kivu et Sud Kivu au 27 mai 2026
                                                                                 Nbre de
                                                               Nbre de cas                       Nbre de cas          Nbre de
                   Provinces           Zones de santé                             décès
                                                                suspects*                        Confirmés*          contacts*
                                                                                suspects*
                                   Aru                                4             1                  1                 0
                                   Bambu                              6             2                  0                244
                                   Bunia                            249            48                 37                404
                                   Kilo                               8             2                  1                 41
                       Ituri       Mongbwalu                        339            88                 20                222
                                   Nizi                               6             2                  2                220
                                   Nyankunde                         45            11                 10                397
                                   Rwampara                         228            69                 33                697
                                   Echantillons sans
                                                                     0              0                  6                  0
                                   fiche
                                Sous total                          885            223               110                2225
                 Nord-Kivu         Butembo                            7             0                 5                   28
                                   Goma                               0             0                 1                   74
                                   Kalunguta                         13             0                 2                  ND
                                   Karisimbi                                                                             181
                                   Katwa                             0              0                  4                 111
                                   Kyondo                            0              0                  0                  16
                                   Oicha                             0              0                  2                 ND
                                Sous total                          20              0                 14                 410
                 Sud-Kivu          Miti Murhesa                      1              0                  1                 ND
                                Sous total                           1              0                  1                  0
                                   Total                            906            223               125               2635**
 *Ces données sont susceptibles de changer après harmonisation des données à différents niveaux de la pyramide sanitaire avec le système de

Surveillance aux Points d’entrées et Points de contrôle (PoE/PoC) :
"""


SITREP14_TEXT = """
                                                       Rapport de Situation de la 17 ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                                              SitRep N°014/MVB_28/2026

Provinces touchées (3)                        ITURI, NORD-KIVU & SUD-KIVU
                                              ITURI : Aru, Damas, Bunia, Kilo, Mongbwalu, Nizi, Nyankunde et Rwampara
Zones de Santé touchées
                                              NORD-KIVU : Butembo, Goma, Oicha, Kalunguta et Katwa
(13)
                                              SUD-KIVU : Miti-Murhesa
Date de rapportage                            28 mai 2026
Date de publication                           29 mai 2026




                                                                                            ND                              ND                                    1
    210                          17                         349*                                                                                                                                    ND
Cumul cas                 Cumul décès                    Cumul Cas                 Taux d’occupation                 Taux d’occupation
                           parmi les                      Suspects                                                                                             Guéris
confirmés                                                                          chez les suspects                 chez les confirmés                                                          Cumul cas
                           confirmés                                                                                                                                                           confirmés CTE
         Le nombre de cas suspects a été revu à la baisse, ces derniers ayant fait l'objet d'investigations et de prélèvements dont les résultats ont confirmé certains cas et infirmé d'autres.
         Les décès suspects ont été temporairement exclus du comptage dans l'attente des résultats des investigations en cours, qui permettront de les confirmer et de les classer comme cas
          probables, ou de les écarter définitivement.


                       0. FAITS SAILLANTS
"""


SITREP15_TEXT = """
                                                       Rapport de Situation de la 17 ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                                              SitRep N°015/MVE_29/2026

Date de rapportage                            29 mai 2026
Date de publication                           30 mai 2026

    263                 42              3491                                                                                   ND
Cumul cas           Cumul décès       Cumul Cas       Taux d’occupation   Taux d’occupation         Guéris               Cumul cas
confirmés            parmi les         Suspects       chez les suspects   chez les confirmés                           confirmés CTE
                     confirmés

                       0. FAITS SAILLANTS
""" * 3


SITREP16_TEXT = """
                                                       Rapport de Situation de la 17 ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                                              SitRep N°016/MVB_30/2026

Date de rapportage                            30 mai 2026
Date de publication                           31 mai 2026

    282                          42                         238                    220                                101                 2
Cumul cas                 Cumul décès                    Cas confirmés          Cas suspects                       Cas suspects        Guéris
confirmés                 parmi les                      actifs                 en cours d'investigation           en isolement
                          confirmés

                       0. FAITS SAILLANTS
""" * 3


SITREP17_TEXT = """
                                                       Rapport de Situation de la 17 ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                                              SitRep N°017/MVB_31/2026

Date de rapportage                            31 mai 2026
Date de publication                           1 juin 2026

    321                          48                         238                    116                                104                 6
Cumul cas                 Cumul décès                    Cas confirmés          Cas suspects                       Cas suspects        Guéris
confirmés                 parmi les                      actifs                 en cours d'investigation           en isolement
                          confirmés

                       0. FAITS SAILLANTS
""" * 3


SITREP18_TEXT = """
                                                       Rapport de Situation de la 17 ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                                              SitRep N°018/MVB_01/06/2026

Date de rapportage                            01 Juin 2026
Date de publication                           02 Juin 2026

      344*                       60                    116*               173                6                  43,9%

  Cumul cas                Cumul décès              Cas suspects      Patients en          Guéris          Taux de suivi de
  confirmés                 parmi les                 en cours        isolement -
                            confirmés              d'investigation   hospitalisation
               *Données en cours d'harmonisation

                       1. FAITS SAILLANTS
""" * 3


SITREP19_TEXT = """
                                       Centre d’Opérations d’Urgence de Santé Publique
                                                       « COUSP RDC »
                                          Système de Gestion de l’Incident MVE-17

          ² Rapport de Situation de la 17                       ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                          SitRep N°019/MVB_02/06/2026

Provinces touchées (3)              ITURI, NORD-KIVU & SUD-KIVU
                                    ITURI : Aru, Aungba, Bambu, Damas, Bunia, Gety, Kilo, Komanda, Lita, Mambasa, Mangala,
Zones de Santé touchées             Mongbwalu, Nizi, Nyankunde, Rimba, Rwampara et Logo
(25)                                NORD-KIVU : Butembo, Goma, Oicha, Kalunguta, Katwa, Kyondo et Beni
                                    SUD-KIVU : Miti-Murhesa
Date de rapportage                  02 Juin 2026
Date de publication                 03 Juin 2026




       363*                          62 (17%)                                206                                    6                            45,5%

Cumul cas confirmés            Cumul décès parmi                         Patients en                        Nombre cumulé                  Taux de suivi des
pour les 3 provinces            les confirmés et                         isolement -                          des guéris                   contacts pour les
                                 taux de létalité                       hospitalisation                                                      3 provinces
                *Données en cours d’harmonisation **Localisation de ces cas confirmés actifs est en cours en vue d’harmoniser les statistiques

          1. FAITS SAILLANTS

          •    Dix-neuf (19) nouveaux cas confirmés, incluant deux décès, ont été notifiés le 02 juin 2026.

3.2 Répartition par zone de santé (Cumul au 02/06/2026)

Tableau 1. Répartition des cas confirmés et des décès de la MVE Bundibugyo par zone de santé et
par province, République Démocratique du Congo, au 02 juin 2026

 Province /                    Cas confirmés            Décès confirmés                Létalité
  Zone de santé                 cumulés (n)               cumulés (n)                 (CFR, %)
 ITURI
     1. Bunia                        85                        8                         9,4
     2. Rwampara                     72                        15                       20,8
     3. Mongbwalu                    47                        10                       21,3
     4. Nyankunde                    22                        1                         4,5
     5. Bambu                        2                         2                        100,0
     6. Aru                          2                         1                        50,0
     7. Kilo                         2                         0                         0,0
     8. Nizi                         2                         0                         0,0
     9. Mangala                      1                         0                         0,0
     10. Damas                       2                         0                         0,0
     11. Aungba                      1                         0                         0,0
     12. Gety                        1                         0                         0,0
     13. Komanda                     1                         0                         0,0
     14. Lita                        1                         0                         0,0
     15. Logo                        1                         0                         0,0
     16. Mambasa                     2                         1                        50,0
     17. Rimba                       3                         0                         0,0
 - Autres ZS (données                94                        10                       10,6
 non ventilées)
 Sous-total Ituri                   341                        48                       14,1
 NORD-KIVU
     1. Katwa                        7                         5                        71,4
     2. Beni                         5                         3                        60,0
     3. Butembo                      2                         2                        100,0
     4. Oicha                        2                         2                        100,0
     5. Kalunguta                    1                         1                        100,0
     6. Kyondo                       1                         0                         0,0
     7. Goma                         1                         0                         0,0
 Sous-total Nord-Kivu                19                        13                       68,4
 SUD-KIVU
     1. Miti-Murhesa                 3                         1                        33,3
 Sous-total Sud-Kivu                 3                         1                        33,3
TOTAL                              363                        62                       17,1

4. ACTIONS DE RIPOSTE PAR PILIER
9         Nord-Kivu : sortie du cas guéri à Goma (J+1), réponse aux                             J+2
"""


SITREP12_TEXT = """
            Rapport de Situation de la 17ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                   SitRep N°012/MVB_26/2026
Date de rapportage               26 mai 2026
Date de publication              26 mai 2026


    121                17*               1077               246               ND                ND              0             ND
Cumul cas          Cumul décès         Cumul cas Cumul Décès Taux d’occupation            Taux d’occupation
                                                                                                               Guéris   Nbre des cas
confirmés            parmi les          suspects       suspects     chez les suspects     chez les confirmés            actifs
                     confirmés
            *Ces décès sont sous-estimés car la confirmation de diagnostics est tardive
"""


UNKNOWN_FUTURE_TEXT = """
            Rapport de Situation de la 17ème Epidémie de la Maladie à Virus EBOLA /RDC
                                                   SitRep N°015/MVB_29/2026
Date de rapportage               29 mai 2026
Date de publication              30 mai 2026

Cette édition présente les indicateurs dans un format narratif et graphique.
Les valeurs cumulatives nationales et les tableaux par zone de santé ne sont pas exposés
dans les libellés publics utilisés par les versions précédentes.
""" * 3


def test_extract_pdf_url_from_post_content():
    post = {
        "link": "https://insp.cd/sitrep-mve-n-013-2026/",
        "content": {
            "rendered": (
                '<a href="https://insp.cd/wp-content/uploads/2026/05/'
                'SitRep_MVE_RDC_NA°013_27_05_2026_ES-IM4.pdf">PDF</a>'
            )
        },
    }

    assert sources._extract_pdf_url(post).endswith("SitRep_MVE_RDC_NA°013_27_05_2026_ES-IM4.pdf")


def test_extract_pdf_url_from_pdfemb_payload():
    pdf_url = "https://insp.cd/wp-content/uploads/2026/06/SitRep_MVE_RDC_N017_01_06_2026.pdf"
    payload = base64.urlsafe_b64encode(json.dumps({"url": pdf_url}).encode()).decode().rstrip("=")
    post = {
        "link": "https://insp.cd/sitrep-n017-mvb_31-2026/",
        "content": {"rendered": f'<iframe src="https://insp.cd/?pdfemb-data={payload}"></iframe>'},
    }

    assert sources._extract_pdf_url(post) == pdf_url


def test_extract_pdf_url_rejects_external_pdfemb_payload():
    payload = base64.urlsafe_b64encode(
        json.dumps({"url": "https://example.com/wp-content/uploads/2026/06/not-official.pdf"}).encode()
    ).decode().rstrip("=")
    post = {
        "link": "https://insp.cd/sitrep-n017-mvb_31-2026/",
        "content": {"rendered": f'<iframe src="https://insp.cd/?pdfemb-data={payload}"></iframe>'},
    }

    assert sources._extract_pdf_url(post) == ""


def test_extract_pdf_url_ignores_non_object_pdfemb_payload():
    payload = base64.urlsafe_b64encode(json.dumps(["not", "an", "object"]).encode()).decode().rstrip("=")
    post = {
        "link": "https://insp.cd/sitrep-n017-mvb_31-2026/",
        "content": {"rendered": f'<iframe src="https://insp.cd/?pdfemb-data={payload}"></iframe>'},
    }

    assert sources._extract_pdf_url(post) == ""


def test_report_title_regex_accepts_insp_title_variants():
    titles = [
        "SitRep MVE N° 014/2026",
        "SitRep N°015/MVE_29/2026",
        "SitRep N°016/MVB_30/2026",
        "SitRep N°017/MVB_31/2026",
        "SitRep N°018/MVB_01/06/2026",
        "SitRep N°018/MVB_01_06_2026",
    ]

    assert [sources._report_number_from_title(title) for title in titles] == [14, 15, 16, 17, 18, 18]
    assert sources._report_number_from_title("SitRep N°017/31/2026") is None


def test_parse_report_text_extracts_dates_totals_and_revision_note():
    parsed = sources.parse_report_text(SITREP13_TEXT)

    assert parsed["report_number"] == "013"
    assert parsed["report_date"] == "2026-05-27"
    assert parsed["publication_date"] == "2026-05-28"
    assert parsed["national_confirmed_cases"] == "125"
    assert parsed["national_confirmed_deaths"] == "17"
    assert parsed["national_suspected_cases"] == "906"
    assert parsed["national_suspected_deaths"] == "223"
    assert "revu à la baisse" in parsed["revision_notes"]


def test_parse_report_text_extracts_sitrep14_split_banner_and_withheld_deaths():
    parsed = sources.parse_report_text(SITREP14_TEXT)

    assert parsed["report_number"] == "014"
    assert parsed["report_date"] == "2026-05-28"
    assert parsed["publication_date"] == "2026-05-29"
    assert parsed["national_confirmed_cases"] == "210"
    assert parsed["national_confirmed_deaths"] == "17"
    assert parsed["national_suspected_cases"] == "349"
    assert parsed["national_suspected_deaths"] == "ND"
    assert parsed["headline_status"] == "headline_extracted"
    assert "décès suspects" in parsed["revision_notes"]


def test_parse_report_text_treats_sitrep15_suspected_footnote_as_marker():
    parsed = sources.parse_report_text(SITREP15_TEXT)

    assert parsed["report_number"] == "015"
    assert parsed["report_date"] == "2026-05-29"
    assert parsed["publication_date"] == "2026-05-30"
    assert parsed["national_confirmed_cases"] == "263"
    assert parsed["national_confirmed_deaths"] == "42"
    assert parsed["national_suspected_cases"] == "349"
    assert parsed["national_recovered"] == "ND"
    assert parsed["headline_status"] == "headline_extracted"


def test_parse_report_text_does_not_strip_future_suspected_value_without_sitrep15_context():
    text = SITREP15_TEXT.replace("SitRep N°015/MVE_29/2026", "SitRep N°018/MVB_29/2026")

    parsed = sources.parse_report_text(text)

    assert parsed["report_number"] == "018"
    assert parsed["national_suspected_cases"] == "3491"


def test_parse_report_text_extracts_sitrep16_suspected_state_split():
    parsed = sources.parse_report_text(SITREP16_TEXT)

    assert parsed["report_number"] == "016"
    assert parsed["report_date"] == "2026-05-30"
    assert parsed["publication_date"] == "2026-05-31"
    assert parsed["national_confirmed_cases"] == "282"
    assert parsed["national_confirmed_deaths"] == "42"
    assert parsed["national_confirmed_active"] == "238"
    assert parsed["national_suspected_cases_under_investigation"] == "220"
    assert parsed["national_suspected_cases_in_isolation"] == "101"
    assert parsed["national_recovered"] == "2"
    assert "national_suspected_cases" not in parsed
    assert parsed["headline_status"] == "headline_extracted"


def test_parse_report_text_extracts_sitrep18_patient_isolation_as_suspected_isolation():
    parsed = sources.parse_report_text(SITREP18_TEXT)

    assert parsed["report_number"] == "018"
    assert parsed["report_date"] == "2026-06-01"
    assert parsed["publication_date"] == "2026-06-02"
    assert parsed["national_confirmed_cases"] == "344"
    assert parsed["national_confirmed_deaths"] == "60"
    assert parsed["national_suspected_cases_under_investigation"] == "116"
    assert parsed["national_suspected_cases_in_isolation"] == "173"
    assert parsed["national_recovered"] == "6"
    assert parsed["headline_status"] == "headline_extracted"


def test_parse_report_text_extracts_sitrep19_revised_confirmed_banner():
    parsed = sources.parse_report_text(SITREP19_TEXT)

    assert parsed["report_number"] == "019"
    assert parsed["report_date"] == "2026-06-02"
    assert parsed["publication_date"] == "2026-06-03"
    assert parsed["national_confirmed_cases"] == "363"
    assert parsed["national_confirmed_deaths"] == "62"
    assert parsed["national_patients_in_isolation"] == "206"
    assert parsed["national_recovered"] == "6"
    assert parsed["national_contact_followup_rate"] == "45,5%"
    assert "national_suspected_cases" not in parsed
    assert "national_suspected_cases_in_isolation" not in parsed
    assert parsed["headline_status"] == "headline_extracted"


def test_parse_pdf_text_classifies_sitrep19_as_partial_supported_layout():
    parsed = sources.parse_pdf_text(SITREP19_TEXT)

    assert parsed["text_extractable"] == "true"
    assert parsed["layout_status"] == "partial_extract"
    assert parsed["extraction_confidence"] == "partial"
    assert parsed["headline_status"] == "headline_extracted"
    assert parsed["table_ii_status"] == "case_distribution_table_extracted"
    assert parsed["national_values_status"] == "partial"
    assert parsed["draft_status"] == "ready_for_review"
    assert parsed["blocking_reason"] == "national_values_partial"


def test_parse_report_text_extracts_adjacent_sitrep12_death_columns():
    parsed = sources.parse_report_text(SITREP12_TEXT)

    assert parsed["report_number"] == "012"
    assert parsed["report_date"] == "2026-05-26"
    assert parsed["national_confirmed_cases"] == "121"
    assert parsed["national_confirmed_deaths"] == "17"
    assert parsed["national_suspected_cases"] == "1077"
    assert parsed["national_suspected_deaths"] == "246"


def test_parse_pdf_text_marks_page_break_only_text_as_not_extractable():
    parsed = sources.parse_pdf_text("\f\f\f\n")

    assert parsed["text_extractable"] == "false"
    assert parsed["text_chars"] == "0"
    assert parsed["layout_status"] == "image_only_pdf"
    assert parsed["extraction_confidence"] == "blocked"
    assert parsed["draft_status"] == "blocked"
    assert parsed["blocking_reason"] == "not_publicly_extractable"
    assert parsed["headline_status"] == "text_not_extractable"
    assert parsed["table_ii_status"] == "text_not_extractable"
    assert "national_confirmed_cases" not in parsed


def test_parse_pdf_path_records_pdftotext_failures_without_crashing(tmp_path: Path, monkeypatch):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a real pdf")

    def fail_pdf_text(pdf_path: Path) -> str:
        raise RuntimeError("pdftotext failed")

    monkeypatch.setattr(sources, "_pdf_text", fail_pdf_text)

    parsed = sources.parse_pdf_path(path)

    assert parsed["text_extractable"] == "false"
    assert parsed["layout_status"] == "image_only_pdf"
    assert parsed["draft_status"] == "blocked"
    assert parsed["headline_status"] == "pdf_text_failed:RuntimeError"
    assert "pdf_text_failed:RuntimeError" in parsed["blocking_reason"]


def test_table_ii_status_reports_missing_table_for_sitrep14_shape():
    parsed = sources.parse_report_text(SITREP14_TEXT)

    assert sources.table_ii_status(SITREP14_TEXT, parsed) == "table_ii_missing"


def test_extract_table_ii_assigns_values_by_layout_columns():
    source = sources.ReportSource(
        report_number=13,
        title="SitRep MVE N° 013/2026",
        post_url="https://insp.cd/sitrep-mve-n-013-2026/",
        post_id=24889,
        pdf_url="https://insp.cd/wp-content/uploads/2026/05/example.pdf",
        parsed={"report_date": "2026-05-27"},
    )

    rows = sources.extract_table_ii(SITREP13_TEXT, source)
    by_key = {(r.nom_raw, r.metric): r.value for r in rows}

    assert by_key[("Bunia", "cumulative_suspected_cases")] == "249"
    assert by_key[("Bunia", "cumulative_suspected_deaths")] == "48"
    assert by_key[("Bunia", "cumulative_confirmed_cases")] == "37"
    assert by_key[("Bunia", "cumulative_contacts_traced")] == "404"
    assert by_key[("Karisimbi", "cumulative_contacts_traced")] == "181"
    assert by_key[("Miti Murhesa", "cumulative_confirmed_cases")] == "1"
    assert ("Karisimbi", "cumulative_suspected_cases") not in by_key
    assert not any(r.nom_raw == "Echantillons sans" for r in rows)
    assert not any(r.nom_raw == "Total" for r in rows)
    assert not any(r.nom_raw == "s total" for r in rows)


def test_extract_table_ii_extracts_sitrep19_confirmed_case_distribution():
    source = sources.ReportSource(
        report_number=19,
        title="SitRep N°019/MVB_02/06/2026",
        post_url="https://insp.cd/sitrep-n019-mvb_02-06-2026/",
        post_id=24930,
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        parsed=sources.parse_report_text(SITREP19_TEXT),
    )

    rows = sources.extract_table_ii(SITREP19_TEXT, source)
    by_key = {(r.nom_raw, r.metric): r.value for r in rows}

    assert by_key[("Bunia", "cumulative_confirmed_cases")] == "85"
    assert by_key[("Bunia", "cumulative_confirmed_deaths")] == "8"
    assert by_key[("Rwampara", "cumulative_confirmed_cases")] == "72"
    assert by_key[("Rwampara", "cumulative_confirmed_deaths")] == "15"
    assert by_key[("Mongbwalu", "cumulative_confirmed_cases")] == "47"
    assert by_key[("Nyankunde", "cumulative_confirmed_cases")] == "22"
    assert by_key[("Rimba", "cumulative_confirmed_cases")] == "3"
    assert by_key[("NA", "cumulative_confirmed_cases")] == "94"
    assert by_key[("NA", "cumulative_confirmed_deaths")] == "10"
    assert by_key[("Beni", "cumulative_confirmed_deaths")] == "3"
    assert by_key[("Miti-Murhesa", "cumulative_confirmed_deaths")] == "1"
    assert by_key[("Goma", "cumulative_confirmed_deaths")] == "0"
    assert {row.method for row in rows} == {"pdftotext_layout_case_distribution"}
    assert not any(row.nom_raw.startswith("Sous-total") for row in rows)
    assert not any(row.nom_raw == "TOTAL" for row in rows)
    assert len([row for row in rows if row.nom_raw == "Goma"]) == 2


def test_write_source_reports_includes_resilience_status_columns(tmp_path: Path):
    path = tmp_path / "source_reports.csv"
    source = sources.ReportSource(
        report_number=14,
        title="SitRep MVE N° 014/2026",
        post_url="https://insp.cd/sitrep-mve-n-014-2026/",
        post_id=24894,
        post_published_at="2026-05-30T14:03:52Z",
        post_modified_at="2026-05-30T14:03:57Z",
        pdf_url="https://insp.cd/wp-content/uploads/2026/05/example.pdf",
        source_relation="raw_matches_official",
        last_modified="Sat, 30 May 2026 14:03:03 GMT",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed=sources.parse_pdf_text(SITREP14_TEXT),
    )

    sources.write_source_reports(path, [source])

    with path.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    assert row["text_extractable"] == "true"
    assert int(row["text_chars"]) > sources.TEXT_EXTRACTABLE_MIN_CHARS
    assert row["post_published_at"] == "2026-05-30T14:03:52Z"
    assert row["post_modified_at"] == "2026-05-30T14:03:57Z"
    assert row["last_modified"] == "Sat, 30 May 2026 14:03:03 GMT"
    assert row["source_gate_status"] == "passed"
    assert row["layout_status"] == "partial_extract"
    assert row["extraction_confidence"] == "partial"
    assert row["headline_status"] == "headline_extracted"
    assert row["table_ii_status"] == "table_ii_missing"
    assert row["national_values_status"] == "found_withheld_by_sitrep"
    assert row["national_suspected_deaths"] == "ND"
    assert row["draft_status"] == "ready_for_review"
    assert row["blocking_reason"] == "table_ii_missing"
    assert row["status"] == "official_verified"


def test_write_source_reports_includes_revised_sitrep19_banner_columns(tmp_path: Path):
    path = tmp_path / "source_reports.csv"
    source = sources.ReportSource(
        report_number=19,
        title="SitRep N°019/MVB_02/06/2026",
        post_url="https://insp.cd/sitrep-n019-mvb_02-06-2026/",
        post_id=24930,
        post_published_at="2026-06-03T15:49:12Z",
        post_modified_at="2026-06-03T15:49:16Z",
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        source_relation="raw_matches_official",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed=sources.parse_pdf_text(SITREP19_TEXT),
    )

    sources.write_source_reports(path, [source])

    with path.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    assert row["source_gate_status"] == "passed"
    assert row["layout_status"] == "partial_extract"
    assert row["table_ii_status"] == "case_distribution_table_extracted"
    assert row["national_values_status"] == "partial"
    assert row["national_confirmed_cases"] == "363"
    assert row["national_confirmed_deaths"] == "62"
    assert row["national_patients_in_isolation"] == "206"
    assert row["national_recovered"] == "6"
    assert row["national_contact_followup_rate"] == "45,5%"
    assert row["national_suspected_cases"] == ""
    assert row["national_suspected_cases_in_isolation"] == ""
    assert row["draft_status"] == "ready_for_review"
    assert row["blocking_reason"] == "national_values_partial"


def test_filter_sources_by_report_number_keeps_requested_window():
    rows = [
        sources.ReportSource(report_number=12, title="", post_url="", post_id=12),
        sources.ReportSource(report_number=13, title="", post_url="", post_id=13),
        sources.ReportSource(report_number=14, title="", post_url="", post_id=14),
        sources.ReportSource(report_number=15, title="", post_url="", post_id=15),
    ]

    filtered = sources.filter_sources_by_report_number(
        rows,
        min_report_number=13,
        max_report_number=14,
    )

    assert [row.report_number for row in filtered] == [13, 14]


def test_sync_official_pdfs_replaces_stale_raw_bytes(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_007-2026.pdf"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"derived image-only copy")
    official_bytes = b"official source pdf bytes"

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        sources,
        "_head_url",
        lambda url, *, allow_insecure_tls=False: {"content-length": str(len(official_bytes))},
    )
    monkeypatch.setattr(
        sources,
        "_download_url",
        lambda url, path, *, allow_insecure_tls=False: path.write_bytes(official_bytes),
    )
    source = sources.ReportSource(
        report_number=7,
        title="SitRep MVE N° 007/2026",
        post_url="https://insp.cd/sitrep-mve-n-007-2026/",
        post_id=1,
        pdf_url="https://insp.cd/wp-content/uploads/2026/05/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_007-2026.pdf",
    )

    [enriched] = sources.enrich_pdf_metadata([source], sync_official_pdfs=True)

    expected_sha = hashlib.sha256(official_bytes).hexdigest()
    assert raw_path.read_bytes() == official_bytes
    assert enriched.pdf_sha256 == expected_sha
    assert enriched.official_pdf_sha256 == expected_sha
    assert enriched.pdf_bytes == len(official_bytes)
    assert enriched.official_pdf_bytes == len(official_bytes)
    assert enriched.source_relation == "raw_matches_official"
    assert enriched.status == "official_synced"


def test_sync_official_pdfs_skips_download_when_manifest_proves_unchanged(
    tmp_path: Path,
    monkeypatch,
):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_007-2026.pdf"
    raw_path.parent.mkdir(parents=True)
    official_bytes = b"official source pdf bytes"
    raw_path.write_bytes(official_bytes)
    official_sha = hashlib.sha256(official_bytes).hexdigest()
    pdf_url = "https://insp.cd/wp-content/uploads/2026/05/example.pdf"

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        sources,
        "_head_url",
        lambda url, *, allow_insecure_tls=False: {
            "content-length": str(len(official_bytes)),
            "etag": '"abc123"',
            "last-modified": "Sat, 30 May 2026 12:00:00 GMT",
        },
    )

    def fail_download(url: str, path: Path, *, allow_insecure_tls: bool = False) -> None:
        raise AssertionError("unchanged source should not be downloaded")

    monkeypatch.setattr(sources, "_download_url", fail_download)
    source = sources.ReportSource(
        report_number=7,
        title="SitRep MVE N° 007/2026",
        post_url="https://insp.cd/sitrep-mve-n-007-2026/",
        post_id=1,
        pdf_url=pdf_url,
        raw_path="data/insp_sitrep/raw/SitRep_MVE_007-2026.pdf",
    )
    cache = {
        7: {
            "pdf_url": pdf_url,
            "pdf_sha256": official_sha,
            "official_pdf_sha256": official_sha,
            "official_pdf_bytes": str(len(official_bytes)),
            "source_gate_status": "passed",
            "etag": '"abc123"',
            "last_modified": "Sat, 30 May 2026 12:00:00 GMT",
        }
    }

    [enriched] = sources.enrich_pdf_metadata(
        [source],
        sync_official_pdfs=True,
        source_report_cache=cache,
    )

    assert enriched.status == "official_unchanged"
    assert enriched.source_relation == "raw_matches_official"
    assert enriched.parsed["source_gate_status"] == "passed"


def test_source_update_reasons_empty_when_manifest_matches_head_metadata():
    source = sources.ReportSource(
        report_number=17,
        title="SitRep N017/MVB_31/2026",
        post_url="https://insp.cd/sitrep-n017-mvb_31-2026/",
        post_id=24915,
        post_published_at="2026-06-01T17:32:30Z",
        post_modified_at="2026-06-01T17:32:35Z",
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_017-2026.pdf",
        last_modified="Mon, 01 Jun 2026 17:31:28 GMT",
        etag='"abc123"',
        official_pdf_bytes=1234,
    )
    cache = {
        "title": source.title,
        "post_published_at": source.post_published_at,
        "post_modified_at": source.post_modified_at,
        "post_url": source.post_url,
        "pdf_url": source.pdf_url,
        "last_modified": source.last_modified,
        "etag": source.etag,
        "official_pdf_bytes": "1234",
    }

    assert sources.source_update_reasons(source, cache) == []


def test_source_update_reasons_flags_new_report():
    source = sources.ReportSource(
        report_number=18,
        title="SitRep N018/MVB_01/2026",
        post_url="https://insp.cd/sitrep-n018-mvb_01-2026/",
        post_id=24916,
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_018-2026.pdf",
    )

    assert sources.source_update_reasons(source, {}) == ["new_report"]


def test_source_update_reasons_flags_changed_pdf_head_metadata():
    source = sources.ReportSource(
        report_number=17,
        title="SitRep N017/MVB_31/2026",
        post_url="https://insp.cd/sitrep-n017-mvb_31-2026/",
        post_id=24915,
        post_published_at="2026-06-01T17:32:30Z",
        post_modified_at="2026-06-01T17:32:35Z",
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_017-2026.pdf",
        last_modified="Mon, 01 Jun 2026 17:31:28 GMT",
        etag='"changed"',
        official_pdf_bytes=1235,
    )
    cache = {
        "title": source.title,
        "post_published_at": source.post_published_at,
        "post_modified_at": source.post_modified_at,
        "post_url": source.post_url,
        "pdf_url": source.pdf_url,
        "last_modified": source.last_modified,
        "etag": '"old"',
        "official_pdf_bytes": "1234",
    }

    assert sources.source_update_reasons(source, cache) == [
        "etag_changed",
        "official_pdf_bytes_changed",
    ]


def test_source_update_reasons_ignores_head_failure_without_source_change():
    source = sources.ReportSource(
        report_number=17,
        title="SitRep N017/MVB_31/2026",
        post_url="https://insp.cd/sitrep-n017-mvb_31-2026/",
        post_id=24915,
        post_published_at="2026-06-01T17:32:30Z",
        post_modified_at="2026-06-01T17:32:35Z",
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_017-2026.pdf",
        status="pdf_head_failed:TimeoutError",
    )
    cache = {
        "title": source.title,
        "post_published_at": source.post_published_at,
        "post_modified_at": source.post_modified_at,
        "post_url": source.post_url,
        "pdf_url": source.pdf_url,
    }

    assert sources.source_update_reasons(source, cache) == []


def test_check_for_updates_main_returns_update_needed_exit_code_for_new_report(
    tmp_path: Path,
    monkeypatch,
):
    source = sources.ReportSource(
        report_number=18,
        title="SitRep N018/MVB_01/2026",
        post_url="https://insp.cd/sitrep-n018-mvb_01-2026/",
        post_id=24916,
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_018-2026.pdf",
    )

    monkeypatch.setattr(sources, "discover_sources", lambda **kwargs: [source])
    monkeypatch.setattr(sources, "enrich_pdf_metadata", lambda source_list, **kwargs: list(source_list))

    assert sources.main([
        "--check-for-updates",
        "--write-source-reports",
        str(tmp_path / "source_reports.csv"),
    ]) == sources.UPDATE_NEEDED_EXIT_CODE


def test_verify_official_pdfs_still_downloads_missing_raw(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_017-2026.pdf"
    official_bytes = b"official source pdf bytes"
    download_paths: list[Path] = []

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        sources,
        "_head_url",
        lambda url, *, allow_insecure_tls=False: {"content-length": str(len(official_bytes))},
    )

    def download(url: str, path: Path, *, allow_insecure_tls: bool = False) -> None:
        download_paths.append(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(official_bytes)

    monkeypatch.setattr(sources, "_download_url", download)
    source = sources.ReportSource(
        report_number=17,
        title="SitRep N°017/MVB_31/2026",
        post_url="https://insp.cd/sitrep-n017-mvb_31-2026/",
        post_id=24915,
        pdf_url="https://insp.cd/wp-content/uploads/2026/06/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_017-2026.pdf",
    )

    [enriched] = sources.enrich_pdf_metadata(
        [source],
        download_missing=True,
        verify_official_pdfs=True,
    )

    expected_sha = hashlib.sha256(official_bytes).hexdigest()
    assert raw_path.read_bytes() == official_bytes
    assert len(download_paths) == 2
    assert enriched.pdf_sha256 == expected_sha
    assert enriched.official_pdf_sha256 == expected_sha
    assert enriched.source_relation == "raw_matches_official"
    assert enriched.parsed["source_gate_status"] == "passed"


def test_sync_official_pdfs_blocks_instead_of_crashing_on_download_timeout(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_007-2026.pdf"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"previous local pdf")

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        sources,
        "_head_url",
        lambda url, *, allow_insecure_tls=False: {"content-length": "1234"},
    )

    def timeout(url: str, path: Path, *, allow_insecure_tls: bool = False) -> None:
        raise TimeoutError("read timed out")

    monkeypatch.setattr(sources, "_download_url", timeout)
    source = sources.ReportSource(
        report_number=7,
        title="SitRep MVE N° 007/2026",
        post_url="https://insp.cd/sitrep-mve-n-007-2026/",
        post_id=1,
        pdf_url="https://insp.cd/wp-content/uploads/2026/05/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_007-2026.pdf",
    )

    [enriched] = sources.enrich_pdf_metadata([source], sync_official_pdfs=True)

    assert enriched.status == "pdf_download_failed:TimeoutError"
    assert enriched.source_relation == "official_unchecked"
    assert enriched.parsed["source_gate_status"] == "blocked_official_unchecked"
    assert enriched.parsed["draft_status"] == "blocked"
    assert "blocked_official_unchecked" in enriched.parsed["blocking_reason"]


def test_source_identity_mismatch_blocks_drafts(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_013-2026.pdf"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"official source pdf bytes")
    official_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    source = sources.ReportSource(
        report_number=13,
        title="SitRep MVE N° 013/2026",
        post_url="https://insp.cd/sitrep-mve-n-013-2026/",
        post_id=13,
        pdf_url="https://insp.cd/wp-content/uploads/2026/05/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_013-2026.pdf",
        official_pdf_sha256=official_sha,
        parsed={
            "report_number": "014",
            "pdf_text_status": "text_extracted",
            "draft_status": "ready_for_review",
        },
    )

    [enriched] = sources.enrich_pdf_metadata([source])

    assert enriched.parsed["source_gate_status"] == "passed"
    assert enriched.parsed["source_identity_status"] == "blocked_report_number_mismatch"
    assert enriched.parsed["draft_status"] == "blocked"
    assert "blocked_report_number_mismatch" in enriched.parsed["blocking_reason"]
    assert sources.build_processed_draft_values([], [enriched]) == []


def test_processed_drafts_write_review_shaped_csvs(tmp_path: Path):
    table_row = sources.ExtractedValue(
        report_number=13,
        report_date="2026-05-27",
        nom_raw="Bunia",
        metric="cumulative_suspected_cases",
        value="249",
        source_pdf="https://insp.cd/example.pdf",
        source_post="https://insp.cd/sitrep-mve-n-013-2026/",
    )
    source = sources.ReportSource(
        report_number=13,
        title="SitRep MVE N° 013/2026",
        post_url="https://insp.cd/sitrep-mve-n-013-2026/",
        post_id=24889,
        pdf_url="https://insp.cd/example.pdf",
        source_relation="raw_matches_official",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed={
            "report_date": "2026-05-27",
            "national_confirmed_cases": "125",
            "draft_status": "ready_for_review",
        },
    )

    drafts = sources.build_processed_draft_values([table_row], [source])
    written = sources.write_processed_drafts(tmp_path / "drafts", drafts)

    assert {
        path.name for path in written
    } == {
        "insp_sitrep__cumulative_suspected_cases__daily.csv",
        "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
    }
    with (tmp_path / "drafts" / "insp_sitrep__cumulative_suspected_cases__daily.csv").open(
        newline="",
        encoding="utf-8",
    ) as f:
        assert list(csv.DictReader(f)) == [
            {"nom": "Bunia", "date": "2026-05-27", "cumulative_suspected_cases": "249"}
        ]
    with (
        tmp_path / "drafts" / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    ).open(newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f)) == [
            {"nom": "DRC", "date": "2026-05-27", "national_cumulative_confirmed_cases": "125"}
        ]

    processed = tmp_path / "processed"
    processed.mkdir()
    processed_path = processed / "insp_sitrep__cumulative_suspected_cases__daily.csv"
    with processed_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "cumulative_suspected_cases"])
        writer.writerow(["Bunia", "2026-05-27", "250"])
    national_path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    with national_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "national_cumulative_confirmed_cases"])
        writer.writerow(["DRC", "2026-05-27", "125"])

    counts = sources.write_processed_review(tmp_path / "review.csv", drafts, processed_dir=processed)

    assert counts["value_mismatch"] == 1
    assert "missing_processed" not in counts

    with processed_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Mongbalu", "2026-05-14", "246"])

    candidates = sources.write_processed_candidates(processed, drafts)

    assert candidates == []
    assert processed_path not in candidates
    with processed_path.open(newline="", encoding="utf-8") as f:
        candidate_rows = list(csv.DictReader(f))
    assert {"nom": "Mongbalu", "date": "2026-05-14", "cumulative_suspected_cases": "246"} in candidate_rows
    assert {"nom": "Bunia", "date": "2026-05-27", "cumulative_suspected_cases": "250"} in candidate_rows


def test_processed_review_marks_missing_rows_as_candidate_added_in_candidate_mode(tmp_path: Path):
    draft = sources.ProcessedDraftValue(
        metric="cumulative_contacts_traced",
        nom="Oicha",
        date="2026-05-27",
        value="ND",
        source_report_number=13,
        source_pdf="https://insp.cd/example.pdf",
        source_post="https://insp.cd/sitrep-mve-n-013-2026/",
        method="pdftotext_layout_table_ii",
    )

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        [draft],
        processed_dir=tmp_path / "processed",
        candidate_mode=True,
    )

    assert counts == {"candidate_added": 1}
    with (tmp_path / "review.csv").open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["status"] == "candidate_added"
    assert row["nom"] == "Oicha"


def test_processed_review_flags_confirmed_cumulative_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "national_cumulative_confirmed_cases"])
        writer.writerow(["DRC", "2026-05-29", "263"])
        writer.writerow(["DRC", "2026-05-30", "238"])

    counts = sources.write_processed_review(tmp_path / "review.csv", [], processed_dir=processed)

    assert counts["manual_review_required"] == 1
    with (tmp_path / "review.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[-1]["method"] == "processed_monotonicity_check"
    assert rows[-1]["metric"] == "national_cumulative_confirmed_cases"
    assert rows[-1]["nom"] == "DRC"
    assert rows[-1]["processed_value"] == "238"
    assert rows[-1]["blocking_reason"] == "cumulative_decrease:2026-05-29=263>2026-05-30=238"


def test_processed_review_flags_candidate_confirmed_cumulative_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "national_cumulative_confirmed_cases"])
        writer.writerow(["DRC", "2026-05-30", "321"])
    draft = sources.ProcessedDraftValue(
        metric="national_cumulative_confirmed_cases",
        nom="DRC",
        date="2026-05-31",
        value="300",
        source_report_number=18,
        source_pdf="https://insp.cd/example.pdf",
        source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
        method="pdftotext_layout_headline",
    )

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        [draft],
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["manual_review_required"] == 1
    with (tmp_path / "review.csv").open(newline="", encoding="utf-8") as f:
        [row] = list(csv.DictReader(f))
    assert row["status"] == "manual_review_required"
    assert row["draft_status"] == "manual_review_required"
    assert row["blocking_reason"] == "cumulative_decrease:2026-05-30=321>2026-05-31=300"


def test_processed_candidates_include_confirmed_cumulative_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    path.write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-05-30,321\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="national_cumulative_confirmed_cases",
            nom="DRC",
            date="2026-05-31",
            value="300",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_headline",
        )
    ]

    assert sources.write_processed_candidates(processed, drafts) == [path]
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,national_cumulative_confirmed_cases",
        "DRC,2026-05-30,321",
        "DRC,2026-05-31,300",
    ]


def test_processed_candidates_include_suspected_cumulative_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_suspected_cases__daily.csv"
    path.write_text(
        "nom,date,national_cumulative_suspected_cases\n"
        "DRC,2026-05-30,349\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="national_cumulative_suspected_cases",
            nom="DRC",
            date="2026-05-31",
            value="300",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_headline",
        )
    ]

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["manual_review_required"] == 1
    assert sources.write_processed_candidates(processed, drafts) == [path]
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,national_cumulative_suspected_cases",
        "DRC,2026-05-30,349",
        "DRC,2026-05-31,300",
    ]


def test_processed_candidates_include_alias_equivalent_cumulative_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__cumulative_confirmed_cases__daily.csv"
    path.write_text(
        "nom,date,cumulative_confirmed_cases\n"
        "Nyankunde,2026-05-30,12\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="cumulative_confirmed_cases",
            nom="Nyakunde",
            date="2026-05-31",
            value="11",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_table_ii",
        )
    ]

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["manual_review_required"] == 1
    assert sources.write_processed_candidates(processed, drafts) == [path]
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,cumulative_confirmed_cases",
        "Nyankunde,2026-05-30,12",
        "Nyakunde,2026-05-31,11",
    ]


def test_processed_candidates_include_candidate_that_creates_future_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    path.write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-05-31,300\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="national_cumulative_confirmed_cases",
            nom="DRC",
            date="2026-05-30",
            value="321",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_headline",
        )
    ]

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["manual_review_required"] == 1
    assert sources.write_processed_candidates(processed, drafts) == [path]
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,national_cumulative_confirmed_cases",
        "DRC,2026-05-31,300",
        "DRC,2026-05-30,321",
    ]


def test_processed_candidates_recheck_after_blocking_candidate_pair_decrease(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    path.write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-05-29,95\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="national_cumulative_confirmed_cases",
            nom="DRC",
            date="2026-05-30",
            value="100",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_headline",
        ),
        sources.ProcessedDraftValue(
            metric="national_cumulative_confirmed_cases",
            nom="DRC",
            date="2026-05-31",
            value="90",
            source_report_number=19,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n019-mvb_02-2026/",
            method="pdftotext_layout_headline",
        ),
    ]

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["candidate_added"] == 1
    assert counts["manual_review_required"] == 1
    sources.write_processed_candidates(processed, drafts)
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,national_cumulative_confirmed_cases",
        "DRC,2026-05-29,95",
        "DRC,2026-05-30,100",
        "DRC,2026-05-31,90",
    ]


def test_processed_candidates_require_candidate_to_clear_processed_high_water_mark(tmp_path: Path):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__national_cumulative_confirmed_cases__daily.csv"
    path.write_text(
        "nom,date,national_cumulative_confirmed_cases\n"
        "DRC,2026-05-29,263\n"
        "DRC,2026-05-30,238\n",
        encoding="utf-8",
    )
    drafts = [
        sources.ProcessedDraftValue(
            metric="national_cumulative_confirmed_cases",
            nom="DRC",
            date="2026-05-31",
            value="240",
            source_report_number=18,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-n018-mvb_01-2026/",
            method="pdftotext_layout_headline",
        )
    ]

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        processed_dir=processed,
        candidate_mode=True,
    )

    assert counts["manual_review_required"] == 2
    assert sources.write_processed_candidates(processed, drafts) == [path]
    assert path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,national_cumulative_confirmed_cases",
        "DRC,2026-05-29,263",
        "DRC,2026-05-30,238",
        "DRC,2026-05-31,240",
    ]


def test_processed_candidates_preserve_existing_rows_and_append_only(
    tmp_path: Path,
    monkeypatch,
):
    processed = tmp_path / "processed"
    processed.mkdir()
    processed_path = processed / "insp_sitrep__cumulative_suspected_deaths__daily.csv"
    processed_path.write_bytes(
        b"nom,date,cumulative_suspected_deaths\r\nNyankunde,2026-05-27,15\r\n"
    )

    def canonical(name: str) -> str | None:
        return "Nyakunde" if name in {"Nyankunde", "Nyakunde"} else None

    monkeypatch.setattr(sources, "to_canonical", canonical)
    drafts = [
        sources.ProcessedDraftValue(
            metric="cumulative_suspected_deaths",
            nom="Nyakunde",
            date="2026-05-27",
            value="11",
            source_report_number=13,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-mve-n-013-2026/",
            method="pdftotext_layout_table_ii",
        ),
        sources.ProcessedDraftValue(
            metric="cumulative_suspected_deaths",
            nom="Nyakunde",
            date="2026-05-28",
            value="16",
            source_report_number=14,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-mve-n-014-2026/",
            method="pdftotext_layout_table_ii",
        ),
    ]

    candidates = sources.write_processed_candidates(processed, drafts)

    assert candidates == [processed_path]
    with processed_path.open(newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f)) == [
            {"nom": "Nyankunde", "date": "2026-05-27", "cumulative_suspected_deaths": "15"},
            {"nom": "Nyakunde", "date": "2026-05-28", "cumulative_suspected_deaths": "16"},
        ]
    assert b"\r\n" in processed_path.read_bytes()


def test_processed_candidates_skip_existing_row_with_equivalent_date_format(
    tmp_path: Path,
    monkeypatch,
):
    processed = tmp_path / "processed"
    processed.mkdir()
    processed_path = processed / "insp_sitrep__cumulative_confirmed_cases__daily.csv"
    processed_path.write_text(
        "nom,date,cumulative_confirmed_cases\n"
        "Mongbalu,27/05/2026,20\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sources, "to_canonical", lambda name: "Mongbalu")
    drafts = [
        sources.ProcessedDraftValue(
            metric="cumulative_confirmed_cases",
            nom="Mongbalu",
            date="2026-05-27",
            value="20",
            source_report_number=13,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-mve-n-013-2026/",
            method="pdftotext_layout_table_ii",
        )
    ]

    candidates = sources.write_processed_candidates(processed, drafts)

    assert candidates == []
    assert processed_path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,cumulative_confirmed_cases",
        "Mongbalu,27/05/2026,20",
    ]


def test_processed_candidates_reuse_existing_display_date_for_same_day(
    tmp_path: Path,
    monkeypatch,
):
    processed = tmp_path / "processed"
    processed.mkdir()
    processed_path = processed / "insp_sitrep__cumulative_contacts_traced__daily.csv"
    processed_path.write_text(
        "nom,date,cumulative_contacts_traced\n"
        "Kyondo,27/05/2026,16\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sources, "to_canonical", lambda name: name)
    drafts = [
        sources.ProcessedDraftValue(
            metric="cumulative_contacts_traced",
            nom="Oicha",
            date="2026-05-27",
            value="ND",
            source_report_number=13,
            source_pdf="https://insp.cd/example.pdf",
            source_post="https://insp.cd/sitrep-mve-n-013-2026/",
            method="pdftotext_layout_table_ii",
        )
    ]

    candidates = sources.write_processed_candidates(processed, drafts)

    assert candidates == [processed_path]
    assert processed_path.read_text(encoding="utf-8").splitlines() == [
        "nom,date,cumulative_contacts_traced",
        "Kyondo,27/05/2026,16",
        "Oicha,27/05/2026,ND",
    ]


def test_processed_drafts_remove_stale_generated_metric_files(tmp_path: Path):
    output_dir = tmp_path / "drafts"
    output_dir.mkdir()
    stale = output_dir / sources.PROCESSED_DRAFT_BY_METRIC["national_cumulative_confirmed_cases"]
    stale.write_text("nom,date,national_cumulative_confirmed_cases\nBunia,2026-05-01,1\n")
    value = sources.ProcessedDraftValue(
        metric="cumulative_suspected_cases",
        nom="Bunia",
        date="2026-05-27",
        value="249",
        source_report_number=13,
        source_pdf="https://insp.cd/example.pdf",
        source_post="https://insp.cd/sitrep-mve-n-013-2026/",
        method="pdftotext_layout_table_ii",
    )

    written = sources.write_processed_drafts(output_dir, [value])

    assert written == [output_dir / sources.PROCESSED_DRAFT_BY_METRIC["cumulative_suspected_cases"]]
    assert not stale.exists()


def test_processed_drafts_require_verified_source_gate():
    source = sources.ReportSource(
        report_number=13,
        title="SitRep MVE N° 013/2026",
        post_url="https://insp.cd/sitrep-mve-n-013-2026/",
        post_id=24889,
        pdf_url="https://insp.cd/example.pdf",
        source_relation="raw_matches_official",
        parsed={
            "report_date": "2026-05-27",
            "national_confirmed_cases": "125",
            "draft_status": "ready_for_review",
        },
    )

    row = sources.ExtractedValue(
        report_number=13,
        report_date="2026-05-27",
        nom_raw="Bunia",
        metric="cumulative_suspected_cases",
        value="249",
        source_pdf=source.pdf_url,
        source_post=source.post_url,
    )

    assert sources.build_processed_draft_values([row], [source]) == []


def test_verified_sitreps_15_16_17_write_expected_national_drafts():
    fixtures = [
        (15, SITREP15_TEXT),
        (16, SITREP16_TEXT),
        (17, SITREP17_TEXT),
    ]
    report_sources = []
    for report_number, text in fixtures:
        report_sources.append(
            sources.ReportSource(
                report_number=report_number,
                title=f"SitRep N°{report_number:03d}/MVB_31/2026",
                post_url=f"https://insp.cd/sitrep-n{report_number:03d}-mvb_31-2026/",
                post_id=report_number,
                pdf_url=f"https://insp.cd/example-{report_number}.pdf",
                raw_path=f"data/insp_sitrep/raw/SitRep_MVE_{report_number:03d}-2026.pdf",
                source_relation="raw_matches_official",
                pdf_sha256=VERIFIED_SHA,
                official_pdf_sha256=VERIFIED_SHA,
                parsed=sources.parse_pdf_text(text),
            )
        )

    drafts = sources.build_processed_draft_values([], report_sources)

    assert {
        (draft.metric, draft.nom, draft.date, draft.value)
        for draft in drafts
    } == {
        ("national_cumulative_confirmed_cases", "DRC", "2026-05-29", "263"),
        ("national_cumulative_confirmed_deaths", "DRC", "2026-05-29", "42"),
        ("national_cumulative_suspected_cases", "DRC", "2026-05-29", "349"),
        ("national_cumulative_confirmed_cases", "DRC", "2026-05-30", "282"),
        ("national_cumulative_confirmed_deaths", "DRC", "2026-05-30", "42"),
        ("national_suspected_cases_under_investigation", "DRC", "2026-05-30", "220"),
        ("national_suspected_cases_in_isolation", "DRC", "2026-05-30", "101"),
        ("national_cumulative_confirmed_cases", "DRC", "2026-05-31", "321"),
        ("national_cumulative_confirmed_deaths", "DRC", "2026-05-31", "48"),
        ("national_suspected_cases_under_investigation", "DRC", "2026-05-31", "116"),
        ("national_suspected_cases_in_isolation", "DRC", "2026-05-31", "104"),
    }


def test_unsupported_future_layout_blocks_drafts_and_writes_review_row(tmp_path: Path):
    parsed = sources.parse_pdf_text(UNKNOWN_FUTURE_TEXT)
    source = sources.ReportSource(
        report_number=15,
        title="SitRep MVE N° 015/2026",
        post_url="https://insp.cd/sitrep-mve-n-015-2026/",
        post_id=24895,
        pdf_url="https://insp.cd/example.pdf",
        source_relation="raw_matches_official",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed=parsed,
    )

    assert parsed["layout_status"] == "unsupported_text_layout"
    assert parsed["draft_status"] == "blocked"
    assert sources.build_processed_draft_values([], [source]) == []

    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        [],
        sources=[source],
        processed_dir=tmp_path / "processed",
    )

    assert counts["blocked"] == 1
    with (tmp_path / "review.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {
            "status": "blocked",
            "processed_file": "",
            "metric": "",
            "nom": "",
            "date": "2026-05-29",
            "processed_value": "",
            "extracted_value": "",
            "source_report_number": "015",
            "source_pdf": "https://insp.cd/example.pdf",
            "source_post": "https://insp.cd/sitrep-mve-n-015-2026/",
            "source_raw_path": "",
            "method": "manual_review_required",
            "draft_status": "blocked",
            "blocking_reason": "headline_not_found;table_ii_missing;national_values_not_found",
        }
    ]


def test_partial_layout_writes_manual_review_row(tmp_path: Path):
    source = sources.ReportSource(
        report_number=14,
        title="SitRep MVE N° 014/2026",
        post_url="https://insp.cd/sitrep-mve-n-014-2026/",
        post_id=24894,
        pdf_url="https://insp.cd/example.pdf",
        source_relation="raw_matches_official",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed=sources.parse_pdf_text(SITREP14_TEXT),
    )

    drafts = sources.build_processed_draft_values([], [source])
    counts = sources.write_processed_review(
        tmp_path / "review.csv",
        drafts,
        sources=[source],
        processed_dir=tmp_path / "processed",
    )

    assert {
        (draft.metric, draft.nom, draft.date, draft.value)
        for draft in drafts
    } == {
        ("national_cumulative_confirmed_cases", "DRC", "2026-05-28", "210"),
        ("national_cumulative_confirmed_deaths", "DRC", "2026-05-28", "17"),
        ("national_cumulative_suspected_cases", "DRC", "2026-05-28", "349"),
    }
    assert counts["manual_review_required"] == 1
    with (tmp_path / "review.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    manual_rows = [row for row in rows if row["status"] == "manual_review_required"]
    assert manual_rows[0]["source_report_number"] == "014"
    assert manual_rows[0]["blocking_reason"] == "table_ii_missing"


def test_source_review_queue_is_small_and_points_to_local_pdf(tmp_path: Path):
    source = sources.ReportSource(
        report_number=14,
        title="SitRep MVE N° 014/2026",
        post_url="https://insp.cd/sitrep-mve-n-014-2026/",
        post_id=24894,
        post_published_at="2026-05-30T14:03:52Z",
        post_modified_at="2026-05-30T14:03:57Z",
        pdf_url="https://insp.cd/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_014-2026.pdf",
        source_relation="raw_matches_official",
        last_modified="Sat, 30 May 2026 14:03:03 GMT",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        parsed=sources.parse_pdf_text(SITREP14_TEXT),
    )

    counts = sources.write_source_review_queue(tmp_path / "source_review_queue.csv", [source])

    assert counts == {"manual_review_required": 1}
    with (tmp_path / "source_review_queue.csv").open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["review_status"] == "manual_review_required"
    assert row["post_published_at"] == "2026-05-30T14:03:52Z"
    assert row["pdf_last_modified"] == "Sat, 30 May 2026 14:03:03 GMT"
    assert row["source_raw_path"] == "data/insp_sitrep/raw/SitRep_MVE_014-2026.pdf"
    assert row["blocking_reason"] == "table_ii_missing"
    assert "Open data/insp_sitrep/raw/SitRep_MVE_014-2026.pdf" in row["review_action"]


def test_review_summary_points_reviewer_to_small_queue_and_pdf(tmp_path: Path):
    source = sources.ReportSource(
        report_number=14,
        title="SitRep MVE N° 014/2026",
        post_url="https://insp.cd/sitrep-mve-n-014-2026/",
        post_id=24894,
        post_published_at="2026-05-30T14:03:52Z",
        post_modified_at="2026-05-30T14:03:57Z",
        pdf_url="https://insp.cd/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_014-2026.pdf",
        source_relation="raw_matches_official",
        last_modified="Sat, 30 May 2026 14:03:03 GMT",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        status="official_unchanged",
        parsed=sources.parse_pdf_text(SITREP14_TEXT),
    )

    sources.write_review_summary(
        tmp_path / "review_summary.md",
        [source],
        source_review_counts={"manual_review_required": 1},
        processed_review_counts={"missing_processed": 519, "value_mismatch": 2},
        extracted_count=4,
        draft_file_count=4,
        source_review_queue=tmp_path / "source_review_queue.csv",
        processed_review=tmp_path / "processed_draft_review.csv",
        processed_draft_dir=tmp_path / "processed_drafts",
    )

    summary = (tmp_path / "review_summary.md").read_text(encoding="utf-8")
    assert "Source review queue" in summary
    assert "INSP Source Timing" in summary
    assert "2026-05-30T14:03:52Z" in summary
    assert "Sat, 30 May 2026 14:03:03 GMT" in summary
    assert "field-level drafts" in summary
    assert "manual_review_required" in summary
    assert "value_mismatch: 2" in summary
    assert "data/insp_sitrep/raw/SitRep_MVE_014-2026.pdf" in summary
    assert "table_ii_missing" in summary


def test_compare_processed_reports_value_mismatches(tmp_path: Path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__cumulative_suspected_deaths__daily.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "cumulative_suspected_deaths"])
        writer.writerow(["Bunia", "2026-05-27", "55"])

    monkeypatch.setitem(
        sources.PROCESSED_BY_METRIC,
        "cumulative_suspected_deaths",
        path.name,
    )
    row = sources.ExtractedValue(
        report_number=13,
        report_date="2026-05-27",
        nom_raw="Bunia",
        metric="cumulative_suspected_deaths",
        value="48",
        source_pdf="",
        source_post="",
    )

    diffs = sources.compare_processed([row], processed_dir=processed)

    assert len(diffs) == 1
    assert "processed=55 extracted=48" in diffs[0]


def test_compare_processed_treats_equivalent_date_formats_as_same_row(
    tmp_path: Path,
    monkeypatch,
):
    processed = tmp_path / "processed"
    processed.mkdir()
    path = processed / "insp_sitrep__cumulative_confirmed_cases__daily.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nom", "date", "cumulative_confirmed_cases"])
        writer.writerow(["Mongbalu", "27/05/2026", "20"])

    monkeypatch.setitem(
        sources.PROCESSED_BY_METRIC,
        "cumulative_confirmed_cases",
        path.name,
    )
    monkeypatch.setattr(sources, "to_canonical", lambda name: "Mongbalu")
    row = sources.ExtractedValue(
        report_number=13,
        report_date="2026-05-27",
        nom_raw="Mongbalu",
        metric="cumulative_confirmed_cases",
        value="20",
        source_pdf="",
        source_post="",
    )

    assert sources.compare_processed([row], processed_dir=processed) == []


def test_main_compares_processed_before_writing_candidates(tmp_path: Path, monkeypatch):
    raw_path = tmp_path / "data" / "insp_sitrep" / "raw" / "SitRep_MVE_013-2026.pdf"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"pdf")
    source = sources.ReportSource(
        report_number=13,
        title="SitRep MVE N° 013/2026",
        post_url="https://insp.cd/sitrep-mve-n-013-2026/",
        post_id=13,
        pdf_url="https://insp.cd/example.pdf",
        raw_path="data/insp_sitrep/raw/SitRep_MVE_013-2026.pdf",
        pdf_sha256=VERIFIED_SHA,
        official_pdf_sha256=VERIFIED_SHA,
        source_relation="raw_matches_official",
        parsed={
            "report_date": "2026-05-27",
            "draft_status": "ready_for_review",
            "source_gate_status": "passed",
        },
    )
    extracted = sources.ExtractedValue(
        report_number=13,
        report_date="2026-05-27",
        nom_raw="Bunia",
        metric="cumulative_suspected_deaths",
        value="48",
        source_pdf=source.pdf_url,
        source_post=source.post_url,
    )
    order: list[str] = []

    monkeypatch.setattr(sources, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sources, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(sources, "discover_sources", lambda **kwargs: [source])
    monkeypatch.setattr(sources, "enrich_pdf_metadata", lambda rows, **kwargs: list(rows))

    def extract(path: Path, row_source: sources.ReportSource) -> list[sources.ExtractedValue]:
        order.append("extract")
        return [extracted]

    def compare(rows, processed_dir=sources.PROCESSED_DIR):
        order.append("compare")
        return ["value mismatch"]

    def write_candidates(processed_dir: Path, draft_values):
        order.append("candidate")
        return []

    monkeypatch.setattr(sources, "extract_table_ii_from_pdf", extract)
    monkeypatch.setattr(sources, "compare_processed", compare)
    monkeypatch.setattr(sources, "write_processed_candidates", write_candidates)

    exit_code = sources.main([
        "--compare-processed",
        "--write-processed-drafts",
        "--write-processed-candidates",
        "--write-source-reports",
        str(tmp_path / "source_reports.csv"),
        "--write-extracted-dir",
        str(tmp_path / "extracted"),
        "--write-processed-draft-dir",
        str(tmp_path / "drafts"),
        "--write-review-diffs",
        str(tmp_path / "review.csv"),
        "--write-source-review-queue",
        str(tmp_path / "source_review_queue.csv"),
        "--write-review-summary",
        str(tmp_path / "review_summary.md"),
    ])

    assert exit_code == 0
    assert order == ["extract", "compare", "candidate"]
