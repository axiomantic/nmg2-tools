import hashlib

from nmg2_tools.extract_demo_corpus import extract, find_pch2_files


def _make_source_tree(tmp_path):
    source = tmp_path / "installer"
    (source / "patches").mkdir(parents=True)
    (source / "other").mkdir(parents=True)

    (source / "patches" / "alpha.pch2").write_bytes(b"alpha-placeholder")
    (source / "patches" / "beta.pch2").write_bytes(b"beta-placeholder")
    (source / "gamma.pch2").write_bytes(b"gamma-placeholder")
    (source / "other" / "readme.txt").write_bytes(b"not a patch")
    (source / "other" / "notes.pch2x").write_bytes(b"not a pch2 either")

    return source


def test_walk_finds_exactly_three_pch2_files(tmp_path):
    source = _make_source_tree(tmp_path)
    found = find_pch2_files(source)
    assert len(found) == 3
    assert all(p.name.endswith(".pch2") for p in found)


def test_manifest_first_line_agrees_with_count(tmp_path):
    source = _make_source_tree(tmp_path)
    dest = tmp_path / "out"

    manifest_path = extract(source, dest)

    lines = manifest_path.read_text().splitlines()
    assert int(lines[0]) == 3
    assert len(lines) == 1 + 3

    pch2_dir = dest / "corpus" / "pch2"
    copied = sorted(p.name for p in pch2_dir.iterdir() if p.name != "MANIFEST.txt")
    assert copied == ["alpha.pch2", "beta.pch2", "gamma.pch2"]


def test_manifest_is_written_beside_the_copied_patches(tmp_path):
    """The manifest is written inside `corpus/pch2/`, beside the copied patches."""
    source = _make_source_tree(tmp_path)
    dest = tmp_path / "out"

    manifest_path = extract(source, dest)

    assert manifest_path == dest / "corpus" / "pch2" / "MANIFEST.txt"
    assert manifest_path.is_file()
    # Writing the old location as well would leave a second, stale manifest
    # that nothing keeps in step with the copied patches.
    assert not (dest / "corpus" / "MANIFEST.txt").exists()


def test_manifest_records_relative_path_size_and_digest_for_every_file(tmp_path):
    source = _make_source_tree(tmp_path)
    dest = tmp_path / "out"

    manifest_path = extract(source, dest)

    def row(rel: str, payload: bytes) -> str:
        return f"{rel}\t{len(payload)}\t{hashlib.sha256(payload).hexdigest()}"

    assert manifest_path.read_text() == (
        "3\n"
        + row("gamma.pch2", b"gamma-placeholder")
        + "\n"
        + row("patches/alpha.pch2", b"alpha-placeholder")
        + "\n"
        + row("patches/beta.pch2", b"beta-placeholder")
        + "\n"
    )
