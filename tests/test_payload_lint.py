import os
import subprocess
import sys
from pathlib import Path

import pytest

from nmg2_tools.payload_lint import (
    KNOWN_REPOSITORIES,
    PCH2_ALLOWED_DIR,
    PENDING_PREFIX,
    SHIPPED_REGISTER,
    SOURCE_BASENAMES,
    SOURCE_SUFFIXES,
    RegisterError,
    RegisterEntry,
    check_register_rows,
    lint_committed_files,
    REPO_SCOPED_VISIBILITIES,
    _committed_files,
    lint_repo_tree,
    load_register,
    main,
)
from nmg2_tools.gitindex import GITLINK_MODE, index_entries

REPO_ROOT = Path(__file__).resolve().parents[1]

# `pch2-exception` rows carry the repository they were granted for. An
# unqualified row grants nothing anywhere, so a fixture that leaves the field
# out no longer describes a usable register.
FIXTURE_REPO = "axiomantic/G2-Edit"

REGISTER = [
    RegisterEntry("nmg2_tools/testdata/pch2_synth/", "public"),
    RegisterEntry("g2Lib/test/fixtures/synthetic_block_program.asm", "public"),
    RegisterEntry("conformance/corpus/", "public allow-listed"),
    RegisterEntry("golden/", "private"),
    RegisterEntry("PatchTestFiles/", "public pch2-exception", FIXTURE_REPO),
    RegisterEntry("testdata/PatchTestFiles/", "public pch2-exception", FIXTURE_REPO),
    # Mirrors the row `nmg2-artifacts` carries for its demo corpus.
    RegisterEntry("corpus/pch2/", "private"),
]


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_pch2_outside_synth_corpus_fails(tmp_path):
    rel = "some/other/place.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert any(f.startswith("PAYLOAD-PCH2-LOCATION") for f in failures)


def test_pch2_inside_synth_corpus_passes(tmp_path):
    rel = "nmg2_tools/testdata/pch2_synth/demo.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert failures == []


def test_pch2_at_registered_corpus_path_in_private_repo_passes(tmp_path):
    """Clause 1 is a PUBLIC-repository rule; a private repository may hold the corpus.

    This is the exact shape `nmg2-artifacts` has: a private repository, a
    `corpus/pch2/` row marked private, and a `.pch2` file beneath it.
    """
    rel = "corpus/pch2/Anthem demo.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="private")
    assert failures == []


def test_pch2_outside_synth_corpus_in_public_repo_still_fails(tmp_path):
    """The private-repository allowance must not weaken the public rule."""
    rel = "corpus/pch2/Anthem demo.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="public")
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-PRIVATE-IN-PUBLIC: {rel}: register marks this path private, "
        "but it is committed in a public repository",
    ]


def test_unregistered_pch2_in_private_repo_is_reported_as_unregistered(tmp_path):
    """Clause 1 does not police a private repository. Clause 2 does.

    The location clause stays a PUBLIC-repository rule, so the finding here
    names registration and not location -- but there IS a finding. A `.pch2`
    the register has never heard of is exactly the file this guard exists to
    mention, and where it sits does not change that.
    """
    rel = "some/other/place.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="private")
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


def test_unregistered_fixture_at_10_bytes_fails(tmp_path):
    rel = "g2Lib/test/fixtures/unknown_thing.bin"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert any(f.startswith("PAYLOAD-UNREGISTERED") for f in failures)


def test_fixture_over_ceiling_no_allowlist_fails(tmp_path):
    rel = "g2Lib/test/fixtures/synthetic_block_program.asm"
    _write(tmp_path / rel, 65_537)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert any(f.startswith("PAYLOAD-CEILING") for f in failures)


def test_fixture_at_ceiling_with_public_row_passes(tmp_path):
    rel = "g2Lib/test/fixtures/synthetic_block_program.asm"
    _write(tmp_path / rel, 65_536)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert failures == []


def test_allow_listed_above_ceiling_passes(tmp_path):
    rel = "conformance/corpus/big_sample.bin"
    _write(tmp_path / rel, 200_000)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert failures == []


def test_private_row_in_public_repo_fails(tmp_path):
    rel = "golden/render.wav"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="public")
    assert any(f.startswith("PAYLOAD-PRIVATE-IN-PUBLIC") for f in failures)


def test_private_row_in_private_repo_passes(tmp_path):
    rel = "golden/render.wav"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="private")
    assert failures == []


def test_pch2_under_pch2_exception_row_passes(tmp_path):
    rel = "PatchTestFiles/InheritedOne.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, repo=FIXTURE_REPO)
    assert failures == []


def test_pch2_exception_row_grants_no_size_exemption(tmp_path):
    rel = "testdata/PatchTestFiles/InheritedBig.pch2"
    _write(tmp_path / rel, 65_537)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, repo=FIXTURE_REPO)
    assert failures == [
        f"PAYLOAD-CEILING: {rel}: 65537 bytes exceeds the 65536 byte ceiling "
        "and is not allow-listed"
    ]


def test_shipped_register_has_exactly_one_pch2_exception_row():
    entries = load_register(SHIPPED_REGISTER)
    exception_entries = [e for e in entries if e.pch2_excepted]
    assert len(exception_entries) == 1
    assert exception_entries[0].path == "PatchTestFiles/"


# --- The pch2 exception is scoped to ONE repository -------------------------
#
# The register is a single file shared by every repository. An
# unqualified `PatchTestFiles/` row would except that path in EVERY public
# repository, so any repository could silence this lint by choosing a
# directory name. The exception carries the repository it was granted for,
# and it applies nowhere else.

SCOPED_REGISTER = [
    RegisterEntry("nmg2_tools/testdata/pch2_synth/", "public"),
    RegisterEntry("PatchTestFiles/", "public pch2-exception", "axiomantic/G2-Edit"),
]


def test_pch2_exception_applies_in_the_repository_it_names(tmp_path):
    rel = "PatchTestFiles/InheritedOne.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(
        tmp_path, [rel], SCOPED_REGISTER, repo="axiomantic/G2-Edit"
    )
    assert failures == []


def test_pch2_exception_does_not_apply_in_a_different_repository(tmp_path):
    """A directory merely NAMED `PatchTestFiles` in another repository fails.

    BOTH clauses answer, and the second is the point: in `mc68k` the scoped
    row is not a weaker row, it is no row, so the path is one the register has
    never heard of. An unregistered `.pch2` with no row at all reports exactly
    this pair, which is what makes the two readings the same reading.
    """
    rel = "PatchTestFiles/Smuggled.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(
        tmp_path, [rel], SCOPED_REGISTER, repo="axiomantic/mc68k"
    )
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row "
        "and no by-rule classification",
    ]


def test_pch2_exception_does_not_apply_when_no_repository_is_supplied(tmp_path):
    """Fail closed: an unidentified repository gets no scoped exception."""
    rel = "PatchTestFiles/Smuggled.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], SCOPED_REGISTER, repo=None)
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row "
        "and no by-rule classification",
    ]


def test_scoped_exception_does_not_widen_to_other_paths_in_its_own_repo(tmp_path):
    """The grant covers its own path only, not every `.pch2` in G2-Edit."""
    rel = "src/Sneaky.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(
        tmp_path, [rel], SCOPED_REGISTER, repo="axiomantic/G2-Edit"
    )
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification",
    ]


