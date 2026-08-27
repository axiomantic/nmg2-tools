import os
import subprocess
import sys
from pathlib import Path

import pytest

from nmg2_tools.payload_lint import (
    PCH2_ALLOWED_DIR,
    SHIPPED_REGISTER,
    RegisterError,
    RegisterEntry,
    lint_committed_files,
    REPO_SCOPED_VISIBILITIES,
    _committed_files,
    load_register,
    main,
)

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
        "nmg2_tools/testdata/pch2_synth/\tpublic\n"
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
    """`--register` defaults to the shipped file wherever the tool is run."""
    tree = tmp_path / "tree"
    tree.mkdir()
    subprocess.run(["git", "-C", str(tree), "init", "-q"], check=True)
    monkeypatch.chdir(tmp_path)
    status = main([str(tree), "--repo", "axiomantic/nmg2-tools"])
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
