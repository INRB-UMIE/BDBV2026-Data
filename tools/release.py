"""`python -m tools.release` — archive previous build, rebuild, prompt for
description, update README.

This module owns all I/O (subprocess, network, $EDITOR). Pure helpers live in
tools.lib.release.

Run from repo root:
    python -m tools.release
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.lib.release import (
    build_tag,
    pack_archive,
    render_editor_template,
    rewrite_readme,
    strip_editor_comments,
)


REPO_ROOT = Path.cwd()
QA_LOG = REPO_ROOT / "qa" / "qa_log.csv"
MATRIX_LOG = REPO_ROOT / "qa" / "matrix_log.csv"
BUILD_DIR = REPO_ROOT / "build"
MANIFEST = BUILD_DIR / "manifest.json"
DESCRIPTION = BUILD_DIR / "DESCRIPTION.md"
README = REPO_ROOT / "README.md"
DIST_DIR = REPO_ROOT / "dist"

ALLOWLIST_PREFIXES = ("build/", "qa/qa_log.csv", "qa/matrix_log.csv", "README.md", "dist/")


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _preflight() -> int:
    if not QA_LOG.exists():
        _eprint(f"qa log not found at {QA_LOG}; run `python -m tools.qa` first.")
        return 2

    with QA_LOG.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "fail":
                _eprint(
                    "qa log contains failures — resolve them and re-run "
                    "`python -m tools.qa` before releasing."
                )
                return 2

    if shutil.which("gh") is None:
        _eprint(
            "gh CLI not found. Install from https://cli.github.com/ and run `gh auth login`."
        )
        return 2

    dirty = _git_dirty_paths()
    unrelated = [p for p in dirty if not any(p.startswith(pre) for pre in ALLOWLIST_PREFIXES)]
    if unrelated:
        _eprint(
            "working tree has unrelated uncommitted changes; commit or stash them first:\n"
            + "\n".join(f"  {p}" for p in unrelated)
        )
        return 2

    return 0


def _git_dirty_paths() -> list[str]:
    """Paths reported by `git status --porcelain` (no status code prefix)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        path = line[3:].split(" -> ", 1)[-1].strip()
        if path:
            paths.append(path)
    return paths


def _archive_previous_build() -> tuple[str, str] | None:
    """Pack the current build/ into dist/<tag>.tar.gz and create a GitHub Release.

    Returns (tag, release_url) on success, or None if archiving was skipped
    (no prior DESCRIPTION.md exists — first ever release).
    """
    if not DESCRIPTION.exists():
        _eprint("no build/DESCRIPTION.md found — skipping archive (first-ever release).")
        return None

    manifest = json.loads(MANIFEST.read_text())
    tag = build_tag(manifest["built_at"], manifest["commit"])

    view = subprocess.run(
        ["gh", "release", "view", tag],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if view.returncode == 0:
        _eprint(f"GitHub release {tag} already exists; did a previous rebuild fail?")
        sys.exit(2)

    out_path = DIST_DIR / f"{tag}.tar.gz"
    members: list[tuple[Path, str]] = [
        (BUILD_DIR / "drc_health_zones.geojson", "build/drc_health_zones.geojson"),
        (BUILD_DIR / "long", "build/long"),
        (BUILD_DIR / "manifest.json", "build/manifest.json"),
        (BUILD_DIR / "DESCRIPTION.md", "build/DESCRIPTION.md"),
        (QA_LOG, "qa/qa_log.csv"),
        (MATRIX_LOG, "qa/matrix_log.csv"),
    ]
    pack_archive(members, out_path)

    create = subprocess.run(
        [
            "gh", "release", "create", tag,
            str(out_path),
            "--title", tag,
            "--notes-file", str(DESCRIPTION),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if create.returncode != 0:
        _eprint(f"`gh release create` failed:\n{create.stderr}")
        sys.exit(2)

    url_lines = [ln for ln in create.stdout.strip().splitlines() if ln.strip()]
    url = url_lines[-1] if url_lines else ""
    _eprint(f"✓ Archived previous build as {tag} → {url}")
    return tag, url


def _prompt_description() -> str:
    editor = os.environ.get("EDITOR", "vi")
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
            f.write(render_editor_template())
            tmp_path = Path(f.name)
        subprocess.run([editor, str(tmp_path)], check=True)
        raw = tmp_path.read_text()
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    body = strip_editor_comments(raw)
    if not body:
        _eprint("description is required (empty after stripping comments); aborting.")
        sys.exit(2)
    return body


def _format_human_date(iso_ts: str) -> str:
    """Render an ISO 8601 timestamp as e.g. '21 May 2026, 10:00 (UTC)'."""
    parsed = dt.datetime.fromisoformat(iso_ts)
    if parsed.tzinfo:
        tzname = parsed.tzname() or "UTC"
        return parsed.strftime(f"%-d %B %Y, %H:%M ({tzname})")
    return parsed.strftime("%-d %B %Y, %H:%M")


def _update_readme(archived: tuple[str, str] | None, archived_summary: str | None) -> None:
    manifest = json.loads(MANIFEST.read_text())
    built_at = manifest["built_at"]
    short_sha = manifest["commit"]
    current_date = built_at.split("T", 1)[0]
    human_ts = _format_human_date(built_at)

    last_build_line = f"Last successful build: **{human_ts}** (commit `{short_sha}`)."
    whats_new = DESCRIPTION.read_text().rstrip()

    if archived and archived_summary:
        tag, url = archived
        archived_date = tag.split("-", 1)[1].rsplit("-", 1)[0]
        past_release_row = (
            f"| {tag} | {archived_date} | {archived_summary} | [release]({url}) |"
        )
    else:
        past_release_row = ""

    readme = README.read_text()
    readme = rewrite_readme(
        readme,
        last_build_line=last_build_line,
        current_build_date=current_date,
        whats_new=whats_new,
        past_release_row=past_release_row,
    )
    README.write_text(readme, encoding="utf-8")
    _eprint("✓ Updated README.md")


def main() -> int:
    parser = argparse.ArgumentParser(prog="tools.release")
    parser.parse_args()

    rc = _preflight()
    if rc != 0:
        return rc

    archived_summary: str | None = None
    if DESCRIPTION.exists():
        archived_summary = DESCRIPTION.read_text().strip().splitlines()[0]
    archived = _archive_previous_build()

    from tools import build_geojson as _bg
    rc = _bg.main()
    if rc != 0:
        _eprint(
            "rebuild failed AFTER archive was published. The release stands "
            "and accurately describes the old build; fix and re-run."
        )
        return rc
    _eprint("✓ Rebuilt build/")

    description = _prompt_description()
    DESCRIPTION.write_text(description + "\n", encoding="utf-8")
    _eprint("✓ Wrote build/DESCRIPTION.md")

    _update_readme(archived, archived_summary)

    _eprint("")
    _eprint("Next: review the changes, then")
    _eprint("  git add build/ qa/qa_log.csv qa/matrix_log.csv README.md")
    _eprint("  git commit -m \"New build YYYY-MM-DD\"")
    _eprint("  git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
