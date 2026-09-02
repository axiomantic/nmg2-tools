"""The `.pch2` parser against the G2 Demo corpus, the T1 half.

THIS TEST RUNS ON EVERY `.pch2` FILE OF THE G2 DEMO CORPUS, which lives at
`corpus/pch2/` in `axiomantic/nmg2-artifacts` and is reached through
`NMG2_ARTIFACTS`. It is INFORMATIONAL by tier: it skips with the standard
reason where the artifact is unreachable, and a regression here does NOT block
a merge.

THE COUNT IS ASSERTED AGAINST `corpus/pch2/MANIFEST.txt`, NEVER AGAINST A
NUMBER WRITTEN HERE. A test that carried the count itself could not detect a
manifest that disagreed with the tree -- a manifest that disagrees with the
tree is exactly the failure this half exists to find. This file states no
count.

WHAT A GREEN RUN HERE PROVES, AND WHAT IT DOES NOT. It proves the parser reads
every real patch in the corpus byte for byte. That is the coverage the T0 half
cannot claim. A construct a real patch uses that the specification does not
describe passes T0 and FAILS HERE, and because this tier is informational the
failure is a signal to extend the parser rather than a block on a merge.
"""

import pathlib

import pytest

from nmg2_tools import pch2
from nmg2_tools.artifacts import (
    gated_skip_reason,
    resolve_artifacts,
)

# The corpus path: `corpus/pch2/` under the artifacts root. This is not a count, and it is not the thing the test must
# not hardcode.
CORPUS_REL = pathlib.Path("corpus") / "pch2"
MANIFEST_REL = CORPUS_REL / "MANIFEST.txt"


@pytest.fixture(scope="module")
def demo_corpus_dir() -> pathlib.Path:
    """The resolved corpus directory, or a skip.

    An artifact-gated test that cannot run must skip WITH A REASON and must
    never pass silently. The
    standard reason comes from `gated_skip_reason()` and applies whenever the
    artifacts root is unreachable. A root that exists but does not hold the
    corpus is skipped with a second, distinct reason rather than failing, so
    that the informational tier stays green on machines without the private
    corpus.

    Both reasons come from `gated_skip_reason()`, which gates on the files the
    body opens, so the manifest is stated as a required path rather than
    checked here with a message of this module's own. A hand-built message here
    would be message 3 spelled a second time, and a message with two
    texts is a message with two meanings."""
    reason = gated_skip_reason(str(MANIFEST_REL))
    if reason is not None:
        pytest.skip(reason)

    base, _why = resolve_artifacts()

    return pathlib.Path(base) / CORPUS_REL


def _patches(corpus: pathlib.Path) -> list[pathlib.Path]:
    """Every `.pch2` file flat in the corpus directory."""
    return sorted(path for path in corpus.iterdir() if path.suffix == ".pch2")


def _manifest(corpus: pathlib.Path) -> tuple[int, list[str]]:
    """The manifest: first line is the count, then one row per file."""
    lines = (corpus / "MANIFEST.txt").read_text().splitlines()
    return int(lines[0]), lines[1:]


def test_every_demo_patch_parses(demo_corpus_dir):
    """The parser reads each real patch byte for byte and raises nothing.

    This is the coverage claim the T0 half is forbidden from making: a green
    run here proves the parser accepts every real patch in the corpus."""
    corpus = demo_corpus_dir
    for path in _patches(corpus):
        pch2.parse(path.read_bytes())


def test_the_accepted_object_types_are_exactly_the_ones_real_patches_carry(
    demo_corpus_dir,
):
    """The parser's accepted type set, held against bytes the synthesizer did
    not write.

    This is the assertion the T0 half CANNOT make. The synthesized corpus is
    written from the same type set the parser reads, so a T0 sweep agrees with
    the parser whatever that set holds. Real patches were written by a device
    that has never seen this repository, so the census below can disagree, and
    equality makes it disagree in both directions: a code a real patch carries
    and the parser refuses raises out of `parse`, and a code the parser accepts
    that no real patch carries -- an invented one -- fails the comparison."""
    corpus = demo_corpus_dir

    seen: set[int] = set()
    for path in _patches(corpus):
        seen.update(obj.type for obj in pch2.parse(path.read_bytes()).objects)

    assert sorted(seen) == sorted(pch2.ACCEPTED_OBJECT_TYPES)


def test_the_patch_count_matches_the_manifest(demo_corpus_dir):
    """The count is taken from the manifest's first line and compared with the
    tree. A manifest row count that disagrees with the directory -- in either
    direction -- fails here. No number is written in this file."""
    corpus = demo_corpus_dir
    count, rows = _manifest(corpus)

    assert count == len(rows)
    assert count == len(_patches(corpus))


def test_every_manifest_row_names_an_existing_patch(demo_corpus_dir):
    """Manifest rows are `<path inside the installer><tab><size><tab>
    <digest>`, and the extractor writes every file FLAT into `corpus/pch2/`.

    So the row's path and the tree's path differ by design, in the one component
    the extraction drops: the installer directory. The row is read for its
    BASENAME, which is what the corpus carries, and the two sets are compared
    WHOLE. Equality rather than membership, so the comparison fails in both
    directions -- a row naming a patch the tree does not hold, and a patch in
    the tree that no row names.

    The installer directory is NOT asserted here. A test that spelled it would
    be the hardcoded-figure defect this module's header refuses for the count,
    wearing a path's clothes."""
    corpus = demo_corpus_dir
    _count, rows = _manifest(corpus)

    listed = {pathlib.PurePosixPath(row.split("\t", 1)[0]).name for row in rows}
    present = {path.name for path in _patches(corpus)}

    assert listed == present