def test_shipped_register_pch2_exception_row_is_scoped_to_g2_edit():
    entries = load_register(SHIPPED_REGISTER)
    exception_entries = [e for e in entries if e.pch2_excepted]
    assert len(exception_entries) == 1
    assert exception_entries[0].path == "PatchTestFiles/"
    assert exception_entries[0].repo == "axiomantic/G2-Edit"


# --- An UNQUALIFIED exception row grants nothing, anywhere ------------------
#
# The row scoping above closed the hole for a row that NAMES a repository. A
# row that names none was still honoured in every repository, which is the
# same hole with the field left out. The register is one file shared by every
# repository, so the unqualified row is the wider hole, not the narrower
# one. It now grants nothing at all.

# The repositories that share `nmg2_tools/testdata/register.tsv`.
SEVEN_REPOS = (
    "axiomantic/nmg2-tools",
    "axiomantic/G2-Edit",
    "axiomantic/mc68k",
    "axiomantic/mcf5307",
    "axiomantic/dsp56300",
    "axiomantic/gearmulator",
    "axiomantic/nmg2-artifacts",
)

UNQUALIFIED_REGISTER = [
    RegisterEntry("nmg2_tools/testdata/pch2_synth/", "public"),
    RegisterEntry("PatchTestFiles/", "public pch2-exception"),
]


def test_unqualified_pch2_exception_row_grants_no_exception_in_any_repository(
    tmp_path,
):
    """Fail closed: a row with no repository field excepts nothing, anywhere.

    Checked against every repository that shares the register, and
    against an unidentified caller.
    """
    rel = "PatchTestFiles/InheritedOne.pch2"
    _write(tmp_path / rel, 10)
    expected = [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row "
        "and no by-rule classification",
    ]
    for repo in (*SEVEN_REPOS, None):
        failures = lint_committed_files(
            tmp_path, [rel], UNQUALIFIED_REGISTER, repo=repo
        )
        assert failures == expected, f"unqualified row was honoured for repo={repo!r}"


def test_unqualified_row_grants_nothing_even_at_the_entry_level():
    """The grant test itself fails closed, not only the caller that uses it."""
    entry = RegisterEntry("PatchTestFiles/", "public pch2-exception")
    assert entry.pch2_excepted is True
    assert entry.pch2_excepted_in("axiomantic/G2-Edit") is False
    assert entry.pch2_excepted_in(None) is False


# --- A malformed exception row is a HARD ERROR, not a silent no-grant -------
#
# Failing closed at the grant test alone would leave a register row that
# reads like a grant and does nothing. That is the same green mirage this
# module exists to stop, so the parse rejects the row and names the line.


def _register_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "register.tsv"
    path.write_text(text)
    return path


def test_load_register_rejects_a_pch2_exception_row_with_no_repository_field(tmp_path):
    path = _register_file(
        tmp_path,
        "nmg2_tools/testdata/pch2_synth/\tpublic\taxiomantic/nmg2-tools\n"
        "PatchTestFiles/\tpublic pch2-exception\n",
    )
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert str(caught.value) == (
        f"{path}:2: a `public pch2-exception` row must carry a third, "
        "tab-separated `owner/name` field naming the one repository it is "
        "granted for: 'PatchTestFiles/\\tpublic pch2-exception'"
    )


def test_load_register_rejects_a_pch2_exception_row_written_with_spaces(tmp_path):
    """The space-separated fallback cannot carry a repository field.

    A row that reaches it therefore cannot be a valid exception row, even
    when the operator wrote a repository slug on the line.
    """
    path = _register_file(
        tmp_path,
        "PatchTestFiles/  public pch2-exception  axiomantic/G2-Edit\n",
    )
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert str(caught.value) == (
        f"{path}:1: a `public pch2-exception` row must carry a third, "
        "tab-separated `owner/name` field naming the one repository it is "
        "granted for: 'PatchTestFiles/  public pch2-exception  "
        "axiomantic/G2-Edit'"
    )


def test_load_register_accepts_the_canonical_pch2_exception_row(tmp_path):
    path = _register_file(
        tmp_path, "PatchTestFiles/\tpublic pch2-exception\taxiomantic/G2-Edit\n"
    )
    entries = load_register(path)
    assert [(e.path, e.visibility, e.repo) for e in entries] == [
        ("PatchTestFiles/", "public pch2-exception", "axiomantic/G2-Edit")
    ]


def test_main_reports_a_malformed_register_row_as_a_named_failure(
    tmp_path, capsys
):
    """A bad register is a named finding and exit 1, never a traceback."""
    register = _register_file(
        tmp_path, "PatchTestFiles/\tpublic pch2-exception\n"
    )
    tree = tmp_path / "tree"
    tree.mkdir()
    # A real, empty git tree: the register is rejected on its own account and
    # not because the tree could not be read.
    subprocess.run(["git", "-C", str(tree), "init", "-q"], check=True)
    status = main([str(tree), "--register", str(register), "--repo", "axiomantic/G2-Edit"])
    assert status == 1
    assert capsys.readouterr().err == (
        f"PAYLOAD-REGISTER-MALFORMED: {register}:1: a `public pch2-exception` "
        "row must carry a third, tab-separated `owner/name` field naming the "
        "one repository it is granted for: "
        "'PatchTestFiles/\\tpublic pch2-exception'\n"
    )


# --- The shipped, qualified row keeps working -------------------------------


def test_shipped_register_exception_applies_in_g2_edit(tmp_path):
    rel = "PatchTestFiles/InheritedOne.pch2"
    _write(tmp_path / rel, 10)
    entries = load_register(SHIPPED_REGISTER)
    failures = lint_committed_files(
        tmp_path, [rel], entries, repo="axiomantic/G2-Edit"
    )
    assert failures == []


def test_shipped_register_exception_does_not_travel_to_another_repository(tmp_path):
    rel = "PatchTestFiles/InheritedOne.pch2"
    _write(tmp_path / rel, 10)
    entries = load_register(SHIPPED_REGISTER)
    failures = lint_committed_files(tmp_path, [rel], entries, repo="axiomantic/mc68k")
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row "
        "and no by-rule classification",
    ]


def test_shipped_register_private_guard_holds_for_the_demo_corpus(tmp_path):
    """The private-repository allowance is untouched by the fail-closed rule.

    `nmg2-artifacts` is private and holds `corpus/pch2/`; clause 1 does not
    police a private repository, and clause 4 lets the `private` row stand.
    """
    rel = "corpus/pch2/Anthem demo.pch2"
    _write(tmp_path / rel, 10)
    entries = load_register(SHIPPED_REGISTER)
    failures = lint_committed_files(
        tmp_path,
        [rel],
        entries,
        visibility="private",
        repo="axiomantic/nmg2-artifacts",
    )
    assert failures == []


# --- The register resolves against the code, not against the cwd ------------
#
# A path resolved against the process's working directory passes from the
# repository root and fails from everywhere else. That is green locally and
# red in CI, in the shape of a real defect, so the guard below has to fail
# where the bug HIDES -- from the repository root -- and not only where it
# already shows.


