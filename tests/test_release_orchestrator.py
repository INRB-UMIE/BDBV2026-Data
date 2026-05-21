"""Integration tests for the tools.release orchestrator.

Stubs `gh` (via PATH manipulation) and `$EDITOR` (env var pointing at a
script) and fakes `tools.build_geojson` via PYTHONPATH so the test exercises
the real orchestrator end-to-end against a tmp directory.
"""

import json
import os
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------- helpers ----------

README_TEMPLATE = (
    "# Header\n\n"
    "Last successful build: **OLD** (commit `oldsha`).\n\n"
    "# Current build (2026-01-01)\n\n"
    "prose\n\n"
    "<!-- whats-new:start -->\n"
    "old description\n"
    "<!-- whats-new:end -->\n\n"
    "## Past releases\n\n"
    "<!-- past-releases:start -->\n"
    "| Tag | Date | Summary | Download |\n"
    "|-----|------|---------|----------|\n"
    "<!-- past-releases:end -->\n\n"
    "# Repository layout\n"
)


def _make_stub(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _seed_repo(tmp: Path, *, with_description: bool = True) -> None:
    """Lay down the minimum file tree the orchestrator inspects."""
    (tmp / "build").mkdir()
    (tmp / "build" / "long").mkdir()
    (tmp / "build" / "drc_health_zones.geojson").write_text(
        '{"type":"FeatureCollection","features":[]}'
    )
    (tmp / "build" / "manifest.json").write_text(json.dumps({
        "shapefile": "data/shapefiles/DRC_Health_zones.shp",
        "n_features": 0,
        "built_at": "2026-05-20T12:00:00+00:00",
        "commit": "abc1234",
        "datasets": [],
    }))
    if with_description:
        (tmp / "build" / "DESCRIPTION.md").write_text("Previous summary line.\n\nMore detail.\n")
    (tmp / "qa").mkdir()
    (tmp / "qa" / "qa_log.csv").write_text("dataset,type,file,status\nfoo,vector,foo.csv,pass\n")
    (tmp / "qa" / "matrix_log.csv").write_text("dataset,file\n")
    (tmp / "README.md").write_text(README_TEMPLATE)
    (tmp / ".gitignore").write_text("bin/\nfake_tools/\ngh.log\ndist/\n")


def _init_git(tmp: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp,
        check=True,
    )


def _install_stubs(tmp: Path, *, editor_body: str, gh_body: str | None = None) -> tuple[Path, Path]:
    """Drop fake `gh` and `$EDITOR` scripts under tmp/bin. Returns (bin_dir, gh_log)."""
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    gh_log = tmp / "gh.log"
    default_gh = (
        f"""#!/usr/bin/env bash
echo "$@" >> {gh_log}
if [ "$1" = "release" ] && [ "$2" = "view" ]; then exit 1; fi
if [ "$1" = "release" ] && [ "$2" = "create" ]; then
  echo "https://github.com/example/repo/releases/tag/$3"
fi
exit 0
"""
    )
    _make_stub(bin_dir / "gh", gh_body or default_gh)
    editor = bin_dir / "fake-editor"
    _make_stub(editor, editor_body)
    return bin_dir, gh_log


FAKE_BUILD_BOOTSTRAP = """
import json, pathlib, sys, types
fake = types.ModuleType('tools.build_geojson')
def _main(built_at={built_at!r}, commit={commit!r}):
    p = pathlib.Path('build/manifest.json')
    m = json.loads(p.read_text())
    m['built_at'] = built_at
    m['commit'] = commit
    p.write_text(json.dumps(m))
    return 0
fake.main = _main
import tools  # real package
sys.modules['tools.build_geojson'] = fake
import tools.release as _r
sys.exit(_r.main())
"""


def _run_release(
    tmp: Path,
    *,
    bin_dir: Path,
    editor: Path,
    fake_build: bool = True,
    built_at: str = "2026-05-22T10:00:00+00:00",
    commit: str = "newsha1",
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "EDITOR": str(editor),
        "PYTHONPATH": str(REPO_ROOT),
    }
    if fake_build:
        bootstrap = FAKE_BUILD_BOOTSTRAP.format(built_at=built_at, commit=commit)
        cmd = [sys.executable, "-c", bootstrap]
    else:
        cmd = [sys.executable, "-m", "tools.release"]
    return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, env=env)


# ---------- preflight ----------

