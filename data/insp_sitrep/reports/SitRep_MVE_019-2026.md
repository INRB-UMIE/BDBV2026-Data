# INSP SitRep digitisation report

| Field | Value |
| --- | --- |
| **Sitrep number** | 19 |
| **Digitiser** | INRB-UMIE Interop Manager draft, pending maintainer review |
| **Report date** | 2 June 2026 |
| **Digitising date** | 3 June 2026 |

## General note

SitRep 019 changes the reporting layout. It still reports health-zone cumulative confirmed
cases, cumulative confirmed deaths, and CFR in Table 1. It does not report the prior
health-zone suspected, contact, hospitalisation, or PoE tables at the same grain.

The new province-level tables in SitRep 019 are not forced into the current health-zone
processed CSV contracts. They are called out for maintainer review in the draft PR body.

Manual review note: Table 4 reports `dont suspects = 159` under patients in isolation.
This is a clearer source than the prior banner wording, but it changes the assumption used
in earlier reports for `national_suspected_cases_in_isolation`; this draft leaves it for
maintainer review rather than committing the value to that processed CSV.

---

## insp_sitrep__national_cumulative_confirmed_cases__daily.csv

**Updated this sitrep?** x Yes - No

**Decisions / notes:** Transcribed from the SitRep 019 banner: 363.

---

## insp_sitrep__national_cumulative_confirmed_deaths__daily.csv

**Updated this sitrep?** x Yes - No

**Decisions / notes:** Transcribed from the SitRep 019 banner: 62.

---

## insp_sitrep__national_cumulative_suspected_cases__daily.csv

**Updated this sitrep?** No

**Decisions / notes:** Not updated. SitRep 019 does not report the under-investigation
component needed to continue the previous sum-based protocol.

---

## insp_sitrep__national_suspected_cases_in_isolation__daily.csv

**Updated this sitrep?** No

**Decisions / notes:** Manual review. Table 4 reports patients in isolation: 206 total,
47 confirmed, and 159 suspected. This draft does not commit the 159 value because earlier
reports used banner wording and the semantics should be confirmed by maintainers.

---

## insp_sitrep__national_suspected_cases_under_investigation__daily.csv

**Updated this sitrep?** No

**Decisions / notes:** Not reported in SitRep 019.

---

## insp_sitrep__national_cumulative_suspected_deaths__daily.csv

**Updated this sitrep?** No

**Decisions / notes:** Not updated. Table 4 reports deaths among suspected/confirmed
patients combined, not separable suspected deaths.

---

## insp_sitrep__cumulative_confirmed_cases__daily.csv

**Updated this sitrep?** x Yes - No

**Decisions / notes:** Transcribed from Table 1, including `NA = 94` for non-ventilated
Ituri cases and the newly affected Rimba health zone.

---

## insp_sitrep__cumulative_confirmed_deaths__daily.csv

**Updated this sitrep?** x Yes - No

**Decisions / notes:** Transcribed from Table 1, including `NA = 10` for non-ventilated
Ituri deaths.

---

## insp_sitrep__new_confirmed_cases__daily.csv

**Updated this sitrep?** x Yes - No

**Decisions / notes:** Transcribed from the SitRep 019 highlights/province summary:
19 new confirmed cases, located in Rwampara (7), Bunia (5), Nyakunde (3), Rimba (3),
and Damas (1). Other Table 1 health zones receive 0. Previously tracked zones omitted
from SitRep 019 Table 1 receive ND.

---

## Existing health-zone operational CSVs

**Updated this sitrep?** No

**Decisions / notes:** SitRep 019 does not report health-zone suspected cases/deaths,
contacts, hospitalisation/patient movement, or PoE data at the prior processed CSV grain.
Relevant new data are province-level or national-level and are summarized for maintainer
review in the draft PR body.

---

## Province-level / new operational data surfaced for review

SitRep 019 includes province + total data not currently represented by existing
health-zone processed contracts:

- Province summary: confirmed cases/deaths, CFR, affected health zones, and new cases.
- Table 2: alerts reported, investigated, investigation rate, and validated.
- Table 3: contacts under follow-up, contacts seen in 24h, and follow-up rate.
- Table 4: patient movement, including patients in bed, admissions, deaths, non-case or
  recovered exits, escaped patients, total exits, patients in isolation, confirmed
  patients in isolation, and suspected patients in isolation.
- Section 4.3: province-level lab indicators, including Ituri samples analyzed and
  Nord-Kivu pending results.

These are not committed as new processed CSV contracts in this draft PR because adding
province-grain processed outputs is a schema decision for maintainers.