@pytest.mark.skipif(
    "_NMG2_FOREIGN_CWD_CHILD" in os.environ,
    reason="the child run of this same module; recursing again would not end",
)
def test_this_module_passes_from_a_foreign_working_directory(tmp_path):
    """Every test here resolves its fixtures independently of the cwd.

    The child run carries `_NMG2_FOREIGN_CWD_CHILD`, which makes this test
    skip inside it. The recursion is one level deep and terminates.
    """
    environment = dict(os.environ, _NMG2_FOREIGN_CWD_CHILD="1")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(Path(__file__).resolve()), "-q",
         "-p", "no:cacheprovider"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_default_register_is_found_from_a_foreign_working_directory(
    tmp_path, monkeypatch, capsys
):
    """`--register` defaults to the shipped file wherever the tool is run.

    The tree under test is THIS REPOSITORY and not an empty scratch directory.
    An empty directory used to serve here, and clause 6 now reports one --
    a lint that looped over no file prints what a clean tree prints. The
    assertion the test was written for is unchanged: run from a foreign
    working directory, the default register still resolves.
    """
    monkeypatch.chdir(tmp_path)
    status = main([str(REPO_ROOT), "--repo", "axiomantic/nmg2-tools"])
    assert status == 0
    assert capsys.readouterr() == ("", "")


# --- An UNREGISTERED path is a finding, not a skip ---------------------------
#
# The guard used to reach `if entry is None: continue` for any committed file
# that carried no register row and sat under no scoped directory. Two real
# files -- `dsp/g2_module_descriptors.csv` and `g2demo/g2_modules.json` --
# passed that way. The control below is the same file under a scoped
# directory, which the guard DID report: the silence was blindness, not a
# clean bill.

CLASS_REGISTER = [
    RegisterEntry("golden/", "private"),
    RegisterEntry("conformance/corpus/", "public allow-listed"),
]


def test_unregistered_file_outside_every_payload_directory_fails(tmp_path):
    rel = "g2demo/g2_modules.json"
    _write(tmp_path / rel, 297_564)
    failures = lint_committed_files(
        tmp_path, [rel], CLASS_REGISTER, visibility="private"
    )
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


def test_unregistered_file_under_a_payload_directory_still_fails(tmp_path):
    """The control, from the same population: this one was never silent."""
    rel = "fixtures/g2_modules.json"
    _write(tmp_path / rel, 297_564)
    failures = lint_committed_files(
        tmp_path, [rel], CLASS_REGISTER, visibility="private"
    )
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


# --- Classes described by RULE, not by enumeration --------------------------
#
# Making an unregistered path fail lights up every project source file and
# every prose file at once. Adding a row per file would be a roster where a
# predicate belongs. Two classes are therefore decided in code:
#
#   source -- project-authored code and build metadata, read line by line in
#             review. Bulk vendor payload does not arrive as reviewed source.
#   prose  -- markdown and reStructuredText. Prose is PUBLIC by default; a
#             prose file that must not be public carries an explicit row,
#             which wins over the class.
#
# Neither class applies inside a payload directory, where the tree itself
# declares that the contents are data.


def test_project_source_needs_no_register_row(tmp_path):
    rel = "nmg2_tools/payload_lint.py"
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


def test_project_source_is_exempt_from_the_ceiling(tmp_path):
    """`tests/planlint/test_secondwrite.py` grew past the ceiling.

    It is Python test source carrying no Clavia byte. The exemption is the
    CLASS's, stated here and not granted by a row of its own: the ceiling
    exists to notice bulk data, and the size of source is a code-review
    concern.
    """
    rel = "tests/planlint/test_secondwrite.py"
    _write(tmp_path / rel, 74_232)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


def test_prose_needs_no_register_row_and_is_exempt_from_the_ceiling(tmp_path):
    rel = "docs/plans/2026-08-04-nmg2-emulator-impl.md"
    _write(tmp_path / rel, 4_366_648)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


def test_an_explicit_row_beats_the_prose_class(tmp_path):
    """`FINDINGS.md` is prose by suffix and private by decision."""
    rel = "golden/FINDINGS.md"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], CLASS_REGISTER, visibility="public")
    assert failures == [
        f"PAYLOAD-PRIVATE-IN-PUBLIC: {rel}: register marks this path private, "
        "but it is committed in a public repository"
    ]


def test_source_suffix_inside_a_payload_directory_still_needs_a_row(tmp_path):
    """A `.py` under `fixtures/` is fixture DATA, not project source."""
    rel = "tests/planlint/fixtures/repo_provenance_bad/nmg2_tools/isa.py"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], CLASS_REGISTER)
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


# --- The ceiling keys on the ROW, never on a roster of directory names ------
#
# The ceiling used to apply only under `fixtures/`, `corpus/`, `golden/`,
# `captures/` or `testdata/`. A 297,564-byte file in `g2demo/` escaped it for
# no reason but the directory's name. The answer is NOT to add `g2demo/` to
# that list -- an exception list amended once per case is a missing
# predicate. The ceiling now applies to every REGISTERED path in either
# visibility, and a path above it must say so with `allow-listed`.


def test_ceiling_applies_to_a_registered_path_in_any_directory(tmp_path):
    rel = "g2demo/g2_modules.json"
    _write(tmp_path / rel, 297_564)
    entries = [RegisterEntry("g2demo/", "private")]
    failures = lint_committed_files(tmp_path, [rel], entries, visibility="private")
    assert failures == [
        f"PAYLOAD-CEILING: {rel}: 297564 bytes exceeds the 65536 byte ceiling "
        "and is not allow-listed"
    ]


def test_private_allow_listed_row_passes_above_the_ceiling(tmp_path):
    rel = "g2demo/g2_modules.json"
    _write(tmp_path / rel, 297_564)
    entries = [RegisterEntry("g2demo/g2_modules.json", "private allow-listed")]
    failures = lint_committed_files(tmp_path, [rel], entries, visibility="private")
    assert failures == []


def test_private_allow_listed_row_is_still_private_in_a_public_repo(tmp_path):
    rel = "g2demo/g2_modules.json"
    _write(tmp_path / rel, 297_564)
    entries = [RegisterEntry("g2demo/g2_modules.json", "private allow-listed")]
    failures = lint_committed_files(tmp_path, [rel], entries, visibility="public")
    assert failures == [
        f"PAYLOAD-PRIVATE-IN-PUBLIC: {rel}: register marks this path private, "
        "but it is committed in a public repository"
    ]


# --- A lint's own synthetic repositories are a class, named as one ----------
#
# `tests/planlint/fixtures/repo_public_bad/` is a fake repository built to
# IMITATE a payload violation: it holds `.pch2` files outside the synth
# corpus and a deliberately over-ceiling blob. Excepting each of those with a
# row of its own would be the roster again, so the class carries one name.
# The grant is strong, so it is scoped to the repository it was granted for,
# exactly as `public pch2-exception` is.

FIXTURE_REPO_REGISTER = [
    RegisterEntry(
        "tests/planlint/fixtures/", "public fixture-repo", "axiomantic/nmg2-tools"
    ),
]


def test_fixture_repo_row_exempts_clause_1_and_the_ceiling(tmp_path):
    pch2 = "tests/planlint/fixtures/repo_public_bad/patches/demo_bank.pch2"
    blob = "tests/planlint/fixtures/repo_public_bad/fixtures/over_ceiling.bin"
    _write(tmp_path / pch2, 10)
    _write(tmp_path / blob, 65_537)
    failures = lint_committed_files(
        tmp_path,
        [pch2, blob],
        FIXTURE_REPO_REGISTER,
        visibility="public",
        repo="axiomantic/nmg2-tools",
    )
    assert failures == []


