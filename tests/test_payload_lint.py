from pathlib import Path

from nmg2_tools.payload_lint import (
    PCH2_ALLOWED_DIR,
    RegisterEntry,
    lint_committed_files,
    load_register,
)

REGISTER = [
    RegisterEntry("nmg2_tools/testdata/pch2_synth/", "public"),
    RegisterEntry("g2Lib/test/fixtures/synthetic_block_program.asm", "public"),
    RegisterEntry("conformance/corpus/", "public allow-listed"),
    RegisterEntry("golden/", "private"),
    RegisterEntry("PatchTestFiles/", "public pch2-exception"),
    RegisterEntry("testdata/PatchTestFiles/", "public pch2-exception"),
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


def test_unregistered_pch2_in_private_repo_passes(tmp_path):
    """A private repository is not the place clause 1 polices, registered or not."""
    rel = "some/other/place.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], REGISTER, visibility="private")
    assert failures == []


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
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert failures == []


def test_pch2_exception_row_grants_no_size_exemption(tmp_path):
    rel = "testdata/PatchTestFiles/InheritedBig.pch2"
    _write(tmp_path / rel, 65_537)
    failures = lint_committed_files(tmp_path, [rel], REGISTER)
    assert any(f.startswith("PAYLOAD-CEILING") for f in failures)


def test_shipped_register_has_exactly_one_pch2_exception_row():
    register_path = Path("nmg2_tools/testdata/register.tsv")
    entries = load_register(register_path)
    exception_entries = [e for e in entries if e.pch2_excepted]
    assert len(exception_entries) == 1
    assert exception_entries[0].path == "PatchTestFiles/"


# --- The pch2 exception is scoped to ONE repository -------------------------
#
# The register is a single file shared by all seven repositories. An
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
    """A directory merely NAMED `PatchTestFiles` in another repository fails."""
    rel = "PatchTestFiles/Smuggled.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(
        tmp_path, [rel], SCOPED_REGISTER, repo="axiomantic/mc68k"
    )
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}"
    ]


def test_pch2_exception_does_not_apply_when_no_repository_is_supplied(tmp_path):
    """Fail closed: an unidentified repository gets no scoped exception."""
    rel = "PatchTestFiles/Smuggled.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(tmp_path, [rel], SCOPED_REGISTER, repo=None)
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}"
    ]


def test_scoped_exception_does_not_widen_to_other_paths_in_its_own_repo(tmp_path):
    """The grant covers its own path only, not every `.pch2` in G2-Edit."""
    rel = "src/Sneaky.pch2"
    _write(tmp_path / rel, 10)
    failures = lint_committed_files(
        tmp_path, [rel], SCOPED_REGISTER, repo="axiomantic/G2-Edit"
    )
    assert failures == [
        f"PAYLOAD-PCH2-LOCATION: {rel}: .pch2 file outside {PCH2_ALLOWED_DIR}"
    ]


def test_shipped_register_pch2_exception_row_is_scoped_to_g2_edit():
    entries = load_register(Path("nmg2_tools/testdata/register.tsv"))
    exception_entries = [e for e in entries if e.pch2_excepted]
    assert len(exception_entries) == 1
    assert exception_entries[0].path == "PatchTestFiles/"
    assert exception_entries[0].repo == "axiomantic/G2-Edit"
