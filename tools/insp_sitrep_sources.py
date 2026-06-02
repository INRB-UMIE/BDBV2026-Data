"""Discover and extract public INSP SitRep MVE source reports.

The INSP SitRep workflow is intentionally split into two layers:

1. Source custody: discover official INSP post/PDF URLs, optionally download the
   PDFs into data/insp_sitrep/raw, and write report-level provenance.
2. Extraction support: parse stable, machine-readable facts from the PDF text
   and compare those extracted values with the existing processed CSV contract.

The module uses only the Python standard library plus the repository's existing
schema helpers. PDF text extraction is optional and uses the system `pdftotext`
binary when available.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import functools
import hashlib
import html
import json
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
INSP_SEARCH_URL = "https://insp.cd/wp-json/wp/v2/search"
INSP_POST_URL = "https://insp.cd/wp-json/wp/v2/posts/{post_id}"
ALIASES_CSV = REPO_ROOT / "data" / "aliases.csv"
DATA_DIR = REPO_ROOT / "data" / "insp_sitrep"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DEFAULT_SOURCE_REPORTS = DATA_DIR / "source_reports.csv"
DEFAULT_EXTRACTED_DIR = DATA_DIR / "extracted"
DEFAULT_PROCESSED_DRAFT_DIR = DEFAULT_EXTRACTED_DIR / "processed_drafts"
DEFAULT_REVIEW_DIFFS = DEFAULT_EXTRACTED_DIR / "processed_draft_review.csv"
DEFAULT_SOURCE_REVIEW_QUEUE = DEFAULT_EXTRACTED_DIR / "source_review_queue.csv"
DEFAULT_REVIEW_SUMMARY = DEFAULT_EXTRACTED_DIR / "review_summary.md"
TEXT_EXTRACTABLE_MIN_CHARS = 200

REPORT_TITLE_RE = re.compile(
    r"SitRep\s+(?:MVE\s+N[°º]\s*0*(?P<old_number>\d+)/2026|"
    r"N[°º]\s*0*(?P<new_number>\d+)/MV[BE]_\d{1,2}(?:[/_]\d{1,2})?[/_]2026)",
    re.I,
)
PDF_HREF_RE = re.compile(r"""href=["'](?P<href>[^"']+\.pdf)["']""", re.I)
PDF_URL_TEXT_RE = re.compile(r"https://insp\.cd/wp-content/uploads/[^\s\"'<>]+\.pdf", re.I)
PDFEMB_DATA_RE = re.compile(r"[?&]pdfemb-data=(?P<payload>[^\"'&<>\s]+)", re.I)
SITREP_LABEL_RE = re.compile(
    r"SitRep\s+N[°º]\s*0*(?P<number>\d+)/(?:MV[BE]_)?(?P<day>\d{1,2})(?:[/_]\d{1,2})?[/_]2026",
    re.I,
)
HEADLINE_RE = re.compile(
    r"(?m)^\s*"
    r"(?P<confirmed_cases>\d[\d ]*)\s+"
    r"(?P<confirmed_deaths>\d[\d ]*)\s+"
    r"(?P<suspected_cases>\d[\d ]*)\*?\s+"
    r"(?P<suspected_deaths>\d[\d ]*)\s+"
    r"\d{1,3},\d%\s+\d{1,3},\d%"
)
COUNT_TOKEN_RE = re.compile(r"\bND\b|\d+(?:[ \u00a0]\d+)*\*?", re.I)

FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

TABLE_II_METRIC_ANCHORS = (
    (68, "cumulative_suspected_cases"),
    (83, "cumulative_suspected_deaths"),
    (101, "cumulative_confirmed_cases"),
    (119, "cumulative_contacts_traced"),
)
TABLE_II_METRIC_ORDER = (
    "cumulative_suspected_cases",
    "cumulative_suspected_deaths",
    "cumulative_confirmed_cases",
    "cumulative_contacts_traced",
)

PROCESSED_BY_METRIC = {
    "cumulative_suspected_cases": "insp_sitrep__cumulative_suspected_cases__daily.csv",
    "cumulative_suspected_deaths": "insp_sitrep__cumulative_suspected_deaths__daily.csv",
    "cumulative_confirmed_cases": "insp_sitrep__cumulative_confirmed_cases__daily.csv",
    "cumulative_confirmed_deaths": "insp_sitrep__cumulative_confirmed_deaths__daily.csv",
    "cumulative_contacts_traced": "insp_sitrep__cumulative_contacts_traced__daily.csv",
}
NATIONAL_BY_PARSED_FIELD = {
    "national_confirmed_cases": "national_cumulative_confirmed_cases",
    "national_confirmed_deaths": "national_cumulative_confirmed_deaths",
    "national_suspected_cases": "national_cumulative_suspected_cases",
    "national_suspected_deaths": "national_cumulative_suspected_deaths",
    "national_suspected_cases_under_investigation": "national_suspected_cases_under_investigation",
    "national_suspected_cases_in_isolation": "national_suspected_cases_in_isolation",
}
REQUIRED_NATIONAL_PARSED_FIELDS = (
    "national_confirmed_cases",
    "national_confirmed_deaths",
    "national_suspected_cases",
    "national_suspected_deaths",
)
PROCESSED_DRAFT_BY_METRIC = {
    **PROCESSED_BY_METRIC,
    "national_cumulative_confirmed_cases": "insp_sitrep__national_cumulative_confirmed_cases__daily.csv",
    "national_cumulative_confirmed_deaths": "insp_sitrep__national_cumulative_confirmed_deaths__daily.csv",
    "national_cumulative_suspected_cases": "insp_sitrep__national_cumulative_suspected_cases__daily.csv",
    "national_cumulative_suspected_deaths": "insp_sitrep__national_cumulative_suspected_deaths__daily.csv",
    "national_suspected_cases_under_investigation": "insp_sitrep__national_suspected_cases_under_investigation__daily.csv",
    "national_suspected_cases_in_isolation": "insp_sitrep__national_suspected_cases_in_isolation__daily.csv",
}
PDF_UPLOAD_PREFIX = "/wp-content/uploads/"
CUMULATIVE_REVIEW_METRICS = tuple(
    metric for metric in PROCESSED_DRAFT_BY_METRIC
    if "cumulative" in metric
)
HTTP_HEADERS = {"User-Agent": "INSP-SitRep-QA/1.0"}
SOURCE_GATE_ACCEPTED_RELATIONS = {"raw_matches_official"}
ACCEPTED_DRAFT_METHODS = {
    "pdftotext_layout_case_distribution",
    "pdftotext_layout_headline",
    "pdftotext_layout_table_ii",
    "withheld_by_sitrep",
}
UPDATE_NEEDED_EXIT_CODE = 2


@dataclass
class ReportSource:
    report_number: int
    title: str
    post_url: str
    post_id: int
    post_published_at: str = ""
    post_modified_at: str = ""
    pdf_url: str = ""
    raw_path: str = ""
    pdf_sha256: str = ""
    pdf_bytes: int | None = None
    official_pdf_sha256: str = ""
    official_pdf_bytes: int | None = None
    source_relation: str = "official_unchecked"
    last_modified: str = ""
    etag: str = ""
    status: str = "discovered"
    parsed: dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedValue:
    report_number: int
    report_date: str
    nom_raw: str
    metric: str
    value: str
    source_pdf: str
    source_post: str
    method: str = "pdftotext_layout_table_ii"

    @property
    def nom(self) -> str:
        return _canonical_table_label(self.nom_raw) or self.nom_raw


@dataclass
class ProcessedDraftValue:
    metric: str
    nom: str
    date: str
    value: str
    source_report_number: int
    source_pdf: str
    source_post: str
    method: str
    source_raw_path: str = ""


def _safe_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _tls_context(*, allow_insecure_tls: bool = False) -> ssl.SSLContext | None:
    if allow_insecure_tls:
        return ssl._create_unverified_context()
    try:
        import certifi  # type: ignore[import-not-found]
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _json_from_url(url: str, *, allow_insecure_tls: bool = False) -> object:
    request = urllib.request.Request(_safe_url(url), headers=HTTP_HEADERS)
    with urllib.request.urlopen(
        request,
        timeout=30,
        context=_tls_context(allow_insecure_tls=allow_insecure_tls),
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _text_from_url(url: str, *, allow_insecure_tls: bool = False) -> str:
    request = urllib.request.Request(_safe_url(url), headers=HTTP_HEADERS)
    with urllib.request.urlopen(
        request,
        timeout=30,
        context=_tls_context(allow_insecure_tls=allow_insecure_tls),
    ) as response:
        return response.read().decode("utf-8")


def _head_url(url: str, *, allow_insecure_tls: bool = False) -> dict[str, str]:
    request = urllib.request.Request(_safe_url(url), headers=HTTP_HEADERS, method="HEAD")
    with urllib.request.urlopen(
        request,
        timeout=30,
        context=_tls_context(allow_insecure_tls=allow_insecure_tls),
    ) as response:
        return {k.lower(): v for k, v in response.headers.items()}


def _download_url(url: str, path: Path, *, allow_insecure_tls: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(_safe_url(url), headers=HTTP_HEADERS)
    with urllib.request.urlopen(
        request,
        timeout=60,
        context=_tls_context(allow_insecure_tls=allow_insecure_tls),
    ) as response:
        path.write_bytes(response.read())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_canonical(value: str) -> str | None:
    from tools.lib.schema import to_canonical as schema_to_canonical

    return schema_to_canonical(value)


def _to_canonical(value: str) -> str | None:
    return to_canonical(value)


def _raw_filename(report_number: int) -> str:
    return f"SitRep_MVE_{report_number:03d}-2026.pdf"


def _extract_pdf_url(post: dict) -> str:
    content = html.unescape((post.get("content") or {}).get("rendered", ""))
    match = PDF_HREF_RE.search(content)
    if match:
        url = urllib.parse.urljoin(post.get("link", "https://insp.cd/"), match.group("href"))
        if _is_insp_upload_pdf(url):
            return url
    embedded = _extract_pdfemb_url(content)
    if embedded:
        return embedded
    match = PDF_URL_TEXT_RE.search(content)
    return match.group(0) if match else ""


def _extract_pdfemb_url(content: str) -> str:
    for match in PDFEMB_DATA_RE.finditer(content):
        payload = urllib.parse.unquote(match.group("payload"))
        try:
            decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8")
            data = json.loads(decoded)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        url = str(data.get("url") or "")
        if _is_insp_upload_pdf(url):
            return url
    return ""


def _is_insp_upload_pdf(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "insp.cd"
        and parsed.path.startswith(PDF_UPLOAD_PREFIX)
        and parsed.path.lower().endswith(".pdf")
    )


def _wp_timestamp(post: dict, gmt_field: str, local_field: str) -> str:
    value = str(post.get(gmt_field) or "")
    if value and value != "0000-00-00T00:00:00":
        return f"{value}Z"
    return str(post.get(local_field) or "")


def discover_sources(limit: int = 100, *, allow_insecure_tls: bool = False) -> list[ReportSource]:
    query = urllib.parse.urlencode({"search": "SitRep", "per_page": str(limit)})
    search_results = _json_from_url(
        f"{INSP_SEARCH_URL}?{query}",
        allow_insecure_tls=allow_insecure_tls,
    )
    if not isinstance(search_results, list):
        raise RuntimeError("INSP search API did not return a list")

    sources: dict[int, ReportSource] = {}
    for item in search_results:
        title = html.unescape(str(item.get("title", "")))
        report_number = _report_number_from_title(title)
        if report_number is None:
            continue
        post_id = int(item["id"])
        post = _json_from_url(
            INSP_POST_URL.format(post_id=post_id),
            allow_insecure_tls=allow_insecure_tls,
        )
        if not isinstance(post, dict):
            continue
        pdf_url = _extract_pdf_url(post)
        raw_path = f"data/insp_sitrep/raw/{_raw_filename(report_number)}"
        source = ReportSource(
            report_number=report_number,
            title=title,
            post_url=str(item.get("url") or post.get("link") or ""),
            post_id=post_id,
            post_published_at=_wp_timestamp(post, "date_gmt", "date"),
            post_modified_at=_wp_timestamp(post, "modified_gmt", "modified"),
            pdf_url=pdf_url,
            raw_path=raw_path,
            status="pdf_found" if pdf_url else "missing_pdf_url",
        )
        existing = sources.get(report_number)
        if existing is None or _prefer_source(source, existing):
            sources[report_number] = source

    return [sources[n] for n in sorted(sources)]


def _report_number_from_title(title: str) -> int | None:
    match = REPORT_TITLE_RE.search(title)
    if not match:
        return None
    return int(match.group("old_number") or match.group("new_number"))


def filter_sources_by_report_number(
    sources: Iterable[ReportSource],
    *,
    min_report_number: int | None = None,
    max_report_number: int | None = None,
) -> list[ReportSource]:
    filtered: list[ReportSource] = []
    for source in sources:
        if min_report_number is not None and source.report_number < min_report_number:
            continue
        if max_report_number is not None and source.report_number > max_report_number:
            continue
        filtered.append(source)
    return filtered


def _prefer_source(candidate: ReportSource, existing: ReportSource) -> bool:
    candidate_slug = f"sitrep-mve-n-{candidate.report_number:03d}"
    existing_slug = f"sitrep-mve-n-{existing.report_number:03d}"
    if candidate_slug in candidate.post_url and existing_slug not in existing.post_url:
        return True
    return bool(candidate.pdf_url) and not existing.pdf_url


def enrich_pdf_metadata(
    sources: Iterable[ReportSource],
    *,
    download_missing: bool = False,
    sync_official_pdfs: bool = False,
    verify_official_pdfs: bool = False,
    parse_pdfs: bool = False,
    allow_insecure_tls: bool = False,
    source_report_cache: dict[int, dict[str, str]] | None = None,
) -> list[ReportSource]:
    enriched: list[ReportSource] = []
    source_report_cache = source_report_cache or {}
    for source in sources:
        raw_path = REPO_ROOT / source.raw_path
        if raw_path.exists():
            source.pdf_sha256 = _sha256(raw_path)
            source.pdf_bytes = raw_path.stat().st_size
        if source.pdf_url:
            try:
                headers = _head_url(source.pdf_url, allow_insecure_tls=allow_insecure_tls)
                source.last_modified = headers.get("last-modified", "")
                source.etag = headers.get("etag", "")
                if headers.get("content-length"):
                    source.official_pdf_bytes = int(headers["content-length"])
            except OSError as exc:
                source.status = f"pdf_head_failed:{exc.__class__.__name__}"
        if source.pdf_url and (sync_official_pdfs or verify_official_pdfs):
            cached = source_report_cache.get(source.report_number, {})
            if _cached_official_still_current(source, cached):
                source.official_pdf_sha256 = cached["official_pdf_sha256"]
                source.official_pdf_bytes = _int_or_none(cached.get("official_pdf_bytes")) or source.official_pdf_bytes
                source.status = "official_unchanged"
            else:
                try:
                    official_path = _download_official_pdf(
                        source.pdf_url,
                        raw_path if sync_official_pdfs else None,
                        allow_insecure_tls=allow_insecure_tls,
                    )
                    source.official_pdf_sha256 = _sha256(official_path)
                    source.official_pdf_bytes = official_path.stat().st_size
                    if not sync_official_pdfs:
                        official_path.unlink(missing_ok=True)
                    if sync_official_pdfs:
                        source.status = "official_synced"
                except OSError as exc:
                    source.status = f"pdf_download_failed:{exc.__class__.__name__}"
        if download_missing and source.pdf_url and not raw_path.exists() and not sync_official_pdfs:
            _download_url(source.pdf_url, raw_path, allow_insecure_tls=allow_insecure_tls)
        if raw_path.exists():
            source.pdf_sha256 = _sha256(raw_path)
            if source.status == "discovered":
                source.status = "raw_available"
            source.pdf_bytes = raw_path.stat().st_size
            source.source_relation = _source_relation(source)
            if parse_pdfs:
                source.parsed = parse_pdf_path(raw_path)
            _apply_source_gate_status(source)
        elif source.official_pdf_sha256:
            source.source_relation = "missing_raw"
            _apply_source_gate_status(source)
        enriched.append(source)
    return enriched


def source_update_reasons(source: ReportSource, cached: dict[str, str]) -> list[str]:
    if not cached:
        return ["new_report"]

    reasons: list[str] = []
    for field_name in (
        "title",
        "post_published_at",
        "post_modified_at",
        "post_url",
        "pdf_url",
    ):
        current = str(getattr(source, field_name) or "")
        previous = str(cached.get(field_name, ""))
        if current and current != previous:
            reasons.append(f"{field_name}_changed")

    if source.status.startswith("pdf_head_failed:"):
        return reasons

    head_values = {
        "last_modified": source.last_modified,
        "etag": source.etag,
        "official_pdf_bytes": (
            "" if source.official_pdf_bytes is None else str(source.official_pdf_bytes)
        ),
    }
    for field_name, current in head_values.items():
        previous = str(cached.get(field_name, ""))
        if current and previous and current != previous:
            reasons.append(f"{field_name}_changed")

    return reasons


def source_update_report(
    sources: Iterable[ReportSource],
    source_report_cache: dict[int, dict[str, str]],
) -> dict[int, list[str]]:
    updates: dict[int, list[str]] = {}
    for source in sources:
        reasons = source_update_reasons(
            source,
            source_report_cache.get(source.report_number, {}),
        )
        if reasons:
            updates[source.report_number] = reasons
    return updates


def _cached_official_still_current(source: ReportSource, cached: dict[str, str]) -> bool:
    if not cached or not source.pdf_sha256:
        return False
    if cached.get("pdf_url") != source.pdf_url:
        return False
    if cached.get("source_gate_status") != "passed":
        return False
    if cached.get("pdf_sha256") != source.pdf_sha256:
        return False
    if cached.get("official_pdf_sha256") != source.pdf_sha256:
        return False

    cached_bytes = _int_or_none(cached.get("official_pdf_bytes"))
    if source.official_pdf_bytes is not None and cached_bytes != source.official_pdf_bytes:
        return False

    if source.etag and cached.get("etag") == source.etag:
        return True
    return bool(
        source.last_modified
        and cached.get("last_modified") == source.last_modified
        and source.official_pdf_bytes is not None
        and cached_bytes == source.official_pdf_bytes
    )


def _int_or_none(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _download_official_pdf(
    url: str,
    raw_path: Path | None,
    *,
    allow_insecure_tls: bool = False,
) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        _download_url(url, tmp_path, allow_insecure_tls=allow_insecure_tls)
        if raw_path is not None:
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            if raw_path.exists() and _sha256(raw_path) == _sha256(tmp_path):
                tmp_path.unlink()
                return raw_path
            tmp_path.replace(raw_path)
            return raw_path
        return tmp_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _source_relation(source: ReportSource) -> str:
    if not source.official_pdf_sha256:
        return "official_unchecked"
    if not source.pdf_sha256:
        return "missing_raw"
    if source.pdf_sha256 == source.official_pdf_sha256:
        return "raw_matches_official"
    return "raw_differs_from_official"


def _source_gate_status(source: ReportSource) -> str:
    if not source.pdf_url:
        return "blocked_missing_official_pdf_url"
    if source.pdf_sha256 and source.official_pdf_sha256 and source.pdf_sha256 == source.official_pdf_sha256:
        return "passed"
    if source.source_relation == "raw_differs_from_official":
        return "blocked_raw_differs_from_official"
    if source.source_relation == "missing_raw":
        return "blocked_missing_raw"
    if source.source_relation in SOURCE_GATE_ACCEPTED_RELATIONS:
        return "blocked_missing_hash_evidence"
    return "blocked_official_unchecked"


def _source_gate_passed(source: ReportSource | None) -> bool:
    return source is not None and _source_gate_status(source) == "passed"


def _apply_source_gate_status(source: ReportSource) -> None:
    status = _source_gate_status(source)
    source.parsed["source_gate_status"] = status
    identity_status = _source_identity_status(source)
    source.parsed["source_identity_status"] = identity_status
    if status != "passed":
        source.parsed["draft_status"] = "blocked"
        _append_blocking_reason(source.parsed, status)
    if identity_status.startswith("blocked_"):
        source.parsed["draft_status"] = "blocked"
        _append_blocking_reason(source.parsed, identity_status)


def _source_identity_status(source: ReportSource) -> str:
    parsed_report = source.parsed.get("report_number", "")
    if parsed_report:
        return "matched" if parsed_report == f"{source.report_number:03d}" else "blocked_report_number_mismatch"
    if source.parsed.get("pdf_text_status"):
        return "blocked_report_number_not_found"
    return "unchecked"


def parse_pdf_path(path: Path) -> dict[str, str]:
    try:
        return parse_pdf_text(_pdf_text(path))
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return _pdf_error_metadata(exc)


def _pdf_error_metadata(exc: BaseException) -> dict[str, str]:
    status = f"pdf_text_failed:{exc.__class__.__name__}"
    parsed = {
        "pdf_text_status": status,
        "text_extractable": "false",
        "text_chars": "0",
        "headline_status": status,
        "table_ii_status": status,
    }
    _classify_pdf_structure(parsed)
    _append_blocking_reason(parsed, status)
    return parsed


def _pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        raise RuntimeError("pdftotext is not available; install poppler to parse PDFs")
    with tempfile.TemporaryDirectory() as tmp:
        text_path = Path(tmp) / "sitrep.txt"
        subprocess.run(
            [pdftotext, "-layout", str(path), str(text_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return text_path.read_text(encoding="utf-8", errors="replace")


def parse_pdf_text(text: str) -> dict[str, str]:
    parsed = _text_metadata(text)
    if parsed["text_extractable"] != "true":
        parsed["headline_status"] = "text_not_extractable"
        parsed["table_ii_status"] = "text_not_extractable"
        _classify_pdf_structure(parsed)
        return parsed

    parsed.update(parse_report_text(text))
    parsed.setdefault("headline_status", "headline_not_found")
    parsed["table_ii_status"] = table_ii_status(text, parsed)
    _classify_pdf_structure(parsed)
    return parsed


def _text_metadata(text: str) -> dict[str, str]:
    text_chars = len(_usable_text(text))
    extractable = text_chars >= TEXT_EXTRACTABLE_MIN_CHARS
    return {
        "pdf_text_status": "text_extracted" if extractable else "text_not_extractable",
        "text_extractable": str(extractable).lower(),
        "text_chars": str(text_chars),
    }


def _usable_text(text: str) -> str:
    return "".join(ch for ch in text if not ch.isspace() and ch != "\f")


def _classify_pdf_structure(parsed: dict[str, str]) -> None:
    parsed["national_values_status"] = _national_values_status(parsed)
    if parsed.get("text_extractable") != "true":
        parsed["layout_status"] = "image_only_pdf"
        parsed["extraction_confidence"] = "blocked"
        parsed["draft_status"] = "blocked"
        parsed["blocking_reason"] = "not_publicly_extractable"
        return

    headline_extracted = parsed.get("headline_status") == "headline_extracted"
    table_status = parsed.get("table_ii_status", "")
    table_extracted = table_status in {"table_ii_extracted", "case_distribution_table_extracted"}
    national_status = parsed["national_values_status"]
    national_complete = national_status in {"found", "found_withheld_by_sitrep"}
    reasons: list[str] = []

    if headline_extracted and table_extracted and national_complete:
        parsed["layout_status"] = "known_text_layout"
        parsed["extraction_confidence"] = "high"
        parsed["draft_status"] = "ready_for_review"
        parsed["blocking_reason"] = ""
        return

    if headline_extracted or table_extracted:
        parsed["layout_status"] = "partial_extract"
        parsed["extraction_confidence"] = "partial"
        parsed["draft_status"] = "ready_for_review"
        if not headline_extracted:
            reasons.append(parsed.get("headline_status") or "headline_not_found")
        if not table_extracted and table_status:
            reasons.append(table_status)
        if headline_extracted and not national_complete:
            reasons.append(f"national_values_{national_status}")
        parsed["blocking_reason"] = ";".join(dict.fromkeys(reasons))
        return

    parsed["layout_status"] = "unsupported_text_layout"
    parsed["extraction_confidence"] = "blocked"
    parsed["draft_status"] = "blocked"
    if not parsed.get("report_number"):
        reasons.append("report_number_not_found")
    if not parsed.get("report_date"):
        reasons.append("report_date_not_found")
    reasons.append(parsed.get("headline_status") or "headline_not_found")
    if table_status:
        reasons.append(table_status)
    if not national_complete:
        reasons.append(f"national_values_{national_status}")
    parsed["blocking_reason"] = ";".join(dict.fromkeys(reasons))


def _national_values_status(parsed: dict[str, str]) -> str:
    values = [parsed.get(field, "") for field in REQUIRED_NATIONAL_PARSED_FIELDS]
    present = [value for value in values if value != ""]
    if not present:
        return "not_found"
    if len(present) < len(values):
        return "partial"
    if any(value == "ND" for value in present):
        return "found_withheld_by_sitrep"
    return "found"


def _append_blocking_reason(parsed: dict[str, str], reason: str) -> None:
    if not reason:
        return
    existing = [item for item in parsed.get("blocking_reason", "").split(";") if item]
    if reason not in existing:
        existing.append(reason)
    parsed["blocking_reason"] = ";".join(existing)


def parse_report_text(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    label = SITREP_LABEL_RE.search(text)
    if label:
        parsed["report_number"] = f"{int(label.group('number')):03d}"

    report_date = _extract_french_date(text, "Date de rapportage")
    publication_date = _extract_french_date(text, "Date de publication")
    if report_date:
        parsed["report_date"] = report_date.isoformat()
    if publication_date:
        parsed["publication_date"] = publication_date.isoformat()

    headline = _extract_cumulative_headline(text)
    if headline:
        for key, value in headline.items():
            parsed[f"national_{key}"] = value
        parsed["headline_status"] = "headline_extracted"
    else:
        parsed["headline_status"] = "headline_not_found"

    notes = _revision_notes(text)
    if notes:
        parsed["revision_notes"] = " | ".join(notes)
    return parsed


def _extract_cumulative_headline(text: str) -> dict[str, str]:
    revised = _extract_revised_confirmed_banner(text)
    if revised:
        return revised

    aligned = _extract_aligned_cumulative_banner(text)
    if aligned:
        return aligned

    headline = HEADLINE_RE.search(text)
    if not headline:
        return {}
    return {
        key: str(_parse_int(value))
        for key, value in headline.groupdict().items()
    }


def _extract_revised_confirmed_banner(text: str) -> dict[str, str]:
    label = SITREP_LABEL_RE.search(text)
    if not label or int(label.group("number")) < 19:
        return {}
    if "Patients en" not in text or "Nombre cumulé" not in text or "Taux de suivi" not in text:
        return {}

    lines = text.splitlines()
    first_label_line = _find_line_containing(lines[:80], "Cumul cas confirmés")
    if first_label_line is None:
        return {}
    start = max(0, first_label_line - 8)
    for line in lines[start:first_label_line]:
        match = re.match(
            r"^\s*"
            r"(?P<confirmed_cases>\d[\d \u00a0]*\*?)\s+"
            r"(?P<confirmed_deaths>\d[\d \u00a0]*)"
            r"(?:\s+\([^)]*\))?\s+"
            r"(?P<patients_in_isolation>\d[\d \u00a0]*)\s+"
            r"(?P<recovered>\d[\d \u00a0]*)\s+"
            r"(?P<contact_followup_rate>\d{1,3},\d+%)\s*$",
            line,
        )
        if not match:
            continue
        values = match.groupdict()
        return {
            "confirmed_cases": _normalize_count_token(values["confirmed_cases"]),
            "confirmed_deaths": _normalize_count_token(values["confirmed_deaths"]),
            "patients_in_isolation": _normalize_count_token(values["patients_in_isolation"]),
            "recovered": _normalize_count_token(values["recovered"]),
            "contact_followup_rate": values["contact_followup_rate"],
        }
    return {}


def _extract_aligned_cumulative_banner(text: str) -> dict[str, str]:
    lines = text.splitlines()
    anchors = _headline_label_anchors(lines)
    if not anchors:
        return {}

    first_label_line = min(line_idx for line_idx, _ in anchors.values())
    value_tokens = _headline_value_tokens(lines, first_label_line)
    report_number = ""
    label = SITREP_LABEL_RE.search(text)
    if label:
        report_number = f"{int(label.group('number')):03d}"
    extracted: dict[str, str] = {}
    for metric, token in _ordered_headline_values(anchors, value_tokens, report_number=report_number).items():
        extracted[metric] = token

    if "suspected_deaths" not in extracted and _suspected_deaths_withheld(text):
        extracted["suspected_deaths"] = "ND"
    has_cumulative_suspected = "suspected_cases" in extracted
    has_split_suspected = {
        "suspected_cases_under_investigation",
        "suspected_cases_in_isolation",
    } <= extracted.keys()
    required = {"confirmed_cases", "confirmed_deaths"}
    return extracted if required <= extracted.keys() and (has_cumulative_suspected or has_split_suspected) else {}


def _ordered_headline_values(
    anchors: dict[str, tuple[int, int]],
    value_tokens: list[tuple[int, str]],
    *,
    report_number: str = "",
) -> dict[str, str]:
    ordered_anchors = sorted(
        ((column, metric) for metric, (_, column) in anchors.items()),
        key=lambda item: item[0],
    )
    ordered_tokens = sorted(value_tokens, key=lambda item: item[0])
    assigned: dict[str, str] = {}
    for (column, metric), (token_column, token) in zip(ordered_anchors, ordered_tokens):
        if abs(token_column - column) <= 45:
            assigned[metric] = _normalize_headline_metric_token(metric, token, report_number=report_number)
    return assigned


def _normalize_headline_metric_token(metric: str, token: str, *, report_number: str = "") -> str:
    if (
        report_number == "015"
        and metric == "suspected_cases"
        and token.isdigit()
        and len(token) == 4
        and token.endswith("1")
        and 300 <= int(token[:-1]) < 1000
    ):
        return token[:-1]
    return token


def _headline_label_anchors(lines: list[str]) -> dict[str, tuple[int, int]]:
    anchors: dict[str, tuple[int, int]] = {}
    for line_idx, line in enumerate(lines[:80]):
        for match in re.finditer(r"Cumul\s+cas", line, re.I):
            context = _column_context(lines, line_idx, match.start())
            if "cte" in context:
                continue
            if "suspect" in context:
                anchors.setdefault("suspected_cases", (line_idx, match.start()))
            elif "confirm" in context:
                anchors.setdefault("confirmed_cases", (line_idx, match.start()))
        for match in re.finditer(r"Cumul\s+d[ée]c[eè]s", line, re.I):
            context = _column_context(lines, line_idx, match.start(), width=26)
            metric = "confirmed_deaths" if "confirm" in context or "parmi les" in context else "suspected_deaths"
            if "suspect" in context and "confirm" not in context:
                metric = "suspected_deaths"
            anchors.setdefault(metric, (line_idx, match.start()))
        for match in re.finditer(r"Cas\s+confirm[ée]s?", line, re.I):
            context = _column_context(lines, line_idx, match.start(), width=36)
            if "actif" in context:
                anchors.setdefault("confirmed_active", (line_idx, match.start()))
        for match in re.finditer(r"Cas\s+suspects?", line, re.I):
            context = _column_context(lines, line_idx, match.start(), width=44)
            if "investigation" in context:
                anchors.setdefault("suspected_cases_under_investigation", (line_idx, match.start()))
            elif "isolement" in context:
                anchors.setdefault("suspected_cases_in_isolation", (line_idx, match.start()))
        for match in re.finditer(r"Patients?", line, re.I):
            context = _column_context(lines, line_idx, match.start(), width=44)
            if "isolement" in context or "hospitalisation" in context:
                anchors.setdefault("suspected_cases_in_isolation", (line_idx, match.start()))
        for match in re.finditer(r"Gu[ée]ris", line, re.I):
            anchors.setdefault("recovered", (line_idx, match.start()))
    return anchors


def _column_context(lines: list[str], line_idx: int, column: int, *, width: int = 34, depth: int = 4) -> str:
    fragments = []
    start = max(0, column - 4)
    end = column + width
    for line in lines[line_idx:line_idx + depth]:
        fragments.append(line[start:end])
    return " ".join(" ".join(fragments).lower().split())


def _headline_value_tokens(lines: list[str], first_label_line: int) -> list[tuple[int, str]]:
    publication_line = _find_line_containing(lines[:first_label_line], "Date de publication")
    start = publication_line + 1 if publication_line is not None else max(0, first_label_line - 8)
    tokens: list[tuple[int, str]] = []
    for line in lines[start:first_label_line]:
        for match in COUNT_TOKEN_RE.finditer(line):
            token = _normalize_count_token(match.group(0))
            if token:
                tokens.append((match.start(), token))
    return tokens


def _find_line_containing(lines: list[str], needle: str) -> int | None:
    needle = needle.lower()
    for index, line in enumerate(lines):
        if needle in line.lower():
            return index
    return None


def _normalize_count_token(value: str) -> str:
    clean = value.replace("*", "").replace("\u00a0", " ").strip()
    if clean.upper() == "ND":
        return "ND"
    return str(_parse_int(clean))


def _suspected_deaths_withheld(text: str) -> bool:
    compact = " ".join(text.lower().split())
    return (
        "décès suspects" in compact
        and ("temporairement exclu" in compact or "attente des résultats" in compact)
    )


def _extract_french_date(text: str, label: str) -> date | None:
    pattern = re.compile(rf"{re.escape(label)}\s+(?P<value>\d{{1,2}}\s+\w+\s+2026)", re.I)
    match = pattern.search(text)
    if not match:
        return None
    return _parse_french_date(match.group("value"))


def _parse_french_date(value: str) -> date:
    parts = value.strip().lower().split()
    if len(parts) != 3:
        raise ValueError(f"not a French date: {value!r}")
    day = int(parts[0])
    month = FRENCH_MONTHS[parts[1]]
    year = int(parts[2])
    return date(year, month, day)


def _parse_int(value: str) -> int:
    return int(value.replace(" ", "").replace("\u00a0", "").replace("*", ""))


def _revision_notes(text: str) -> list[str]:
    notes: list[str] = []
    for line in text.splitlines():
        clean = " ".join(line.strip().split())
        lowered = clean.lower()
        if not clean:
            continue
        if (
            "revu à la baisse" in lowered
            or "susceptibles de changer" in lowered
            or ("décès suspects" in lowered and "exclu" in lowered)
        ):
            notes.append(clean.lstrip("* "))
    return notes


def table_ii_status(text: str, parsed: dict[str, str] | None = None) -> str:
    if len(_usable_text(text)) < TEXT_EXTRACTABLE_MIN_CHARS:
        return "text_not_extractable"
    section = _table_ii_section(text)
    if not section:
        return "table_ii_missing"
    parsed = parsed or parse_report_text(text)
    report_number = int(parsed.get("report_number") or 0)
    source = ReportSource(
        report_number=report_number,
        title="",
        post_url="",
        post_id=0,
        parsed=parsed,
    )
    extracted = extract_table_ii(text, source)
    if not extracted:
        return "table_ii_unparsed"
    if any(row.method == "pdftotext_layout_case_distribution" for row in extracted):
        return "case_distribution_table_extracted"
    return "table_ii_extracted"


def extract_table_ii(text: str, source: ReportSource) -> list[ExtractedValue]:
    section = _table_ii_section(text)
    report_date = source.parsed.get("report_date", "")
    table_date = _extract_table_asof_date(section)
    if table_date:
        report_date = table_date.isoformat()
    if not report_date:
        report_date = parse_report_text(text).get("report_date", "")
    if _is_confirmed_case_distribution_section(section):
        return _extract_confirmed_case_distribution(section, source, report_date)
    rows: list[ExtractedValue] = []
    for line in section.splitlines():
        label = _table_label(line)
        if not label or _canonical_table_label(label) is None:
            label = _find_known_table_label(line)
        if not label or _skip_table_label(label):
            continue
        if _canonical_table_label(label) is None:
            continue
        assigned = _assign_table_values_after_label(line, label)
        if not assigned:
            assigned = _assign_table_values(line)
        for metric, value in assigned.items():
            rows.append(
                ExtractedValue(
                    report_number=source.report_number,
                    report_date=report_date,
                    nom_raw=label,
                    metric=metric,
                    value=value,
                    source_pdf=source.pdf_url,
                    source_post=source.post_url,
                )
            )
    return rows


def _is_confirmed_case_distribution_section(section: str) -> bool:
    compact = " ".join(section.split()).lower()
    return (
        "cas confirmés" in compact
        and "décès confirmés" in compact
        and "cumulés" in compact
        and "cas suspects" not in compact
    )


def _extract_confirmed_case_distribution(
    section: str,
    source: ReportSource,
    report_date: str,
) -> list[ExtractedValue]:
    rows: list[ExtractedValue] = []
    for line in section.splitlines():
        label = _confirmed_distribution_label(line)
        if not label:
            continue
        values = _confirmed_distribution_values(line, label)
        if not values:
            continue
        for metric, value in values.items():
            rows.append(
                ExtractedValue(
                    report_number=source.report_number,
                    report_date=report_date,
                    nom_raw=label,
                    metric=metric,
                    value=value,
                    source_pdf=source.pdf_url,
                    source_post=source.post_url,
                    method="pdftotext_layout_case_distribution",
                )
            )
    return rows


def _confirmed_distribution_label(line: str) -> str:
    normalized = " ".join(line.strip().split())
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered.startswith(("province", "zone de santé", "ituri", "nord-kivu", "sud-kivu")):
        return ""
    if lowered.startswith(("sous-total", "total")):
        return ""
    if ("autres zs" in lowered and "non ventil" in lowered) or lowered.startswith("- autres zs"):
        return "NA"
    without_index = re.sub(r"^\d+\.\s+", "", normalized)
    return _find_known_table_label(without_index)


def _confirmed_distribution_values(line: str, label: str) -> dict[str, str]:
    normalized = " ".join(line.strip().split())
    if label == "NA":
        after = normalized
    else:
        match = re.search(rf"(?<!\w){re.escape(label)}(?!\w)", normalized, flags=re.I)
        if not match:
            return {}
        after = normalized[match.end():]
    tokens = re.findall(r"\b\d+\b", after)
    if len(tokens) < 2:
        return {}
    return {
        "cumulative_confirmed_cases": _normalize_count_token(tokens[0]),
        "cumulative_confirmed_deaths": _normalize_count_token(tokens[1]),
    }


def extract_table_ii_from_pdf(path: Path, source: ReportSource) -> list[ExtractedValue]:
    try:
        text = _pdf_text(path)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return []
    if len(_usable_text(text)) < TEXT_EXTRACTABLE_MIN_CHARS:
        return []
    return extract_table_ii(text, source)


def _table_ii_section(text: str) -> str:
    start = _case_distribution_table_start(text)
    if start < 0:
        return ""
    end_candidates = []
    for token in (
        "*Ces données",
        "Surveillance aux Points",
        "Points d’entrées",
        "Points d'entrée",
        "ACTIVITES REALISEES",
    ):
        pos = text.find(token, start + 40)
        if pos > start:
            end_candidates.append(pos)
    for match in re.finditer(r"(?m)^\s*Tableau\s+[IVXLCDM]+[.:]", text[start + 40:]):
        end_candidates.append(start + 40 + match.start())
    for match in re.finditer(r"(?m)^\s{0,2}\d+\.\s+[A-ZÉÈÀÙÂÊÎÔÛÇ]", text[start + 40:]):
        end_candidates.append(start + 40 + match.start())
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end]


def _case_distribution_table_start(text: str) -> int:
    starts = [m.start() for m in re.finditer(r"Répartition\s+des\s+cas", text, re.I)]
    for start in reversed(starts):
        window = text[start:start + 2500]
        compact_window = " ".join(window.split())
        compact_lower = compact_window.lower()
        if "zones de santé" not in compact_lower and "zone de santé" not in compact_lower:
            continue
        has_table_ii_counts = "nbre de cas" in compact_lower or "cas suspects" in compact_lower
        has_confirmed_distribution = "cas confirmés" in compact_lower and "décès confirmés" in compact_lower
        if not has_table_ii_counts and not has_confirmed_distribution:
            continue
        table_start = text.rfind("Tableau", 0, start)
        if 0 <= table_start and start - table_start < 250:
            return table_start
        return start
    return -1


def _extract_table_asof_date(section: str) -> date | None:
    french = re.search(r"\bau\s+(?P<value>\d{1,2}\s+\w+\s+2026)", section, re.I)
    if french:
        return _parse_french_date(french.group("value"))
    numeric = re.search(r"\bau\s+(?P<day>\d{1,2})\s*/\s*(?P<month>\d{1,2})\s*/\s*2026", section, re.I)
    if numeric:
        return date(2026, int(numeric.group("month")), int(numeric.group("day")))
    return None


def _table_label(line: str) -> str:
    if len(line) < 45:
        return ""
    label = line[35:62].strip()
    return " ".join(label.split())


def _skip_table_label(label: str) -> bool:
    lowered = label.lower()
    return (
        lowered in {"zones de santé", "sous total", "total"}
        or "echantillons" in lowered
        or "échantillons" in lowered
        or "provinces" in lowered
    )


def _canonical_table_label(label: str) -> str | None:
    if label == "NA":
        return "NA"
    for candidate in (label, label.title(), label.upper(), label.replace(" ", "-"), label.title().replace(" ", "-")):
        canonical = _to_canonical(candidate)
        if canonical is not None:
            return canonical
    # Some INSP tables omit hyphens that are present in the shapefile canonical
    # label, e.g. "Miti Murhesa" in the PDF vs "Miti-Murhesa" in the repo.
    return None


@functools.lru_cache(maxsize=1)
def _known_table_labels() -> tuple[str, ...]:
    labels: set[str] = set()
    for path in PROCESSED_BY_METRIC.values():
        processed_path = PROCESSED_DIR / path
        if not processed_path.exists():
            continue
        with processed_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                nom = (row.get("nom") or "").strip()
                if not nom or nom == "nom":
                    continue
                labels.add(nom)
                labels.add(nom.replace("-", " "))
    if ALIASES_CSV.exists():
        with ALIASES_CSV.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                observed = (row.get("observed_name") or "").strip()
                canonical = (row.get("canonical_nom") or "").strip()
                if observed and canonical and _canonical_table_label(observed):
                    labels.add(observed)
                    labels.add(observed.replace("-", " "))
    expanded = set(labels)
    expanded.add("NA")
    for label in labels:
        expanded.add(label.title())
        expanded.add(label.upper())
    return tuple(sorted(expanded, key=len, reverse=True))


def _find_known_table_label(line: str) -> str:
    normalized = " ".join(line.strip().split())
    if not normalized:
        return ""
    for label in _known_table_labels():
        pattern = rf"(?<!\w){re.escape(label)}(?!\w)"
        match = re.search(pattern, normalized, flags=re.I)
        if match:
            return match.group(0)
    return ""


def _assign_table_values_after_label(line: str, label: str) -> dict[str, str]:
    normalized = " ".join(line.strip().split())
    match = re.search(rf"(?<!\w){re.escape(label)}(?!\w)", normalized, flags=re.I)
    if not match:
        return {}
    after = normalized[match.end():]
    tokens = [token.replace("*", "") for token in re.findall(r"\bND\b|\bN\b|\d+\*{0,2}", after)]
    tokens = ["ND" if token == "N" else token for token in tokens]
    if len(tokens) < 3:
        return {}
    return {
        metric: value
        for metric, value in zip(TABLE_II_METRIC_ORDER, tokens[:len(TABLE_II_METRIC_ORDER)])
    }


def _assign_table_values(line: str) -> dict[str, str]:
    assigned: dict[str, str] = {}
    for match in re.finditer(r"\bND\b|\d+\*{0,2}", line):
        token = match.group(0).replace("*", "")
        start = match.start()
        anchor, metric = min(TABLE_II_METRIC_ANCHORS, key=lambda item: abs(item[0] - start))
        if abs(anchor - start) <= 8:
            assigned[metric] = token
    return assigned


def write_source_reports(path: Path, sources: Iterable[ReportSource]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "report_number",
        "title",
        "report_date",
        "publication_date",
        "post_published_at",
        "post_modified_at",
        "post_url",
        "pdf_url",
        "raw_path",
        "pdf_sha256",
        "pdf_bytes",
        "official_pdf_sha256",
        "official_pdf_bytes",
        "source_relation",
        "source_gate_status",
        "source_identity_status",
        "last_modified",
        "etag",
        "pdf_text_status",
        "text_extractable",
        "text_chars",
        "layout_status",
        "extraction_confidence",
        "headline_status",
        "table_ii_status",
        "national_values_status",
        "national_confirmed_cases",
        "national_confirmed_deaths",
        "national_confirmed_active",
        "national_suspected_cases",
        "national_suspected_deaths",
        "national_suspected_cases_under_investigation",
        "national_suspected_cases_in_isolation",
        "national_recovered",
        "national_patients_in_isolation",
        "national_contact_followup_rate",
        "draft_status",
        "blocking_reason",
        "revision_notes",
        "status",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for source in sources:
            row = {
                "report_number": f"{source.report_number:03d}",
                "title": source.title,
                "report_date": source.parsed.get("report_date", ""),
                "publication_date": source.parsed.get("publication_date", ""),
                "post_published_at": source.post_published_at,
                "post_modified_at": source.post_modified_at,
                "post_url": source.post_url,
                "pdf_url": source.pdf_url,
                "raw_path": source.raw_path,
                "pdf_sha256": source.pdf_sha256,
                "pdf_bytes": "" if source.pdf_bytes is None else str(source.pdf_bytes),
                "official_pdf_sha256": source.official_pdf_sha256,
                "official_pdf_bytes": (
                    "" if source.official_pdf_bytes is None else str(source.official_pdf_bytes)
                ),
                "source_relation": source.source_relation,
                "source_gate_status": source.parsed.get("source_gate_status") or _source_gate_status(source),
                "source_identity_status": source.parsed.get("source_identity_status") or _source_identity_status(source),
                "last_modified": source.last_modified,
                "etag": source.etag,
                "pdf_text_status": source.parsed.get("pdf_text_status", ""),
                "text_extractable": source.parsed.get("text_extractable", ""),
                "text_chars": source.parsed.get("text_chars", ""),
                "layout_status": source.parsed.get("layout_status", ""),
                "extraction_confidence": source.parsed.get("extraction_confidence", ""),
                "headline_status": source.parsed.get("headline_status", ""),
                "table_ii_status": source.parsed.get("table_ii_status", ""),
                "national_values_status": source.parsed.get("national_values_status", ""),
                "national_confirmed_cases": source.parsed.get("national_confirmed_cases", ""),
                "national_confirmed_deaths": source.parsed.get("national_confirmed_deaths", ""),
                "national_confirmed_active": source.parsed.get("national_confirmed_active", ""),
                "national_suspected_cases": source.parsed.get("national_suspected_cases", ""),
                "national_suspected_deaths": source.parsed.get("national_suspected_deaths", ""),
                "national_suspected_cases_under_investigation": source.parsed.get(
                    "national_suspected_cases_under_investigation", ""
                ),
                "national_suspected_cases_in_isolation": source.parsed.get(
                    "national_suspected_cases_in_isolation", ""
                ),
                "national_recovered": source.parsed.get("national_recovered", ""),
                "national_patients_in_isolation": source.parsed.get("national_patients_in_isolation", ""),
                "national_contact_followup_rate": source.parsed.get("national_contact_followup_rate", ""),
                "draft_status": source.parsed.get("draft_status", ""),
                "blocking_reason": source.parsed.get("blocking_reason", ""),
                "revision_notes": source.parsed.get("revision_notes", ""),
                "status": _manifest_status(source),
            }
            writer.writerow(row)


def _manifest_status(source: ReportSource) -> str:
    source_gate_status = source.parsed.get("source_gate_status") or _source_gate_status(source)
    if source_gate_status == "passed":
        return "official_verified"
    if source.status.startswith(("pdf_head_failed:", "pdf_download_failed:")):
        return source.status
    if source.status == "missing_pdf_url":
        return source.status
    return source_gate_status


def read_source_report_cache(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        cache: dict[int, dict[str, str]] = {}
        for row in rows:
            try:
                report_number = int(row.get("report_number", ""))
            except ValueError:
                continue
            cache[report_number] = dict(row)
        return cache


def write_extracted_values(path: Path, rows: Iterable[ExtractedValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "report_number",
        "report_date",
        "nom_raw",
        "nom",
        "metric",
        "value",
        "source_pdf",
        "source_post",
        "method",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "report_number": f"{row.report_number:03d}",
                "report_date": row.report_date,
                "nom_raw": row.nom_raw,
                "nom": row.nom,
                "metric": row.metric,
                "value": row.value,
                "source_pdf": row.source_pdf,
                "source_post": row.source_post,
                "method": row.method,
            })


def build_processed_draft_values(
    rows: Iterable[ExtractedValue],
    sources: Iterable[ReportSource],
) -> list[ProcessedDraftValue]:
    source_list = list(sources)
    source_by_report = {source.report_number: source for source in source_list}
    draft_values: list[ProcessedDraftValue] = []
    for row in rows:
        if row.method not in ACCEPTED_DRAFT_METHODS:
            continue
        source = source_by_report.get(row.report_number)
        if not _source_allows_drafts(source):
            continue
        canonical = _canonical_table_label(row.nom_raw)
        if canonical is None:
            continue
        draft_values.append(
            ProcessedDraftValue(
                metric=row.metric,
                nom=canonical,
                date=row.report_date,
                value=row.value,
                source_report_number=row.report_number,
                source_pdf=row.source_pdf,
                source_post=row.source_post,
                method=row.method,
                source_raw_path=source.raw_path if source else "",
            )
        )

    for source in source_list:
        if not _source_allows_drafts(source):
            continue
        report_date = source.parsed.get("report_date", "")
        if not report_date:
            continue
        for parsed_field, metric in NATIONAL_BY_PARSED_FIELD.items():
            value = source.parsed.get(parsed_field, "")
            if not value or value == "ND":
                continue
            draft_values.append(
                ProcessedDraftValue(
                    metric=metric,
                    nom="DRC",
                    date=report_date,
                    value=value,
                    source_report_number=source.report_number,
                    source_pdf=source.pdf_url,
                    source_post=source.post_url,
                    method="pdftotext_layout_headline",
                    source_raw_path=source.raw_path,
                )
            )

    return draft_values


def _source_allows_drafts(source: ReportSource | None) -> bool:
    if not _source_gate_passed(source):
        return False
    if source.parsed.get("source_identity_status", "").startswith("blocked_"):
        return False
    return source.parsed.get("draft_status") == "ready_for_review"


def write_processed_drafts(output_dir: Path, draft_values: Iterable[ProcessedDraftValue]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_metric: dict[str, dict[tuple[str, str], ProcessedDraftValue]] = {}
    for value in draft_values:
        if value.metric not in PROCESSED_DRAFT_BY_METRIC:
            continue
        by_metric.setdefault(value.metric, {})[(value.nom, _date_key(value.date))] = value

    current_paths = {
        output_dir / PROCESSED_DRAFT_BY_METRIC[metric]
        for metric in by_metric
    }
    for filename in set(PROCESSED_DRAFT_BY_METRIC.values()):
        stale_path = output_dir / filename
        if stale_path not in current_paths:
            stale_path.unlink(missing_ok=True)

    written: list[Path] = []
    for metric, indexed in sorted(by_metric.items()):
        path = output_dir / PROCESSED_DRAFT_BY_METRIC[metric]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["nom", "date", metric], lineterminator="\n")
            writer.writeheader()
            for value in sorted(indexed.values(), key=lambda item: (item.date, item.nom)):
                writer.writerow({"nom": value.nom, "date": value.date, metric: value.value})
        written.append(path)
    return written


def write_processed_candidates(processed_dir: Path, draft_values: Iterable[ProcessedDraftValue]) -> list[Path]:
    processed_dir.mkdir(parents=True, exist_ok=True)
    draft_list = list(draft_values)
    by_metric: dict[str, dict[tuple[str, str], ProcessedDraftValue]] = {}
    for value in draft_list:
        if value.metric not in PROCESSED_DRAFT_BY_METRIC:
            continue
        by_metric.setdefault(value.metric, {})[(_nom_key(value.nom), _date_key(value.date))] = value

    written: list[Path] = []
    for metric, indexed in sorted(by_metric.items()):
        path = processed_dir / PROCESSED_DRAFT_BY_METRIC[metric]
        rows: list[dict[str, str]] = []
        row_index: dict[tuple[str, str], int] = {}
        date_display_by_key: dict[str, str] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    nom = row.get("nom", "")
                    date_value = row.get("date", "")
                    if not nom or not date_value:
                        continue
                    date_key = _date_key(date_value)
                    row_index.setdefault((_to_canonical(nom) or nom, date_key), len(rows))
                    date_display_by_key.setdefault(date_key, date_value)
                    rows.append({
                        "nom": nom,
                        "date": date_value,
                        metric: row.get(metric, ""),
                    })
        new_rows: list[dict[str, str]] = []
        for value in indexed.values():
            key = (value.nom, _date_key(value.date))
            existing_index = row_index.get(key)
            if existing_index is not None:
                continue
            row_index[key] = len(rows)
            row = {
                "nom": value.nom,
                "date": date_display_by_key.get(_date_key(value.date), value.date),
                metric: value.value,
            }
            rows.append(row)
            new_rows.append(row)
        if not new_rows:
            continue
        fieldnames = ["nom", "date", metric]
        if path.exists():
            with path.open("a", newline="", encoding="utf-8") as f:
                if _needs_append_newline(path):
                    f.write("\n")
                writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
                for row in new_rows:
                    writer.writerow(row)
        else:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        written.append(path)
    return written


def _needs_append_newline(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as f:
        f.seek(-1, 2)
        return f.read(1) not in {b"\n", b"\r"}


def _date_key(value: str) -> str:
    clean = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", clean):
        return clean
    match = re.fullmatch(r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})", clean)
    if match:
        return (
            f"{match.group('year')}-"
            f"{int(match.group('month')):02d}-"
            f"{int(match.group('day')):02d}"
        )
    return clean


def _nom_key(value: str) -> str:
    return _to_canonical(value) or value


def write_processed_review(
    path: Path,
    draft_values: Iterable[ProcessedDraftValue],
    *,
    sources: Iterable[ReportSource] = (),
    processed_dir: Path = PROCESSED_DIR,
    candidate_mode: bool = False,
) -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "status",
        "processed_file",
        "metric",
        "nom",
        "date",
        "processed_value",
        "extracted_value",
        "source_report_number",
        "source_pdf",
        "source_post",
        "source_raw_path",
        "method",
        "draft_status",
        "blocking_reason",
    ]
    counts: dict[str, int] = {}
    indexes: dict[str, dict[tuple[str, str], str]] = {}
    by_key: dict[tuple[str, str, str], ProcessedDraftValue] = {}
    draft_list = list(draft_values)
    monotonic_issues = _cumulative_review_issues(processed_dir, draft_list)
    candidate_monotonic_issues = {
        (issue["metric"], issue["nom_key"], _date_key(issue["date"])): issue
        for issue in monotonic_issues
        if issue["source"] == "candidate"
    }
    for value in draft_list:
        by_key[(value.metric, _nom_key(value.nom), _date_key(value.date))] = value

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for value in sorted(by_key.values(), key=lambda item: (item.metric, item.date, item.nom)):
            processed_file = PROCESSED_DRAFT_BY_METRIC.get(value.metric, "")
            processed_value = ""
            if processed_file:
                if value.metric not in indexes:
                    processed_path = processed_dir / processed_file
                    indexes[value.metric] = (
                        _processed_index(processed_path, value.metric)
                        if processed_path.exists()
                        else {}
                    )
                processed_value = indexes[value.metric].get((value.nom, _date_key(value.date)), "")
            issue = candidate_monotonic_issues.get((value.metric, _nom_key(value.nom), _date_key(value.date)))
            blocking_reason = ""
            draft_status = ""
            if issue:
                status = "manual_review_required"
                blocking_reason = issue["blocking_reason"]
                draft_status = "manual_review_required"
            elif processed_value == "":
                status = "candidate_added" if candidate_mode else "missing_processed"
            elif processed_value == value.value:
                status = "match"
            else:
                status = "value_mismatch"
            counts[status] = counts.get(status, 0) + 1
            writer.writerow({
                "status": status,
                "processed_file": processed_file,
                "metric": value.metric,
                "nom": value.nom,
                "date": value.date,
                "processed_value": processed_value,
                "extracted_value": value.value,
                "source_report_number": f"{value.source_report_number:03d}",
                "source_pdf": value.source_pdf,
                "source_post": value.source_post,
                "source_raw_path": value.source_raw_path,
                "method": value.method,
                "draft_status": draft_status,
                "blocking_reason": blocking_reason,
            })
        for source in sorted(sources, key=lambda item: item.report_number):
            reason = source.parsed.get("blocking_reason", "")
            draft_status = source.parsed.get("draft_status", "")
            if not reason and draft_status != "blocked":
                continue
            status = "blocked" if draft_status == "blocked" else "manual_review_required"
            counts[status] = counts.get(status, 0) + 1
            writer.writerow({
                "status": status,
                "processed_file": "",
                "metric": "",
                "nom": "",
                "date": source.parsed.get("report_date", ""),
                "processed_value": "",
                "extracted_value": "",
                "source_report_number": f"{source.report_number:03d}",
                "source_pdf": source.pdf_url,
                "source_post": source.post_url,
                "source_raw_path": source.raw_path,
                "method": "manual_review_required",
                "draft_status": draft_status,
                "blocking_reason": reason,
            })
        for issue in monotonic_issues:
            if issue["source"] == "candidate":
                continue
            counts["manual_review_required"] = counts.get("manual_review_required", 0) + 1
            writer.writerow({
                "status": "manual_review_required",
                "processed_file": issue["processed_file"],
                "metric": issue["metric"],
                "nom": issue["nom"],
                "date": issue["date"],
                "processed_value": issue["processed_value"],
                "extracted_value": "",
                "source_report_number": "",
                "source_pdf": "",
                "source_post": "",
                "source_raw_path": "",
                "method": "processed_monotonicity_check",
                "draft_status": "manual_review_required",
                "blocking_reason": issue["blocking_reason"],
            })
    return counts


def _cumulative_review_issues(
    processed_dir: Path,
    draft_values: Iterable[ProcessedDraftValue] = (),
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    draft_list = list(draft_values)
    for metric in CUMULATIVE_REVIEW_METRICS:
        filename = PROCESSED_DRAFT_BY_METRIC[metric]
        path = processed_dir / filename
        by_nom: dict[str, list[tuple[str, int, str, str]]] = {}
        existing_keys: set[tuple[str, str]] = set()
        if path.exists():
            with path.open(newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    raw_value = row.get(metric, "")
                    value = _count_or_none(raw_value)
                    if value is None:
                        continue
                    nom = row.get("nom", "")
                    if not nom:
                        continue
                    date_key = _date_key(row.get("date", ""))
                    nom_key = _nom_key(nom)
                    existing_keys.add((nom_key, date_key))
                    by_nom.setdefault(nom_key, []).append((date_key, value, "processed", nom))
        for draft in draft_list:
            if draft.metric != metric:
                continue
            value = _count_or_none(draft.value)
            if value is None:
                continue
            date_key = _date_key(draft.date)
            nom_key = _nom_key(draft.nom)
            if (nom_key, date_key) in existing_keys:
                continue
            by_nom.setdefault(nom_key, []).append((date_key, value, "candidate", draft.nom))
        for nom_key, rows in by_nom.items():
            sorted_rows = sorted(rows)
            max_date = ""
            max_value: int | None = None
            for index, (row_date, value, source, display_nom) in enumerate(sorted_rows):
                future_processed_drop = next(
                    (
                        (future_date, future_value)
                        for future_date, future_value, future_source, _ in sorted_rows[index + 1:]
                        if future_source == "processed" and future_value < value
                    ),
                    None,
                )
                if source == "candidate" and future_processed_drop is not None:
                    future_date, future_value = future_processed_drop
                    issues.append({
                        "processed_file": filename,
                        "metric": metric,
                        "nom": display_nom,
                        "nom_key": nom_key,
                        "date": row_date,
                        "processed_value": str(value),
                        "source": "candidate",
                        "blocking_reason": (
                            "cumulative_decrease:"
                            f"{row_date}={value}>{future_date}={future_value}"
                        ),
                    })
                    continue
                if max_value is not None and value < max_value:
                    issues.append({
                        "processed_file": filename,
                        "metric": metric,
                        "nom": display_nom,
                        "nom_key": nom_key,
                        "date": row_date,
                        "processed_value": str(value),
                        "source": source,
                        "blocking_reason": (
                            "cumulative_decrease:"
                            f"{max_date}={max_value}>{row_date}={value}"
                        ),
                    })
                    if source == "candidate":
                        continue
                    continue
                max_date = row_date
                max_value = value
    return issues


def _count_or_none(value: str) -> int | None:
    clean = value.strip()
    if not clean or clean.upper() == "ND":
        return None
    try:
        return _parse_int(clean)
    except ValueError:
        return None


def write_source_review_queue(path: Path, sources: Iterable[ReportSource]) -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "review_status",
        "report_number",
        "report_date",
        "post_published_at",
        "post_modified_at",
        "pdf_last_modified",
        "source_raw_path",
        "source_pdf",
        "source_post",
        "source_gate_status",
        "source_identity_status",
        "source_relation",
        "layout_status",
        "extraction_confidence",
        "headline_status",
        "table_ii_status",
        "national_values_status",
        "draft_status",
        "blocking_reason",
        "review_action",
    ]
    counts: dict[str, int] = {}
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for source in sorted(sources, key=lambda item: item.report_number):
            source_gate_status = source.parsed.get("source_gate_status") or _source_gate_status(source)
            source_identity_status = source.parsed.get("source_identity_status") or _source_identity_status(source)
            draft_status = source.parsed.get("draft_status", "")
            reason = source.parsed.get("blocking_reason", "")
            if source_gate_status == "passed" and draft_status != "blocked" and not reason:
                continue
            review_status = "blocked" if source_gate_status != "passed" or draft_status == "blocked" else "manual_review_required"
            counts[review_status] = counts.get(review_status, 0) + 1
            writer.writerow({
                "review_status": review_status,
                "report_number": f"{source.report_number:03d}",
                "report_date": source.parsed.get("report_date", ""),
                "post_published_at": source.post_published_at,
                "post_modified_at": source.post_modified_at,
                "pdf_last_modified": source.last_modified,
                "source_raw_path": source.raw_path,
                "source_pdf": source.pdf_url,
                "source_post": source.post_url,
                "source_gate_status": source_gate_status,
                "source_identity_status": source_identity_status,
                "source_relation": source.source_relation,
                "layout_status": source.parsed.get("layout_status", ""),
                "extraction_confidence": source.parsed.get("extraction_confidence", ""),
                "headline_status": source.parsed.get("headline_status", ""),
                "table_ii_status": source.parsed.get("table_ii_status", ""),
                "national_values_status": source.parsed.get("national_values_status", ""),
                "draft_status": draft_status,
                "blocking_reason": reason,
                "review_action": _source_review_action(source, review_status, reason),
            })
    return counts


def _source_review_action(source: ReportSource, review_status: str, reason: str) -> str:
    raw = source.raw_path or "raw PDF"
    if review_status == "blocked":
        return f"Open {raw}; automated drafts are blocked until this source/layout issue is resolved: {reason}"
    return f"Open {raw}; compare the listed partial/ambiguous field(s) against the PDF: {reason}"


def write_review_summary(
    path: Path,
    sources: Iterable[ReportSource],
    *,
    source_review_counts: dict[str, int],
    processed_review_counts: dict[str, int] | None = None,
    extracted_count: int = 0,
    draft_file_count: int = 0,
    candidate_file_count: int = 0,
    source_review_queue: Path = DEFAULT_SOURCE_REVIEW_QUEUE,
    processed_review: Path = DEFAULT_REVIEW_DIFFS,
    processed_draft_dir: Path = DEFAULT_PROCESSED_DRAFT_DIR,
) -> None:
    source_list = list(sources)
    processed_review_counts = processed_review_counts or {}
    review_items = [
        source for source in source_list
        if (
            (source.parsed.get("source_gate_status") or _source_gate_status(source)) != "passed"
            or source.parsed.get("draft_status") == "blocked"
            or bool(source.parsed.get("blocking_reason", ""))
        )
    ]
    ready_reports = [
        source for source in source_list
        if (
            (source.parsed.get("source_gate_status") or _source_gate_status(source)) == "passed"
            and source.parsed.get("draft_status") == "ready_for_review"
            and not source.parsed.get("blocking_reason", "")
        )
    ]

    lines = [
        "# INSP SitRep Ingest Review",
        "",
        "This packet is generated from official INSP source sync plus advisory public-PDF extraction.",
        "",
        "## First Checks",
        f"- Source review queue: `{_display_path(source_review_queue)}`",
        f"- Processed draft review: `{_display_path(processed_review)}`",
        f"- Processed draft CSVs: `{_display_path(processed_draft_dir)}`",
    ]
    if candidate_file_count:
        lines.append(f"- Processed candidate CSVs: `{_display_path(PROCESSED_DIR)}`")
    lines.extend([
        "",
        "## Run Summary",
        f"- Reports discovered: {len(source_list)}",
        f"- Table II values extracted: {extracted_count}",
        f"- Processed draft files written: {draft_file_count}",
        f"- Processed candidate files written: {candidate_file_count}",
        f"- Source manifest statuses: {_format_counts(_counts_by(source_list, _manifest_status))}",
        f"- Source gate statuses: {_format_counts(_counts_by(source_list, lambda source: source.parsed.get('source_gate_status') or _source_gate_status(source)))}",
        f"- Layout statuses: {_format_counts(_counts_by(source_list, lambda source: source.parsed.get('layout_status', 'unknown')))}",
        f"- Source review queue: {_format_counts(source_review_counts)}",
        f"- Processed draft review: {_format_counts(processed_review_counts)}",
        "",
        "## INSP Source Timing",
        "| Report | Report Date | INSP Post Published | INSP Post Modified | PDF Last-Modified | Layout | Blocker |",
        "|---|---|---|---|---|---|---|",
    ])
    for source in sorted(source_list, key=lambda item: item.report_number):
        lines.append(
            "| "
            f"{source.report_number:03d} | "
            f"{source.parsed.get('report_date', '')} | "
            f"{_md_cell(source.post_published_at)} | "
            f"{_md_cell(source.post_modified_at)} | "
            f"{_md_cell(source.last_modified)} | "
            f"{_md_cell(source.parsed.get('layout_status', ''))} | "
            f"{_md_cell(source.parsed.get('blocking_reason', ''))} |"
        )
    lines.extend([
        "",
        "## Reviewer Actions",
        "- Source rows are report-level gates. Processed candidate rows are Table II field-level drafts with accepted evidence methods.",
        "- A report can need manual review for one field while still producing candidate rows for other fields with stronger evidence.",
        "- National headline values are recorded once in `source_reports.csv`; this helper does not expand new national totals across every zone.",
    ])
    if source_review_counts.get("blocked", 0):
        lines.append("- Resolve blocked source/layout rows before trusting automated drafts for those reports.")
    if source_review_counts.get("manual_review_required", 0):
        lines.append("- Review manual rows by opening `source_raw_path` and comparing only the listed ambiguous field(s).")
    if processed_review_counts.get("value_mismatch", 0):
        lines.append("- Inspect value mismatches before accepting processed candidate rows.")
    if processed_review_counts.get("candidate_added", 0):
        lines.append("- Review `candidate_added` rows as new processed CSV rows proposed by this run.")
    if candidate_file_count:
        lines.append("- Review changed `processed/*.csv` rows in the draft PR against the official PDFs.")
        lines.append("- Treat `processed_draft_review.csv` as the pre-candidate comparison against prior processed files.")
    elif processed_review_counts.get("missing_processed", 0):
        lines.append("- Use processed draft CSVs as candidate rows for missing processed values after review.")
    if not source_review_counts and not processed_review_counts:
        lines.append("- No source or processed review rows were generated.")

    lines.extend(["", "## Reports Needing Review"])
    if review_items:
        lines.extend([
            "| Report | Date | Status | Reason | Local PDF |",
            "|---|---|---|---|---|",
        ])
        for source in sorted(review_items, key=lambda item: item.report_number):
            source_gate_status = source.parsed.get("source_gate_status") or _source_gate_status(source)
            draft_status = source.parsed.get("draft_status", "")
            status = "blocked" if source_gate_status != "passed" or draft_status == "blocked" else "manual_review_required"
            reason = source.parsed.get("blocking_reason", "")
            lines.append(
                "| "
                f"{source.report_number:03d} | "
                f"{source.parsed.get('report_date', '')} | "
                f"{status} | "
                f"{_md_cell(reason)} | "
                f"`{source.raw_path}` |"
            )
    else:
        lines.append("No report-level source or layout blockers.")

    lines.extend(["", "## High-Confidence Draft Reports"])
    if ready_reports:
        lines.append(", ".join(f"{source.report_number:03d}" for source in ready_reports))
    else:
        lines.append("None.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _counts_by(items: Iterable[ReportSource], key_fn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = key_fn(item) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}: {counts[key]}" for key in sorted(counts))


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|") if value else ""


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def compare_processed(rows: Iterable[ExtractedValue], processed_dir: Path = PROCESSED_DIR) -> list[str]:
    indexes: dict[str, dict[tuple[str, str], str]] = {}
    diffs: list[str] = []
    for row in rows:
        canonical = _canonical_table_label(row.nom_raw)
        if canonical is None:
            continue
        path = processed_dir / PROCESSED_BY_METRIC[row.metric]
        if row.metric not in indexes:
            indexes[row.metric] = _processed_index(path, row.metric)
        existing = indexes[row.metric].get((canonical, _date_key(row.report_date)))
        if existing is None:
            diffs.append(
                f"missing processed row: {path.name} {canonical} "
                f"{row.report_date} expected={row.value}"
            )
        elif existing != row.value:
            diffs.append(
                f"value mismatch: {path.name} {canonical} {row.report_date} "
                f"processed={existing} extracted={row.value}"
            )
    return diffs


def _processed_index(path: Path, metric: str) -> dict[tuple[str, str], str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {
            (_to_canonical(row["nom"]) or row["nom"], _date_key(row["date"])): row[metric]
            for row in reader
            if row.get("nom") and row.get("date")
        }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--download-missing", action="store_true", help="Download missing PDFs into raw/")
    parser.add_argument(
        "--sync-official-pdfs",
        action="store_true",
        help="Download official INSP PDFs into raw/, replacing stale or derived local copies",
    )
    parser.add_argument(
        "--verify-official-pdfs",
        action="store_true",
        help="Download official INSP PDFs to a temp file for hash comparison without changing raw/",
    )
    parser.add_argument("--parse-pdfs", action="store_true", help="Extract headline facts from local PDFs")
    parser.add_argument("--extract-table-ii", action="store_true", help="Extract Table II rows from local PDFs")
    parser.add_argument("--compare-processed", action="store_true", help="Compare extracted Table II values to processed CSVs")
    parser.add_argument(
        "--check-for-updates",
        action="store_true",
        help=(
            "Check official source metadata against source_reports.csv and exit "
            f"{UPDATE_NEEDED_EXIT_CODE} when a new or changed source should be ingested"
        ),
    )
    parser.add_argument(
        "--write-processed-drafts",
        action="store_true",
        help="Write extracted values as processed-contract draft CSVs under extracted/",
    )
    parser.add_argument(
        "--write-processed-candidates",
        action="store_true",
        help="Merge extracted processed-contract values into processed/ as draft PR candidate changes",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit non-zero when --compare-processed finds differences",
    )
    parser.add_argument("--write-source-reports", type=Path, default=DEFAULT_SOURCE_REPORTS)
    parser.add_argument("--write-extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--write-processed-draft-dir", type=Path, default=DEFAULT_PROCESSED_DRAFT_DIR)
    parser.add_argument("--write-review-diffs", type=Path, default=DEFAULT_REVIEW_DIFFS)
    parser.add_argument("--write-source-review-queue", type=Path, default=DEFAULT_SOURCE_REVIEW_QUEUE)
    parser.add_argument("--write-review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--min-report-number",
        type=int,
        default=None,
        help="Only process SitRep report numbers greater than or equal to this value",
    )
    parser.add_argument(
        "--max-report-number",
        type=int,
        default=None,
        help="Only process SitRep report numbers less than or equal to this value",
    )
    parser.add_argument(
        "--allow-insecure-tls",
        action="store_true",
        help="Disable TLS certificate verification for local trust-store debugging only",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    needs_processed_drafts = args.write_processed_drafts or args.write_processed_candidates
    needs_table_extraction = args.extract_table_ii or args.compare_processed or needs_processed_drafts
    verify_for_evidence = needs_table_extraction and not args.sync_official_pdfs
    exit_code = 0
    source_report_cache = read_source_report_cache(args.write_source_reports)
    sources = discover_sources(limit=args.limit, allow_insecure_tls=args.allow_insecure_tls)
    sources = filter_sources_by_report_number(
        sources,
        min_report_number=args.min_report_number,
        max_report_number=args.max_report_number,
    )
    sources = enrich_pdf_metadata(
        sources,
        download_missing=args.download_missing,
        sync_official_pdfs=args.sync_official_pdfs,
        verify_official_pdfs=args.verify_official_pdfs or verify_for_evidence,
        parse_pdfs=args.parse_pdfs or needs_table_extraction,
        allow_insecure_tls=args.allow_insecure_tls,
        source_report_cache=source_report_cache,
    )
    if args.check_for_updates:
        updates = source_update_report(sources, source_report_cache)
        if not updates:
            print("No new or changed official INSP SitRep sources found.")
            return 0
        print(f"Found {len(updates)} new or changed official INSP SitRep source(s):")
        for report_number in sorted(updates):
            print(f"  - {report_number:03d}: {', '.join(updates[report_number])}")
        return UPDATE_NEEDED_EXIT_CODE

    write_source_reports(args.write_source_reports, sources)
    source_review_counts = write_source_review_queue(args.write_source_review_queue, sources)

    extracted: list[ExtractedValue] = []
    if needs_table_extraction:
        for source in sources:
            raw_path = REPO_ROOT / source.raw_path
            if raw_path.exists() and _source_gate_passed(source):
                extracted.extend(extract_table_ii_from_pdf(raw_path, source))
        write_extracted_values(args.write_extracted_dir / "table_ii_values.csv", extracted)

    print(f"Discovered {len(sources)} INSP SitRep source(s).")
    print(f"Wrote {_display_path(args.write_source_reports)}")
    print(f"Wrote source review queue to {_display_path(args.write_source_review_queue)}.")
    print(f"Source review queue counts: {source_review_counts}")
    if extracted:
        print(f"Extracted {len(extracted)} Table II value(s).")
    review_counts: dict[str, int] = {}
    written: list[Path] = []
    candidate_written: list[Path] = []
    draft_target = args.write_processed_draft_dir
    if args.compare_processed:
        diffs = compare_processed(extracted)
        if diffs:
            print(f"Processed comparison found {len(diffs)} difference(s):")
            for diff in diffs[:50]:
                print(f"  - {diff}")
            if args.fail_on_diff:
                exit_code = 1
        else:
            print("Processed comparison found no differences.")
    if needs_processed_drafts:
        draft_values = build_processed_draft_values(extracted, sources)
        review_counts = write_processed_review(
            args.write_review_diffs,
            draft_values,
            sources=sources,
            candidate_mode=args.write_processed_candidates,
        )
        written = write_processed_drafts(args.write_processed_draft_dir, draft_values)
        if args.write_processed_candidates:
            candidate_written = write_processed_candidates(PROCESSED_DIR, draft_values)
            print(
                f"Wrote {len(candidate_written)} processed candidate file(s) "
                f"to {_display_path(PROCESSED_DIR)}."
            )
        print(f"Wrote {len(written)} processed draft file(s) to {_display_path(draft_target)}.")
        print(f"Wrote processed draft review to {_display_path(args.write_review_diffs)}.")
        print(f"Processed draft review counts: {review_counts}")
    write_review_summary(
        args.write_review_summary,
        sources,
        source_review_counts=source_review_counts,
        processed_review_counts=review_counts,
        extracted_count=len(extracted),
        draft_file_count=len(written),
        candidate_file_count=len(candidate_written),
        source_review_queue=args.write_source_review_queue,
        processed_review=args.write_review_diffs,
        processed_draft_dir=draft_target,
    )
    print(f"Wrote review summary to {_display_path(args.write_review_summary)}.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
