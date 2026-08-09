"""The packaging contract for the two packages this repository ships.

`pyproject.toml` pins the layout. A package that the `packages` list does not
name is a package that `pip install .` does not install, and a fresh clone
therefore cannot import it. The list is asserted here so that adding a package
directory without declaring it fails.

The `plan_lint` module that this repository once carried is asserted ABSENT.
It recovered 4 task blocks where `planlint` recovers 210, its `--` rule
polarity was inverted against the behaviour of `ctest`, and it exited 0 when it
parsed nothing. None of its rules survive.
"""

import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_declares_both_packages():
    """Exact equality, not membership. A third package added without a row
    here is a package no one decided to ship."""
    assert PYPROJECT["tool"]["setuptools"]["packages"] == ["nmg2_tools", "planlint"]


def test_pyproject_declares_the_planlint_console_script():
    assert PYPROJECT["project"]["scripts"] == {"planlint": "planlint.cli:main"}


def test_planlint_package_directory_holds_every_module_the_cli_imports():
    """The ten lint modules plus the four support modules. A module that the
    migration dropped makes `planlint.cli` fail to import; this names which."""
    committed = sorted(p.name for p in (ROOT / "planlint").glob("*.py"))

    assert committed == [
        "__init__.py",
        "checks.py",
        "cli.py",
        "closure.py",
        "counts.py",
        "document.py",
        "finding.py",
        "graph.py",
        "implicit.py",
        "payload.py",
        "registrar.py",
        "structure.py",
        "tiers.py",
        "waves.py",
    ]


def test_planlint_cli_exposes_the_ten_lints():
    from planlint import cli

    # `structure` runs FIRST. Every lint below it reads a parsed document, so
    # a broken fence or an unpaired backtick is the cause and the rest are the
    # consequence.
    assert list(cli.DOCUMENT_LINTS) == [
        "structure",
        "graph",
        "waves",
        "tiers",
        "checks",
        "counts",
        "implicit",
        "registrar",
        "closure",
    ]
    assert cli.REPOSITORY_LINTS == ("payload",)
    assert cli.ALL_LINTS == [
        "structure",
        "graph",
        "waves",
        "tiers",
        "checks",
        "counts",
        "implicit",
        "registrar",
        "closure",
        "payload",
    ]


def test_planlint_never_exits_zero_with_no_input():
    """The founding defect of this project was a check that passed because it
    ran nothing. `--plan` naming a file that does not exist is exit 2, and the
    message names the missing path rather than reporting a clean run."""
    import io

    from planlint import cli

    stream = io.StringIO()
    code = cli.main(["--plan", str(ROOT / "no_such_plan.md")], stream=stream)

    assert code == 2
    assert stream.getvalue() == f"no such plan document: {ROOT / 'no_such_plan.md'}\n"


def test_the_superseded_plan_lint_module_is_absent():
    """Its rules are not preserved anywhere. `planlint` replaces it whole."""
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
        # TOOL-1. The LZO1X decompressor.
        "lzo1x.py",
        "payload_lint.py",
        # TOOL-4. The Windows PE resource reader.
        "pe.py",
        # TOOL-4. The Macintosh resource-fork reader.
        "rsrc.py",
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
        "test_packaging.py",
        "test_payload_lint.py",
        "test_submodule_lint.py",
        # TOOL-12. The synthesized `.pch2` corpus generator.
        "test_synth_pch2.py",
    ]


def test_planlint_is_imported_from_this_repository_and_not_elsewhere():
    """A stale copy on `sys.path` would let every assertion above pass while
    the committed tree stayed broken."""
    import planlint

    assert pathlib.Path(planlint.__file__).resolve().parent == ROOT / "planlint"
    assert sys.modules["planlint"].__name__ == "planlint"
