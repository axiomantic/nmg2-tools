"""The packaging contract for the packages this repository ships.

`pyproject.toml` pins the layout. A package that the `packages` list does not
name is a package that `pip install .` does not install, and a fresh clone
therefore cannot import it. The list is asserted here so that adding a package
directory without declaring it fails.

The `plan_lint` module that this repository once carried is asserted ABSENT.
Its `--` rule polarity was inverted against the behaviour of `ctest`, and it
exited 0 when it parsed nothing. None of its rules survive.
"""

import pathlib
import shutil
import subprocess
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_declares_its_packages():
    """Exact equality, not membership. A second package added without a row
    here is a package no one decided to ship."""
    assert PYPROJECT["tool"]["setuptools"]["packages"] == ["nmg2_tools"]


def test_the_superseded_plan_lint_module_is_absent():
    """Its rules are not preserved anywhere."""
    assert sorted(
        p.name for p in (ROOT / "nmg2_tools").glob("*.py")
    ) == [
        "__init__.py",
        # REPO-5. The Python half of the ArtifactResolver.
        "artifacts.py",
        # TOOL-2. The container checksum.
        "checksum.py",
        # TOOL-3. The container header and section table.
        "container.py",
        "credential_lint.py",
        # TOOL-7. The DSP56300 disassembler.
        "dsp56k_dis.py",
        "extract_demo_corpus.py",
        # TOOL-5. The CS2 flash image builder.
        "flashimage.py",
        # The git index reader both repository lints share, and the one place
        # that knows a gitlink from a file.
        "gitindex.py",
        # TOOL-1. The LZO1X decompressor.
        "lzo1x.py",
        # TOOL-8. The module map generator.
        "modulemap.py",
        "payload_lint.py",
        # TOOL-10. The `.pch2` parser.
        "pch2.py",
        # TOOL-4. The Windows PE resource reader.
        "pe.py",
        # TOOL-4. The Macintosh resource-fork reader.
        "rsrc.py",
        # TOOL-6. The descriptor signature scanner.
        "sigscan.py",
        "submodule_lint.py",
        # TOOL-12. The synthesized `.pch2` corpus generator.
        "synth_pch2.py",
    ]


def test_the_superseded_plan_lint_test_module_is_absent():
    assert sorted(p.name for p in (ROOT / "tests").glob("test_*.py")) == [
        # REPO-5. The Python half of the ArtifactResolver.
        "test_artifacts.py",
        # TOOL-2. The container checksum.
        "test_checksum.py",
        # TOOL-3. The container header and section table.
        "test_container.py",
        "test_credential_lint.py",
        # TOOL-7. The DSP56300 disassembler.
        "test_dsp56k_dis.py",
        # TOOL-4. The updater resource extraction tests.
        "test_extract.py",
        "test_extract_demo_corpus.py",
        # TOOL-5. The CS2 flash image builder.
        "test_flashimage.py",
        # TOOL-1. The LZO1X decompressor.
        "test_lzo1x.py",
        # TOOL-8. The module map generator.
        "test_modulemap.py",
        "test_packaging.py",
        "test_payload_lint.py",
        # TOOL-10. The `.pch2` parser against the synthesized corpus (T0).
        "test_pch2.py",
        # TOOL-10. The `.pch2` parser against the G2 Demo corpus (T1).
        "test_pch2_real_corpus.py",
        # TOOL-6. The descriptor signature scanner.
        "test_sigscan.py",
        "test_submodule_lint.py",
        # TOOL-12. The synthesized `.pch2` corpus generator.
        "test_synth_pch2.py",
    ]


def tracked_paths():
    """Every path this repository tracks, or a stated reason there is no answer.

    A missing `git` and a repository that tracks nothing produce the same empty
    list, which is this project's signature failure mode. Each absence skips
    with its own reason instead.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH, so the tracked file set cannot be read")
    if not (ROOT / ".git").exists():
        pytest.skip(f"{ROOT} is not a git checkout, so it tracks nothing to read")
    listing = subprocess.run(
        [git, "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [path for path in listing.split("\0") if path]


def test_no_generated_metadata_tree_is_tracked():
    """`setuptools` writes `*.egg-info/` and rewrites it on every build. Under
    version control it disagrees with the tree between builds and nothing
    notices: `SOURCES.txt` goes on naming a module the tree no longer holds for
    as long as no one reran `pip install .`, and a `grep -r` over this
    repository finds no reader for any file in it.
    """
    tracked = tracked_paths()
    assert "pyproject.toml" in tracked  # an empty listing makes the next line pass
    assert [path for path in tracked if ".egg-info/" in path] == []


def test_the_lint_gate_is_wired_end_to_end():
    """The four pieces of the ruff gate reference each other, or it is not a gate.

    `pyproject.toml` holds the rules, `.ruff-version` holds the tool version,
    `scripts/ruff-baseline.sh` produces the reading and `.ruff-baseline.txt`
    holds the reading it is compared against. Delete any one and the CI job
    either stops running or starts passing for the wrong reason. This asserts
    the wiring only: whether the tree still MATCHES the baseline is the CI job's
    question, and asking it here would need ruff installed, which would make the
    check skip on a machine without it and read exactly like a pass.
    """
    lint = PYPROJECT["tool"]["ruff"]["lint"]
    assert lint["select"], "no rules selected: the gate would report nothing"

    version = (ROOT / ".ruff-version").read_text(encoding="utf-8").strip()
    assert version, ".ruff-version is empty"

    script = ROOT / "scripts" / "ruff-baseline.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "the script is not executable"
    assert ".ruff-version" in script.read_text(encoding="utf-8"), (
        "the script does not read the pin, so it can use a different ruff than CI"
    )

    baseline = (ROOT / ".ruff-baseline.txt").read_text(encoding="utf-8")
    rows = [line for line in baseline.splitlines() if not line.startswith("#")]
    assert rows, "an empty baseline makes any diff against it meaningless"

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/ruff-baseline.sh" in workflow
    assert ".ruff-baseline.txt" in workflow
    assert ".ruff-version" in workflow
