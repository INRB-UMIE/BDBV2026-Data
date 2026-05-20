"""Rewrite raw IOM IDP matrices into contract-compliant outputs.

Reads raw/matrix_individuals_{all_time,by_month,by_week}.csv where header/row
labels look like 'CD5401ZS01 | BUNIA', and writes:

  processed/idp__individuals__static.matrix.csv     (from all_time)
  processed/idp__individuals__monthly.matrix.csv    (from by_month, YYYY-MM -> YYYY-MM-01)
  processed/idp__individuals__weekly.matrix.csv     (from by_week)

Labels are normalised by parsing the ZSCode prefix and looking up the canonical
Nom from the shapefile (authoritative). If the ZSCode is not in the current
shapefile (e.g. legacy 'CD5401ZS01' for Bunia, which the current MoH shapefile
merges into CD5402ZS02), the trailing name is title-cased and resolved via the
alias table. When two input labels collapse onto the same canonical Nom (the
known case: both Bunia-coded entries), their row vectors are summed and their
column vectors are summed.

Run from repo root:
    python data/IDP/process.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.lib.schema import to_canonical, zscode_to_canonical  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
PROCESSED = HERE / "processed"

ZSCODE_LABEL_RE = re.compile(r"^\s*(?P<zscode>CD\d{4}ZS\d{2})\s*\|\s*(?P<name>.+?)\s*$")


def _label_to_canonical(label: str) -> str:
    m = ZSCODE_LABEL_RE.match(label)
    if not m:
        raise ValueError(f"IDP: label {label!r} does not match '<ZSCode> | <NAME>'")
    canonical = zscode_to_canonical(m.group("zscode"))
    if canonical is not None:
        return canonical
    # ZSCode not in current shapefile — fall back to the trailing name, title-cased.
    name = m.group("name").strip()
    canonical = to_canonical(name.title())
    if canonical is not None:
        return canonical
    raise ValueError(
        f"IDP: cannot resolve {label!r}: ZSCode {m.group('zscode')!r} not in shapefile "
        f"and title-cased name {name.title()!r} not a canonical Nom or alias"
    )


def _to_int(s: str) -> int:
    s = s.strip()
    return int(s) if s else 0


def _rewrite_snapshot() -> Path:
    src = RAW / "matrix_individuals_all_time.csv"
    dst = PROCESSED / "idp__individuals__static.matrix.csv"
    with src.open(newline="", encoding="utf-8-sig") as f_in:
        reader = csv.reader(f_in)
        header = next(reader)
        rows = list(reader)
    if header[0] != "origin_hz":
        raise ValueError(f"IDP: expected first header 'origin_hz', got {header[0]!r}")

    # Map each raw destination column to a canonical Nom; preserve order of first occurrence.
    col_canonical = [_label_to_canonical(h) for h in header[1:]]
    dest_order: list[str] = []
    dest_groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(col_canonical):
        if c not in dest_groups:
            dest_order.append(c)
        dest_groups[c].append(i)

    # Group rows by canonical origin; sum cell values across the same canonical destination.
    origin_order: list[str] = []
    origin_totals: dict[str, list[int]] = {}
    for row in rows:
        origin = _label_to_canonical(row[0])
        values = [_to_int(v) for v in row[1:]]
        if origin not in origin_totals:
            origin_order.append(origin)
            origin_totals[origin] = [0] * len(dest_order)
        for dest, idxs in zip(dest_order, [dest_groups[d] for d in dest_order]):
            origin_totals[origin][dest_order.index(dest)] += sum(values[i] for i in idxs)

    PROCESSED.mkdir(exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.writer(f_out)
        w.writerow(["nom", *dest_order])
        for origin in origin_order:
            w.writerow([origin, *origin_totals[origin]])
    return dst


def _rewrite_time_series(
    src_name: str,
    dst_name: str,
    date_col_in: str,
    date_normaliser,
) -> Path:
    src = RAW / src_name
    dst = PROCESSED / dst_name
    with src.open(newline="", encoding="utf-8-sig") as f_in:
        reader = csv.reader(f_in)
        header = next(reader)
        rows = list(reader)
    if header[0] != date_col_in:
        raise ValueError(f"IDP: expected first header {date_col_in!r}, got {header[0]!r}")
    if header[1] != "origin_hz":
        raise ValueError(f"IDP: expected second header 'origin_hz', got {header[1]!r}")

    col_canonical = [_label_to_canonical(h) for h in header[2:]]
    dest_order: list[str] = []
    dest_groups: dict[str, list[int]] = defaultdict(list)
    for i, c in enumerate(col_canonical):
        if c not in dest_groups:
            dest_order.append(c)
        dest_groups[c].append(i)

    # (date, origin) -> [destination totals]
    accumulator: dict[tuple[str, str], list[int]] = {}
    date_order: list[str] = []
    origin_seen_per_date: dict[str, list[str]] = defaultdict(list)
    seen_dates: set[str] = set()
    for row in rows:
        date = date_normaliser(row[0])
        if date not in seen_dates:
            seen_dates.add(date)
            date_order.append(date)
        origin = _label_to_canonical(row[1])
        if origin not in origin_seen_per_date[date]:
            origin_seen_per_date[date].append(origin)
        key = (date, origin)
        if key not in accumulator:
            accumulator[key] = [0] * len(dest_order)
        values = [_to_int(v) for v in row[2:]]
        for k, dest in enumerate(dest_order):
            accumulator[key][k] += sum(values[i] for i in dest_groups[dest])

    PROCESSED.mkdir(exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.writer(f_out)
        w.writerow(["date", "nom", *dest_order])
        for date in date_order:
            for origin in origin_seen_per_date[date]:
                w.writerow([date, origin, *accumulator[(date, origin)]])
    return dst


_YYYY_MM = re.compile(r"^(\d{4})-(\d{2})$")


def _month_to_iso(value: str) -> str:
    m = _YYYY_MM.match(value.strip())
    if not m:
        raise ValueError(f"IDP: expected YYYY-MM month, got {value!r}")
    return f"{m.group(1)}-{m.group(2)}-01"


def _week_passthrough(value: str) -> str:
    return value.strip()


def main() -> int:
    out_static = _rewrite_snapshot()
    out_monthly = _rewrite_time_series(
        "matrix_individuals_by_month.csv",
        "idp__individuals__monthly.matrix.csv",
        date_col_in="month",
        date_normaliser=_month_to_iso,
    )
    out_weekly = _rewrite_time_series(
        "matrix_individuals_by_week.csv",
        "idp__individuals__weekly.matrix.csv",
        date_col_in="week_start",
        date_normaliser=_week_passthrough,
    )
    for p in (out_static, out_monthly, out_weekly):
        print(f"wrote {p.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
