from pathlib import Path

from nmg2_tools.payload_lint import RegisterEntry, lint_committed_files, load_register

REGISTER = [
    RegisterEntry("nmg2_tools/testdata/pch2_synth/", "public"),
    RegisterEntry("g2Lib/test/fixtures/synthetic_block_program.asm", "public"),
    RegisterEntry("conformance/corpus/", "public allow-listed"),
    RegisterEntry("golden/", "private"),
    RegisterEntry("PatchTestFiles/", "public pch2-exception"),
    RegisterEntry("testdata/PatchTestFiles/", "public pch2-exception"),
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