def test_fixture_repo_row_does_not_apply_in_another_repository(tmp_path):
    pch2 = "tests/planlint/fixtures/repo_public_bad/patches/demo_bank.pch2"
    _write(tmp_path / pch2, 10)
    failures = lint_committed_files(
        tmp_path,
        [pch2],
        FIXTURE_REPO_REGISTER,
        visibility="public",
        repo="axiomantic/mc68k",
    )
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {pch2}: .pch2 file outside {PCH2_ALLOWED_DIR}",
        f"PAYLOAD-UNREGISTERED: {pch2}: committed file with no register row "
        "and no by-rule classification",
    ]


def test_fixture_repo_row_grants_nothing_when_no_repository_is_supplied(tmp_path):
    blob = "tests/planlint/fixtures/repo_public_bad/fixtures/over_ceiling.bin"
    _write(tmp_path / blob, 65_537)
    failures = lint_committed_files(
        tmp_path, [blob], FIXTURE_REPO_REGISTER, visibility="public", repo=None
    )
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {blob}: committed file with no register row "
        "and no by-rule classification"
    ]


# The two tests above assert that a scoped row "does not apply" elsewhere, but
# each feeds the guard a file another clause catches anyway -- a `.pch2` and an
# over-ceiling blob. They therefore held while the row still answered clause 2
# for every repository in the register's reach. The input that separates the
# two readings is the SMALL, unclassified, non-`.pch2` file: nothing else
# reports it, so it is silent exactly when the row is being read as a
# registration it is not.


def test_fixture_repo_row_in_another_repository_does_not_register_a_small_file(
    tmp_path,
):
    small = "tests/planlint/fixtures/repo_public_bad/fixtures/blob.bin"
    _write(tmp_path / small, 10)
    failures = lint_committed_files(
        tmp_path,
        [small],
        FIXTURE_REPO_REGISTER,
        visibility="public",
        repo="axiomantic/mc68k",
    )
    assert failures == [
        f"PAYLOAD-UNREGISTERED: {small}: committed file with no register row "
        "and no by-rule classification"
    ]


def test_a_scoped_row_that_does_not_apply_falls_back_to_a_broader_row(tmp_path):
    """The row is absent HERE, not absent everywhere: a wider row still covers.

    Reading the scoped row as no row must not also discard a plain row that
    the path sits beneath. Otherwise the repair would trade one wrong answer
    for another.
    """
    small = "tests/planlint/fixtures/repo_public_bad/fixtures/blob.bin"
    _write(tmp_path / small, 10)
    register = FIXTURE_REPO_REGISTER + [RegisterEntry("tests/", "private")]
    failures = lint_committed_files(
        tmp_path,
        [small],
        register,
        visibility="public",
        repo="axiomantic/mc68k",
    )
    assert failures == [
        f"PAYLOAD-PRIVATE-IN-PUBLIC: {small}: register marks this path "
        "private, but it is committed in a public repository"
    ]


def test_load_register_rejects_a_fixture_repo_row_with_no_repository_field(tmp_path):
    path = _register_file(
        tmp_path, "tests/planlint/fixtures/\tpublic fixture-repo\n"
    )
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert str(caught.value) == (
        f"{path}:1: a `public fixture-repo` row must carry a third, "
        "tab-separated `owner/name` field naming the one repository it is "
        "granted for: 'tests/planlint/fixtures/\\tpublic fixture-repo'"
    )


def test_load_register_rejects_an_unknown_visibility(tmp_path):
    """A typo must not read as `public`, which is what silence would mean."""
    path = _register_file(tmp_path, "golden/\tprivte\n")
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert str(caught.value) == (
        f"{path}:1: unknown visibility 'privte'; the register accepts only "
        "public, private, public allow-listed, private allow-listed, "
        "public pch2-exception, public fixture-repo: 'golden/\\tprivte'"
    )


# --- The shipped register, held against the real tree ------------------------


def test_shipped_register_classifies_every_committed_file_in_this_repository():
    """No committed file in `nmg2-tools` is unclassified, and none fails.

    This is the artifact check: not that the code has a branch for it, but
    that the register and the class rules together cover the tree that is
    actually committed. The control below plants one unclassifiable path into
    the same population, so the empty list above is a measurement and not the
    silence this whole change was about.
    """
    root = Path(__file__).resolve().parents[1]
    entries = load_register(SHIPPED_REGISTER)
    committed = _committed_files(root)
    assert (
        lint_committed_files(
            root, committed, entries, "public", "axiomantic/nmg2-tools"
        )
        == []
    )

    planted = "evidence/unknown_capture.dat"
    assert lint_committed_files(
        root, [*committed, planted], entries, "public", "axiomantic/nmg2-tools"
    ) == [
        f"PAYLOAD-UNREGISTERED: {planted}: committed file with no register row "
        "and no by-rule classification"
    ]


def test_every_repo_scoped_row_in_the_shipped_register_names_a_repository():
    entries = load_register(SHIPPED_REGISTER)
    scoped = [
        (e.path, e.visibility, e.repo)
        for e in entries
        if e.visibility in REPO_SCOPED_VISIBILITIES
    ]
    assert scoped == [
        ("PatchTestFiles/", "public pch2-exception", "axiomantic/G2-Edit"),
        (
            "tests/planlint/fixtures/",
            "public fixture-repo",
            "axiomantic/nmg2-tools",
        ),
    ]


# --- Clause 6: the register read BACK against the tree ------------------------
#
# Every clause above walks committed files and asks the register about them.
# None of them walks a ROW and asks the tree, and that is the direction in
# which five `gearmulator` fixture rows carried a wrong root and a sixth named
# a file that never existed, for months, while the guard stayed green. A row
# that matched nothing by accident was indistinguishable from a row whose file
# had not landed yet, so the tests below check BOTH buckets in BOTH directions:
# an unexplained unmatched row is loud, an explicitly pending one is quiet, and
# a pending row that starts matching is loud again so the marker cannot rot.

HOME = "axiomantic/gearmulator"
AWAY = "axiomantic/mc68k"
FIXTURES = "source/nord/g2/g2Lib/test/fixtures/"
TREE = [FIXTURES + "esai_sync_spin.asm", "README.md"]


def test_a_row_matching_no_committed_path_in_its_home_is_reported():
    entries = [RegisterEntry(FIXTURES + "no_such_spin.asm", "public", HOME)]
    failures = check_register_rows(TREE, entries, HOME)
    assert failures == [
        f"PAYLOAD-REGISTER-UNMATCHED: {FIXTURES}no_such_spin.asm: this row is "
        f"at home in {HOME} and matches no committed path there, so it "
        "registers nothing. Correct the path, or mark the row "
        f"`{PENDING_PREFIX}<reason>` if the file is yet to land"
    ]


def test_the_wrong_prefix_that_started_this_is_reported():
    """The defect verbatim: `g2Lib/` where the tree says `source/nord/g2/`."""
    entries = [RegisterEntry("g2Lib/test/fixtures/esai_sync_spin.asm",
                             "public", HOME)]
    failures = check_register_rows(TREE, entries, HOME)
    assert len(failures) == 1
    assert failures[0].startswith(
        "PAYLOAD-REGISTER-UNMATCHED: g2Lib/test/fixtures/esai_sync_spin.asm:"
    )