def test_preflight_fails_when_qa_log_missing(tmp_path):
    _seed_repo(tmp_path)
    (tmp_path / "qa" / "qa_log.csv").unlink()

    result = subprocess.run(
        [sys.executable, "-m", "tools.release"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode != 0
    assert "qa" in result.stderr.lower()


def test_preflight_fails_when_qa_log_has_failures(tmp_path):
    _seed_repo(tmp_path)
    (tmp_path / "qa" / "qa_log.csv").write_text(
        "dataset,type,file,status\nfoo,vector,foo.csv,fail\n"
    )

    result = subprocess.run(
        [sys.executable, "-m", "tools.release"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode != 0
    assert "fail" in result.stderr.lower()


def test_preflight_fails_when_gh_missing(tmp_path):
    _seed_repo(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "tools.release"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            "PATH": "/nonexistent-bin",
            "PYTHONPATH": str(REPO_ROOT),
            "HOME": str(tmp_path),
        },
    )
    assert result.returncode != 0
    assert "gh" in result.stderr.lower()


def test_preflight_fails_on_unrelated_dirty_paths(tmp_path):
    _seed_repo(tmp_path)
    _init_git(tmp_path)
    bin_dir, _ = _install_stubs(tmp_path, editor_body="#!/usr/bin/env bash\necho x > \"$1\"\n")
    (tmp_path / "unrelated.txt").write_text("dirty")

    result = subprocess.run(
        [sys.executable, "-m", "tools.release"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
            "PYTHONPATH": str(REPO_ROOT),
        },
    )
    assert result.returncode != 0
    assert "unrelated" in result.stderr.lower() or "dirty" in result.stderr.lower()


# ---------- happy path ----------

def test_full_release_end_to_end(tmp_path):
    """One pass through preflight → archive → rebuild → editor → README rewrite."""
    _seed_repo(tmp_path)
    _init_git(tmp_path)
    editor_body = (
        "#!/usr/bin/env bash\n"
        "cat > \"$1\" <<EOF\n"
        "# this comment must be stripped\n"
        "Updated ACLED and added new Flowminder month.\n"
        "\n"
        "Motivated by sitrep refresh.\n"
        "EOF\n"
    )
    bin_dir, gh_log = _install_stubs(tmp_path, editor_body=editor_body)
    result = _run_release(
        tmp_path,
        bin_dir=bin_dir,
        editor=bin_dir / "fake-editor",
    )
    assert result.returncode == 0, result.stderr

    # gh was called with the right tag (derived from the OLD manifest).
    log = gh_log.read_text()
    assert "release view build-2026-05-20-abc1234" in log
    assert "release create build-2026-05-20-abc1234" in log

    # Tarball exists and contains the expected members.
    tarballs = list((tmp_path / "dist").glob("build-2026-05-20-abc1234.tar.gz"))
    assert tarballs, "expected one tarball under dist/"
    with tarfile.open(tarballs[0], "r:gz") as tf:
        names = set(tf.getnames())
    assert "build/drc_health_zones.geojson" in names
    assert "build/manifest.json" in names
    assert "build/DESCRIPTION.md" in names
    assert "qa/qa_log.csv" in names
    assert "qa/matrix_log.csv" in names

    # New DESCRIPTION.md reflects the editor input minus the comment.
    desc = (tmp_path / "build" / "DESCRIPTION.md").read_text()
    assert desc.startswith("Updated ACLED")
    assert "# this comment" not in desc

    # README rewritten: new current-build heading + commit + whats-new + past row.
    readme = (tmp_path / "README.md").read_text()
    assert "# Current build (2026-05-22)" in readme
    assert "newsha1" in readme
    assert "Updated ACLED and added new Flowminder month." in readme
    assert "old description" not in readme
    assert "build-2026-05-20-abc1234" in readme
    assert "Previous summary line." in readme


def test_editor_refuses_empty_description(tmp_path):
    _seed_repo(tmp_path)
    _init_git(tmp_path)
    editor_body = "#!/usr/bin/env bash\necho '# only comments' > \"$1\"\n"
    bin_dir, _ = _install_stubs(tmp_path, editor_body=editor_body)
    result = _run_release(
        tmp_path,
        bin_dir=bin_dir,
        editor=bin_dir / "fake-editor",
    )
    assert result.returncode != 0
    assert "description" in result.stderr.lower()


def test_first_ever_release_skips_archive(tmp_path):
    """When build/DESCRIPTION.md is absent, archive step is skipped (no gh call)."""
    _seed_repo(tmp_path, with_description=False)
    _init_git(tmp_path)
    editor_body = (
        "#!/usr/bin/env bash\n"
        "cat > \"$1\" <<EOF\n"
        "Inaugural described build.\n"
        "EOF\n"
    )
    bin_dir, gh_log = _install_stubs(tmp_path, editor_body=editor_body)
    result = _run_release(
        tmp_path,
        bin_dir=bin_dir,
        editor=bin_dir / "fake-editor",
    )
    assert result.returncode == 0, result.stderr

    # gh should NOT have been called for `release view` or `release create`.
    log = gh_log.read_text() if gh_log.exists() else ""
    assert "release view" not in log
    assert "release create" not in log

    # DESCRIPTION.md was written for the new build.
    desc = (tmp_path / "build" / "DESCRIPTION.md").read_text()
    assert desc.startswith("Inaugural described build")

    # README rewritten with the new current build, but no past-release row added.
    readme = (tmp_path / "README.md").read_text()
    assert "# Current build (2026-05-22)" in readme
    assert "Inaugural described build" in readme
