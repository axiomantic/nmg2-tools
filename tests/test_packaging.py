"""The packaging contract for the package this repository ships.

`pyproject.toml` pins the layout. A package that the `packages` list does not
name is a package that `pip install .` does not install, and a fresh clone
therefore cannot import it. The list is asserted here so that adding a package
directory without declaring it fails.

The module and test rosters below are EXACT equalities, not membership checks.
A file added to `nmg2_tools/` or to `tests/` without a row here is a file no
one decided to ship.
"""

import pathlib
import shutil
import subprocess
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_declares_the_one_package():
    """Exact equality, not membership. A second package added without a row
    here is a package no one decided to ship."""
    assert PYPROJECT["tool"]["setuptools"]["packages"] == ["nmg2_tools"]


def test_the_package_holds_exactly_the_declared_modules():
    """One row per shipped module."""
    assert sorted(
        p.name for p in (ROOT / "nmg2_tools").glob("*.py")
    ) == [
        "__init__.py",
        # The Python half of the ArtifactResolver.
        "artifacts.py",
        # The container checksum.
        "checksum.py",
        # The container header and section table.
        "container.py",
        # The firmware-CRC cross-check.
        "crc_crosscheck.py",
        # The DSP56300 disassembler.
        "dsp56k_dis.py",
        "extract_demo_corpus.py",
        # The CS2 flash image builder.
        "flashimage.py",
        # The LZO1X decompressor.
        "lzo1x.py",
        # The module map generator.
        "modulemap.py",
        # The `.pch2` parser.
        "pch2.py",
        # The Windows PE resource reader.
        "pe.py",
        # The Macintosh resource-fork reader.
        "rsrc.py",
        # The descriptor signature scanner.
        "sigscan.py",
        # The synthesized `.pch2` corpus generator.
        "synth_pch2.py",
        # The `.pch2`-to-wire reassembler oracle.
        "wire_compose.py",
    ]


def test_the_suite_holds_exactly_the_declared_test_modules():
    assert sorted(p.name for p in (ROOT / "tests").glob("test_*.py")) == [
        # The Python half of the ArtifactResolver.
        "test_artifacts.py",
        # The container checksum.
        "test_checksum.py",
        # The container header and section table.
        "test_container.py",
        # The firmware-CRC cross-check.
        "test_crc_crosscheck.py",
        # The DSP56300 disassembler.
        "test_dsp56k_dis.py",
        # The updater resource extraction tests.
        "test_extract.py",
        "test_extract_demo_corpus.py",
        # The CS2 flash image builder.
        "test_flashimage.py",
        # The LZO1X decompressor.
        "test_lzo1x.py",
        # The module map generator.
        "test_modulemap.py",
        "test_packaging.py",
        # The `.pch2` parser against the synthesized corpus (T0).
        "test_pch2.py",
        # The `.pch2` parser against the G2 Demo corpus (T1).
        "test_pch2_real_corpus.py",
        # The descriptor signature scanner.
        "test_sigscan.py",
        # The synthesized `.pch2` corpus generator.
        "test_synth_pch2.py",
        # The `.pch2`-to-wire reassembler oracle.
        "test_wire_compose.py",
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
    notices, because a `grep -r` over this repository finds no reader for any
    file in it.
    """
    tracked = tracked_paths()
    assert "pyproject.toml" in tracked  # an empty listing makes the next line pass
    assert [path for path in tracked if ".egg-info/" in path] == []
