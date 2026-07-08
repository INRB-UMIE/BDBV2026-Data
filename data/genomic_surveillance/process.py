"""Aggregate BDBV genome sequences to DRC health zones (sequence count per zone).

Reads:
  raw/bia_fasta_metadata_consensus_v0.1.tsv   one row per sequenced genome, with
                                              a consensus `health_zone` and
                                              `province` resolved from the FASTA
                                              header and the lab / DHIS2 linelists
                                              (see BDBV2026-Phylogenetic-analyses).

Writes:
  processed/genomic_surveillance__sequence_count__static.csv   nom, sequence_count
  process_log.csv                                              per-sequence audit:
                                              taxa, health_zone, province,
                                              resolved_nom, status
                                              (assigned / unresolved / no_zone)

Each genome's consensus `health_zone` is resolved to a canonical shapefile `Nom`
via data/aliases.csv (tools.lib.schema.to_canonical). Sequences that do not
resolve to a zone are logged and excluded from the contract vector so the QA
runner does not see unresolved noms.

Run from repo root:
    python data/genomic_surveillance/process.py
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.lib.schema import to_canonical  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW_TSV = HERE / "raw" / "bia_fasta_metadata_consensus_v0.1.tsv"
OUT_CSV = HERE / "processed" / "genomic_surveillance__sequence_count__static.csv"
LOG_CSV = HERE / "process_log.csv"

TBD = "TBD"


def _load_rows() -> list[dict[str, str]]:
    with RAW_TSV.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _resolve(rows: list[dict[str, str]]) -> tuple[Counter[str], list[dict[str, str]]]:
    """Return (per-zone counts, per-sequence log rows)."""
    per_zone: Counter[str] = Counter()
    log_rows: list[dict[str, str]] = []
    for row in rows:
        taxa = (row.get("taxa") or "").strip()
        health_zone = (row.get("health_zone") or "").strip()
        province = (row.get("province") or "").strip()

        if not health_zone or health_zone == TBD:
            status = "no_zone"
            resolved = ""
        else:
            resolved = to_canonical(health_zone) or ""
            if resolved:
                status = "assigned"
                per_zone[resolved] += 1
            else:
                status = "unresolved"

        log_rows.append(
            {
                "taxa": taxa,
                "health_zone": health_zone,
                "province": province,
                "resolved_nom": resolved,
                "status": status,
            }
        )
    return per_zone, log_rows


def main() -> int:
    rows = _load_rows()
    per_zone, log_rows = _resolve(rows)

    OUT_CSV.parent.mkdir(exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nom", "sequence_count"])
        for nom in sorted(per_zone):
            w.writerow([nom, per_zone[nom]])

    with LOG_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["taxa", "health_zone", "province", "resolved_nom", "status"]
        )
        w.writeheader()
        w.writerows(log_rows)

    status_counts = Counter(r["status"] for r in log_rows)
    total_assigned = sum(per_zone.values())
    print(f"wrote {OUT_CSV.relative_to(REPO_ROOT)} ({len(per_zone)} zones)")
    print(f"wrote {LOG_CSV.relative_to(REPO_ROOT)} ({len(log_rows)} sequences)")
    print(
        f"sequences assigned: {total_assigned}; "
        f"status breakdown: {dict(status_counts)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