def test_the_phantom_row_that_started_this_is_reported():
    """`frame_sync_spin.asm` names a file that never existed in `gearmulator`.

    The row is checked against a tree holding the file that DID land, which is
    the known positive: the same call answers nothing for `esai_sync_spin.asm`
    and answers this row, so the empty result below is a measurement.
    """
    phantom = RegisterEntry(FIXTURES + "frame_sync_spin.asm", "public", HOME)
    landed = RegisterEntry(FIXTURES + "esai_sync_spin.asm", "public", HOME)
    assert check_register_rows(TREE, [landed], HOME) == []
    failures = check_register_rows(TREE, [phantom, landed], HOME)
    assert len(failures) == 1
    assert FIXTURES + "frame_sync_spin.asm" in failures[0]


def test_a_row_is_only_read_back_in_the_repository_it_is_at_home_in():
    """A row is checked where it lives, and applies where the path turns up.

    Reading it back everywhere would report every `nmg2-artifacts` row against
    `gearmulator`; not reading it back anywhere is the hole this clause fills.
    """
    entries = [
        RegisterEntry(FIXTURES + "no_such_spin.asm", "public", HOME),
        RegisterEntry("README.md", "public", AWAY),
    ]
    assert check_register_rows(TREE, entries, AWAY) == []
    assert len(check_register_rows(TREE, entries, HOME)) == 1


def test_a_pending_row_that_matches_nothing_is_quiet():
    entries = [
        RegisterEntry(FIXTURES + "golden/manifest.txt", "public", HOME,
                      "SCH-40 will generate it"),
        RegisterEntry(FIXTURES + "esai_sync_spin.asm", "public", HOME),
    ]
    assert check_register_rows(TREE, entries, HOME) == []


def test_a_pending_row_stays_quiet_in_a_run_where_another_row_fails():
    """The pending row is not merely masked by a red run; it is not reported.

    A "quiet" that only holds while everything else passes would put the
    forward declaration back in the silent bucket the moment the register had
    a real defect -- which is precisely when it is read.
    """
    entries = [
        RegisterEntry(FIXTURES + "golden/manifest.txt", "public", HOME,
                      "SCH-40 will generate it"),
        RegisterEntry(FIXTURES + "no_such_spin.asm", "public", HOME),
    ]
    failures = check_register_rows(TREE, entries, HOME)
    assert len(failures) == 1
    assert "no_such_spin.asm" in failures[0]
    assert "manifest.txt" not in failures[0]


def test_a_pending_row_that_starts_matching_is_reported():
    """The marker expires by itself, so `pending` is not a hiding place."""
    entries = [RegisterEntry(FIXTURES + "esai_sync_spin.asm", "public", HOME,
                             "SCH-34 will add it")]
    failures = check_register_rows(TREE, entries, HOME)
    assert len(failures) == 1
    assert failures[0].startswith("PAYLOAD-REGISTER-PENDING-SATISFIED: ")
    assert "SCH-34 will add it" in failures[0]


@pytest.mark.parametrize("repo", [None, "axiomantic/not-a-repository"])
def test_an_unidentified_or_unrostered_repository_is_reported(repo):
    entries = [RegisterEntry("README.md", "public", HOME)]
    failures = check_register_rows(TREE, entries, repo)
    assert len(failures) == 1
    assert failures[0].startswith("PAYLOAD-REGISTER-UNCHECKED: ")


def test_a_register_with_no_rows_is_reported():
    failures = check_register_rows(TREE, [], HOME)
    assert len(failures) == 1
    assert failures[0].startswith("PAYLOAD-REGISTER-EMPTY: ")


def test_a_tree_with_no_tracked_files_is_reported():
    """A loop over a vanished scope exits 0 and prints what a clean tree does."""
    entries = [RegisterEntry("README.md", "public", HOME)]
    failures = check_register_rows([], entries, HOME)
    assert len(failures) == 1
    assert failures[0].startswith("PAYLOAD-REGISTER-NO-FILES: ")


def test_a_rostered_repository_no_row_is_at_home_in_is_reported():
    """Otherwise the clause is vacuous there and says so nowhere."""
    entries = [RegisterEntry("README.md", "public", HOME)]
    failures = check_register_rows(TREE, entries, AWAY)
    assert len(failures) == 1
    assert failures[0].startswith("PAYLOAD-REGISTER-NO-HOME-ROWS: ")


# --- The home field is required, rostered, and single for a grant ------------


def test_load_register_rejects_a_row_with_no_home_field(tmp_path):
    path = _register_file(tmp_path, "golden/\tprivate\n")
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert str(caught.value) == (
        f"{path}:1: every row must carry a third, tab-separated `home` field "
        "naming the repositories this row is expected to match a committed "
        "path in, comma-separated: 'golden/\\tprivate'"
    )


def test_load_register_rejects_a_home_outside_the_roster(tmp_path):
    """A typo may not simply move from the path field to the home field."""
    path = _register_file(tmp_path, "golden/\tprivate\taxiomantic/nmg2-tool\n")
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert "unknown home repository 'axiomantic/nmg2-tool'" in str(caught.value)


def test_load_register_rejects_a_repo_scoped_row_naming_two_repositories(
    tmp_path,
):
    """A grant this strong is granted in one place or it is a mistake."""
    path = _register_file(
        tmp_path,
        "PatchTestFiles/\tpublic pch2-exception\t"
        "axiomantic/G2-Edit,axiomantic/mc68k\n",
    )
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert "must carry a third, tab-separated `owner/name` field" in str(
        caught.value
    )


@pytest.mark.parametrize("field", ["pending=", "pending", "SCH-40"])
def test_load_register_rejects_a_malformed_fourth_field(tmp_path, field):
    path = _register_file(
        tmp_path, f"golden/\tprivate\taxiomantic/nmg2-tools\t{field}\n"
    )
    with pytest.raises(RegisterError) as caught:
        load_register(path)
    assert "the fourth field must read `pending=<reason>`" in str(caught.value)


def test_load_register_reads_homes_and_a_pending_reason(tmp_path):
    path = _register_file(
        tmp_path,
        "golden/\tprivate\taxiomantic/nmg2-tools,axiomantic/gearmulator\n"
        "later.bin\tprivate\taxiomantic/gearmulator\tpending=SCH-40 adds it\n",
    )
    entries = load_register(path)
    assert [(e.path, e.homes, e.pending) for e in entries] == [
        ("golden/", ("axiomantic/nmg2-tools", "axiomantic/gearmulator"), None),
        ("later.bin", ("axiomantic/gearmulator",), "SCH-40 adds it"),
    ]
    # A row homed in two places is scoped to neither, so `.repo` -- the ONE
    # repository a grant names -- has no answer for it.
    assert entries[0].repo is None
    assert entries[1].repo == "axiomantic/gearmulator"


# --- The shipped register, held against the roster ---------------------------


def test_every_shipped_row_names_at_least_one_rostered_home():
    entries = load_register(SHIPPED_REGISTER)
    assert entries
    assert [e.path for e in entries if not e.homes] == []
    assert [
        (e.path, slug)
        for e in entries
        for slug in e.homes
        if slug not in KNOWN_REPOSITORIES
    ] == []


