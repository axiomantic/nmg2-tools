"""The packaging contract for the one package this repository ships.

`pyproject.toml` pins the layout. A package that the `packages` list does not
name is a package that `pip install .` does not install, and a fresh clone
therefore cannot import it. The list is asserted here so that adding a package
directory without declaring it fails.
"""

import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_declares_the_single_package():
    """Exact equality, not membership. A second package added without a row
    here is a package no one decided to ship."""
    assert PYPROJECT["tool"]["setuptools"]["packages"] == ["nmg2_tools"]


def test_nmg2_tools_holds_exactly_the_committed_modules():
    """A module added or dropped without a row here is a module no one decided
    to ship. The glob is asserted non-empty first so that a vanished package
    directory fails loudly rather than passing on an empty iteration."""
    committed = sorted(p.name for p in (ROOT / "nmg2_tools").glob("*.py"))

    assert committed, "nmg2_tools/ holds no Python modules"
    assert committed == [
        "__init__.py",
        # REPO-5. The Python half of the ArtifactResolver.
        "artifacts.py",
        "extract_demo_corpus.py",
    ]


def test_tests_directory_holds_exactly_the_committed_test_modules():
    committed = sorted(p.name for p in (ROOT / "tests").glob("test_*.py"))

    assert committed, "tests/ holds no test modules"
    assert committed == [
        # REPO-5. The Python half of the ArtifactResolver.
        "test_artifacts.py",
        "test_extract_demo_corpus.py",
        "test_packaging.py",
    ]


def test_nmg2_tools_is_imported_from_this_repository_and_not_elsewhere():
    """A stale copy on `sys.path` would let every assertion above pass while
    the committed tree stayed broken."""
    import nmg2_tools

    assert pathlib.Path(nmg2_tools.__file__).resolve().parent == ROOT / "nmg2_tools"
    assert sys.modules["nmg2_tools"].__name__ == "nmg2_tools"