def test_every_rostered_repository_has_at_least_one_row_at_home():
    """Otherwise clause 6 examines no row there and reports nothing about it."""
    entries = load_register(SHIPPED_REGISTER)
    homeless = [
        repo
        for repo in KNOWN_REPOSITORIES
        if not any(repo in entry.homes for entry in entries)
    ]
    assert homeless == []


def test_the_shipped_register_is_matched_by_this_repository(tmp_path):
    """Every row at home in `nmg2-tools` matches a path committed here.

    The control plants one broken row into the same population, so the empty
    list above is a measurement of the tree and not of an inert check.
    """
    entries = load_register(SHIPPED_REGISTER)
    committed = _committed_files(REPO_ROOT)
    repo = "axiomantic/nmg2-tools"
    assert check_register_rows(committed, entries, repo) == []
    planted = [*entries, RegisterEntry("no/such/path.bin", "public", repo)]
    assert len(check_register_rows(committed, planted, repo)) == 1


def test_clause_6_does_not_answer_for_clause_2(tmp_path, capsys):
    """A new check that quietly disables an old one is the failure to avoid.

    The planted file is unregistered AND the run is red for clause 6 as well,
    because the scratch tree matches almost no row at home here. Both findings
    must appear.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    subprocess.run(["git", "-C", str(tree), "init", "-q"], check=True)
    (tree / "planted_payload.bin").write_bytes(b"\x00" * 8)
    subprocess.run(
        ["git", "-C", str(tree), "add", "planted_payload.bin"], check=True
    )
    status = main([str(tree), "--repo", "axiomantic/nmg2-tools"])
    assert status == 1
    errors = capsys.readouterr().err.splitlines()
    assert any(
        line.startswith("PAYLOAD-UNREGISTERED: planted_payload.bin:")
        for line in errors
    )
    assert any(line.startswith("PAYLOAD-REGISTER-UNMATCHED: ") for line in errors)


def test_main_reports_a_missing_register_as_a_named_failure(tmp_path, capsys):
    """The most complete way to know nothing gets a name, not a traceback."""
    tree = tmp_path / "tree"
    tree.mkdir()
    subprocess.run(["git", "-C", str(tree), "init", "-q"], check=True)
    status = main(
        [str(tree), "--register", str(tmp_path / "gone.tsv"),
         "--repo", "axiomantic/nmg2-tools"]
    )
    assert status == 1
    assert capsys.readouterr().err.startswith("PAYLOAD-REGISTER-UNREADABLE: ")


# --- The `source` class, and the tree rows that stand next to it -------------
#
# The guard was red on the great majority of every file it saw in five
# repositories, all of it PAYLOAD-UNREGISTERED and none of it a payload-shaped
# clause. Two things were missing, and they are different things.
#
# The class was missing spellings of the argument it already makes: a `.cxx` is
# read line by line in review exactly as a `.cpp` is. The trees were missing a
# DECISION: a vendored copy of wxWidgets is somebody else's code, and saying so
# once per tree is a row, while saying so once per file would be a roster.


@pytest.mark.parametrize(
    "rel",
    [
        "source/dsp56kEmu/asmjit/x86assembler.cxx",
        "src/mcf5307/decode.nim",
        "source/nord/g2/g2Lib/sources_dsp.cmake",
        "source/nord/g2/g2Lib/CMakeLists.txt",
        "CMakeLists.txt",
        "src/misc.mm",
        "include/wx/vector.inl",
        "include/wx/string.hxx",
    ],
)
def test_a_reviewed_source_spelling_needs_no_register_row(tmp_path, rel):
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


@pytest.mark.parametrize("suffix", [".asm", ".inc", ".in", ".m4", ".sln", ".vcproj"])
def test_the_suffixes_held_back_from_the_class_still_need_a_row(tmp_path, suffix):
    """`.asm` is the one that matters, and it is why this test exists.

    A DISASSEMBLY of Clavia firmware is an `.asm` file. The register carries
    three `.asm` fixture rows whose comment establishes, per file, that each is
    a hand-written spin and not disassembled output -- evidence somebody had to
    go and get. Putting `.asm` in the class would have made that paragraph
    unnecessary by making the question unaskable, so the class stops short of
    it and this test is what notices if it ever stops stopping.
    """
    rel = f"source/firmware/dump{suffix}"
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


VENDORED = [RegisterEntry("source/wxWidgets/", "public", "axiomantic/dsp56300")]
DSP = "axiomantic/dsp56300"


def test_a_tree_row_does_not_move_its_source_files_above_the_ceiling(tmp_path):
    """The row is a decision about the tree, not about its source files.

    `Musashi/m68kops.c` is 840,080 bytes and passed the ceiling for as long as
    nothing covered it, because the ceiling exempts the source class. Writing
    `Musashi/` made it fail -- which turned every tree row into a reason not to
    write the row. An unregistered `.cpp` and a registered one now answer the
    same.
    """
    rel = "source/wxWidgets/src/common/filefn.cpp"
    _write(tmp_path / rel, 840_080)
    assert lint_committed_files(tmp_path, [rel], VENDORED, repo=DSP) == []


def test_a_tree_row_keeps_the_ceiling_over_everything_that_is_not_source(tmp_path):
    """The planted control for the exemption above.

    A blob dropped into an exempted vendored tree is still PAYLOAD-CEILING.
    That is the whole reason the tree rows are `public` and never
    `public allow-listed`.
    """
    rel = "source/wxWidgets/src/common/harmless_looking.dat"
    _write(tmp_path / rel, 300_000)
    assert lint_committed_files(tmp_path, [rel], VENDORED, repo=DSP) == [
        f"PAYLOAD-CEILING: {rel}: 300000 bytes exceeds the 65536 byte ceiling "
        "and is not allow-listed"
    ]


def test_a_tree_row_does_not_except_a_pch2_dropped_inside_it(tmp_path):
    """A `public` row is not a `pch2-exception` row, and clause 1 still runs."""
    rel = "source/wxWidgets/docs/gtk/patch.pch2"
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], VENDORED, repo=DSP) == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}"
    ]


def test_a_tree_row_registers_only_the_tree_it_names(tmp_path):
    rel = "source/wxWidgetsExtra/blob.dat"
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], VENDORED, repo=DSP) == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


#: The vendored tree rows carrying `allow-listed`, pinned by name rather than
#: counted. Each one is a tree MEASURED to hold files above the ceiling that
#: were present in upstream's tree at the fork point; the register's own
#: comment carries the per-tree figures. Adding a row to this set reds this
#: test, which is the point: `allow-listed` retires clause 3 over a whole tree
#: and must be a decision someone writes down, never a default a new row
#: inherits.
ALLOW_LISTED_TREES = {
    "source/wxWidgets/",
    "source/portaudio/",
    "source/portmidi/",
    "source/libresample/",
    "source/osTIrusJucePlugin/",
    "source/osirusJucePlugin/",
    "source/mqJucePlugin/",
    "source/xtJucePlugin/",
    "source/jucePluginData/",
    "source/ronaldo/",
    "source/nord/n2x/",
}


def test_the_allow_listed_tree_rows_are_exactly_the_pinned_set():
    """Which vendored trees retire the ceiling, read off the register itself.

    The set above is not the whole roster: `source/fst/`, `source/3rdparty/`,
    `source/HxDplugin/`, `source/vtuneSdk/` and `Musashi/` hold no
    over-ceiling file and stay plain `public`, so the first large blob to
    land in one of them is still PAYLOAD-CEILING. This test pins BOTH
    directions -- a tree gaining `allow-listed` and a tree losing it are each
    a red -- so the split stays a decision and not a drift.

    The `nord/n2x/` row is checked separately for a second reason:
    `source/nord/g2/` is this project's own work and no row may cover it.
    """
    entries = load_register(SHIPPED_REGISTER)
    trees = [
        e
        for e in entries
        if e.is_dir_rule
        and e.homes != ("axiomantic/nmg2-artifacts",)
        and e.path.startswith(("source/", "Musashi/"))
    ]
    assert trees, "no vendored tree rows found; this test would pass vacuously"
    assert {e.path for e in trees if e.allow_listed} == ALLOW_LISTED_TREES
    tight = {e.path for e in trees} - ALLOW_LISTED_TREES
    assert tight, "every vendored tree is allow-listed; clause 3 now says nothing"
    assert [e.path for e in trees if e.is_private] == []
    assert [e.path for e in trees if e.path.startswith("source/nord/g2")] == []


# --- Gitlinks are not files, and the test is the mode ------------------------


def _gitlink_fixture(tmp_path):
    """A repository holding one gitlink, one file, and one decoy.

    The decoy is the control this pair of tests turns on: `SynthLib` is the
    real submodule name from the G2-Edit fork, and `vendor/SynthLib` is a
    REAL FILE sitting at a name that looks exactly like one. A skip list keyed
    on the name would swallow both.
    """
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    _write(tmp_path / "README.md", 10)
    _write(tmp_path / "vendor" / "SynthLib", 10)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "README.md", "vendor/SynthLib"],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(tmp_path), "update-index", "--add", "--cacheinfo",
            "160000," + "0" * 39 + "1,SynthLib",
        ],
        check=True,
    )
    return tmp_path


def test_committed_files_excludes_the_gitlink_and_keeps_the_files(tmp_path):
    """The instrument, held against a gitlink and a file from ONE repository.

    `git ls-files` alone lists all three of these identically. `-s` exposes
    the index mode, and mode 160000 is the whole of the test.
    """
    root = _gitlink_fixture(tmp_path)
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert sorted(listed) == ["README.md", "SynthLib", "vendor/SynthLib"]
    assert sorted(_committed_files(root)) == ["README.md", "vendor/SynthLib"]


def test_a_gitlink_gets_no_unregistered_finding(tmp_path):
    root = _gitlink_fixture(tmp_path)
    failures = lint_repo_tree(
        root, SHIPPED_REGISTER, repo="axiomantic/nmg2-tools"
    )
    assert [f for f in failures if "SynthLib" in f and ": SynthLib:" in f] == []


def test_a_real_file_at_a_submodule_looking_name_still_goes_red(tmp_path):
    """THE PLANTED CONTROL.

    `vendor/SynthLib` is a file, committed at the exact name of a real
    submodule in this set. It has no register row and no by-rule class, so
    clause 2 must still answer for it. If this goes green the filter has
    started keying on names, and the guard has a hole shaped like a naming
    convention.
    """
    root = _gitlink_fixture(tmp_path)
    failures = lint_repo_tree(
        root, SHIPPED_REGISTER, repo="axiomantic/nmg2-tools"
    )
    assert (
        "PAYLOAD-UNREGISTERED: vendor/SynthLib: committed file with no "
        "register row and no by-rule classification"
    ) in failures


def test_index_entries_reports_the_mode_git_reports(tmp_path):
    root = _gitlink_fixture(tmp_path)
    modes = {path: mode for mode, path in index_entries(root)}
    assert modes["SynthLib"] == GITLINK_MODE
    assert modes["vendor/SynthLib"] != GITLINK_MODE
    assert modes["README.md"] != GITLINK_MODE


def test_a_path_holding_a_tab_survives_the_listing(tmp_path):
    """Why the listing asks for `-z`.

    Without it git quotes such a path and the tab-split below would read the
    quoting as data -- a path silently renamed on its way into the guard.
    """
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    awkward = "odd\tname.bin"
    _write(tmp_path / awkward, 10)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "--", awkward], check=True
    )
    assert _committed_files(tmp_path) == [awkward]


# --- What a register row does and does not assert about a gitlink -----------
#
# A directory row may sit above a submodule gitlink. In `gearmulator` the
# `source/3rdparty/` row does exactly that: it covers 66 committed files and
# three gitlinks (`RmlUi`, `freetype`, `lunasvg`). Those three were silent
# before the mode filter landed, absorbed by a row that legitimately covers
# the 66 -- so the true false-positive population was larger than the visible
# findings, and no clause said so.
#
# Reporting that coverage was considered and REJECTED. The register asserts
# the provenance of BYTES IN THIS REPOSITORY, and a gitlink has none here; its
# content lives in another repository, where `submodule_lint` owns it entirely
# -- the URL authority table, `SUBMODULE-UNDECLARED` for a gitlink no section
# declares, and `SUBMODULE-STALE-DECLARATION` for the reverse. Every gitlink
# in a tree therefore reaches a named check that goes red, and it does so
# without the register. A finding here would fire three times on `gearmulator`
# for a non-defect, and its only remedy would be to narrow or not write the
# `source/3rdparty/` row -- pressure against writing register rows, which this
# module names as the one thing the register must never create.
#
# What keeps the register HONEST instead is clause 6, and the property is a
# consequence of the mode filter rather than a rule written anywhere: rows are
# matched against `_committed_files`, which excludes gitlinks, so a row whose
# only would-be matches are gitlinks matches nothing and is reported. The two
# tests below pin that. It arrived as a side effect and nothing held it, so a
# later change to either the population or `matches` could restore the hole in
# silence.


def _gitlink_only_subtree(tmp_path):
    """A repository where `vendor/` holds ONLY gitlinks, and `lib/` holds both."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    _write(tmp_path / "lib" / "payload.bin", 10)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "lib/payload.bin"], check=True
    )
    for gitlink in ("vendor/RmlUi", "lib/freetype"):
        subprocess.run(
            [
                "git", "-C", str(tmp_path), "update-index", "--add",
                "--cacheinfo", "160000," + "0" * 39 + "1," + gitlink,
            ],
            check=True,
        )
    return tmp_path


def test_a_row_whose_only_subtree_entries_are_gitlinks_is_unmatched(tmp_path):
    """THE HONESTY PROPERTY, and the load-bearing test of this pair.

    An operator who writes `vendor/` believing they have registered the
    submodule beneath it has registered nothing, and must be told so. If this
    goes green, a register row can assert a provenance that no committed byte
    answers for, which is precisely the defect clause 6 exists to end.
    """
    root = _gitlink_only_subtree(tmp_path)
    register = _register_file(
        tmp_path, "vendor/\tpublic\taxiomantic/nmg2-tools\n"
    )
    failures = lint_repo_tree(
        root, register, repo="axiomantic/nmg2-tools"
    )
    assert [
        f for f in failures if f.startswith("PAYLOAD-REGISTER-UNMATCHED")
    ] == [
        "PAYLOAD-REGISTER-UNMATCHED: vendor/: this row is at home in "
        "axiomantic/nmg2-tools and matches no committed path there, so it "
        "registers nothing. Correct the path, or mark the row "
        f"`{PENDING_PREFIX}<reason>` if the file is yet to land"
    ]


def test_a_row_covering_files_and_a_gitlink_is_matched_and_silent(tmp_path):
    """The known negative, and the `source/3rdparty/` shape in miniature.

    `lib/` covers one committed file and one gitlink. The row is matched by
    the file, and the gitlink beneath it draws no finding of its own. This is
    the DELIBERATE answer, not an oversight: see the note above this block.
    """
    root = _gitlink_only_subtree(tmp_path)
    register = _register_file(
        tmp_path, "lib/\tpublic\taxiomantic/nmg2-tools\n"
    )
    failures = lint_repo_tree(
        root, register, repo="axiomantic/nmg2-tools"
    )
    assert [f for f in failures if "freetype" in f] == []
    assert [
        f for f in failures if f.startswith("PAYLOAD-REGISTER-UNMATCHED")
    ] == []


# --- The residual backlog's predicates ----------------------------------------
# Three predicates closed 19 of the 67 findings that remained after the
# vendored-tree rows. Each one WIDENS the class, so each one gets a known
# positive (the file it was written for goes quiet) AND a known negative (the
# nearest payload-shaped spelling still goes red). A widening tested only by
# its known positive cannot tell a class from a hole.


@pytest.mark.parametrize(
    "rel",
    [
        "build_win64.bat",
        "deploy/win/start_Impact__MS.bat",
        "source/build_win32.bat",
    ],
)
def test_a_windows_batch_script_needs_no_register_row(tmp_path, rel):
    """`.sh` has always been in the class; `.bat` is the same thing for cmd.exe.

    Excluding the Windows spelling was an omission, not a decision, and these
    are three of the nine real files it left unanswered.
    """
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


@pytest.mark.parametrize(
    "rel",
    [
        "source/jucePluginLib/version.h.in",
        "source/skins.h.in",
        "source/synthLib/buildconfig.h.in",
    ],
)
def test_a_configure_template_of_a_source_header_needs_no_register_row(
    tmp_path, rel
):
    """The `.in` STEM rule: `version.h.in` is a `.h` with placeholders in it."""
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


@pytest.mark.parametrize(
    "rel",
    [
        "source/firmware/dump.bin.in",
        "source/firmware/dump.asm.in",
        "source/firmware/dump.inc.in",
        "source/firmware/patches.pch2.in",
        "source/macsetup.command.in",
        "source/portaudio/Makefile.in",
        "source/libresample/configure.in",
    ],
)
def test_the_template_rule_inherits_from_the_stem_and_invents_nothing(
    tmp_path, rel
):
    """THE LOAD-BEARING TEST OF THE `.in` RULE, and the reason it is admissible.

    A BLANKET `.in` class was refused, and this rule is not that class. The
    exemption is INHERITED FROM THE STEM or it does not exist, so a template
    can never be a way to put a refused suffix past this check: `dump.bin.in`
    reads as `.bin` and `dump.asm.in` reads as `.asm`, and both are still
    PAYLOAD-UNREGISTERED. If this test goes green while the previous one does
    too, the rule has become the blanket class it was written to avoid.
    """
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


@pytest.mark.parametrize(
    "rel",
    [
        "CMakePresets.json",
        "source/.clang-format",
        "uncrustify.cfg",
        ".nim-version",
        "nested/dir/CMakePresets.json",
    ],
)
def test_a_fixed_tool_defined_filename_needs_no_register_row(tmp_path, rel):
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


@pytest.mark.parametrize(
    "rel",
    [
        # The file the `.json` suffix class would have swallowed: 297,564
        # bytes of Clavia-derived module metadata. The basename predicate
        # cannot reach it, and that is why it is a basename.
        "g2demo/g2_modules.json",
        "conformance/presets.json",
        "source/firmware/dump.cfg",
        "source/firmware/dump.clang-format",
        "source/firmware/version.txt",
    ],
)
def test_the_basename_predicate_does_not_widen_into_a_suffix_class(
    tmp_path, rel
):
    """The known negative for the fixed-name predicate.

    A basename is the narrowest thing this module can say. It cannot be
    reached by choosing a suffix or a directory, only by naming the file the
    thing the tool actually reads -- so `presets.json` next to
    `CMakePresets.json` is still a finding, and so is `dump.cfg` next to
    `uncrustify.cfg`.
    """
    _write(tmp_path / rel, 10)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == [
        f"PAYLOAD-UNREGISTERED: {rel}: committed file with no register row and "
        "no by-rule classification"
    ]


def test_a_batch_script_above_the_ceiling_passes_and_that_is_the_price(
    tmp_path,
):
    """THE REACH THIS PASS GAVE UP, WRITTEN DOWN AS A GREEN TEST.

    A `.bat` is now `source`, and the ceiling does not police source. So a
    360 KB batch file with a base64 blob pasted into it passes, where before
    this change it was PAYLOAD-UNREGISTERED at any size. That is exactly the
    trade `.sh` has always made, and it is bounded: it buys nothing for clause
    1, so a `.pch2` beside it is still refused, and it buys nothing for any
    other spelling. If this bound is ever thought too generous, the fix is to
    drop `.bat` from the class and write nine rows -- not to weaken this test.
    """
    rel = "scripts/build.bat"
    _write(tmp_path / rel, 360_000)
    assert lint_committed_files(tmp_path, [rel], CLASS_REGISTER) == []


def test_the_register_reads_a_row_whose_path_holds_spaces(tmp_path):
    """`G2-Edit` carries three of these, and the tab format is what saves them.

    `load_register` falls back to splitting on whitespace ONLY when a line
    yields fewer than two tab-separated fields. A row written with real tabs
    therefore keeps its spaces, and the fallback -- which would read
    `G2 Editor.xcodeproj/` as a path of `G2` -- never runs.
    """
    register = _register_file(
        tmp_path,
        "G2 Editor.xcodeproj/\tpublic\taxiomantic/G2-Edit\n"
        "Module dev debug notes.txt\tpublic\taxiomantic/G2-Edit\n",
    )
    entries = load_register(register)
    assert [entry.path for entry in entries] == [
        "G2 Editor.xcodeproj/",
        "Module dev debug notes.txt",
    ]
    assert entries[0].matches("G2 Editor.xcodeproj/project.pbxproj")
    assert entries[1].matches("Module dev debug notes.txt")


def test_the_shipped_register_still_refuses_the_suffixes_it_held_back():
    """The refusal is a property of the SHIPPED module, not of a fixture.

    The parametrized test above proves the classifier refuses these spellings.
    This one proves nobody quietly added one to the shipped sets while doing
    so, which is the edit that would make that test's fixture lie.
    """
    for suffix in (".asm", ".inc", ".sln", ".vcxproj", ".vcproj", ".filters",
                   ".m4", ".am", ".cfg", ".html", ".js", ".txt", ".def",
                   ".yml", ".yaml", ".json", ".png", ".bin", ".in"):
        assert suffix not in SOURCE_SUFFIXES, suffix
    assert "uncrustify.cfg" in SOURCE_BASENAMES
    assert ".bat" in SOURCE_SUFFIXES
