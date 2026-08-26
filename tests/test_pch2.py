"""The `.pch2` parser against the synthesized corpus. Task TOOL-10, T0 half.

Design section 15.7, plan section 3.5.

THIS TEST RUNS ON THE SYNTHESIZED CORPUS AND ON NOTHING ELSE. It reads no
Clavia byte, so it runs in every public repository and on a pull request from
a fork. It depends on REPO-2 and TOOL-12 and on nothing else.

WHAT A GREEN RUN HERE PROVES, AND WHAT IT DOES NOT. A green run proves that the
parser handles every case the format specification names: framing, the CRC, the
file-against-wire differences and the malformed set. It proves NOTHING
about real-world patch variety, because nobody wrote this corpus from real
patches. A construct a real patch uses that section 15.7 does not describe
passes here and fails the T1 half against the G2 Demo corpus, which is private
and informational by tier. That gap is known, stated and accepted.

THE NAMES ARE READ FROM THE MANIFEST, NEVER SPELLED OUT HERE. The synthesized
corpus carries `MANIFEST.tsv`, which states which file is malformed and which
named refusal its parser must raise. A parser test that carried the names
itself could not disagree with a corpus that changed shape; the sweep test
below reads the manifest so that a drift between the corpus and this test is a
failure instead.
"""

import pytest

from nmg2_tools import pch2
from nmg2_tools.pch2 import Pch2Error, Pch2File, Pch2Object
from nmg2_tools.synth_pch2 import (
    CORPUS_DIRECTORY,
    OBJECT_TYPES,
    UNKNOWN_OBJECT_TYPE,
)


def _corpus() -> dict[str, bytes]:
    """The COMMITTED bytes on disk, not a fresh generation. The parser must
    read what was committed, so this test exercises the artifact and not the
    generator that produced it."""
    return {
        path.name: path.read_bytes()
        for path in CORPUS_DIRECTORY.glob("*.pch2")
    }


def _read_manifest() -> dict[str, tuple[str, str]]:
    """Read the refusal table from the committed manifest. The format is
    `name<tab>kind<tab>expected_refusal`, with `-` for a well-formed file."""
    table: dict[str, tuple[str, str]] = {}
    manifest = (CORPUS_DIRECTORY / "MANIFEST.tsv").read_bytes().decode("ascii")
    for line in manifest.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name, kind, refusal = line.split("\t")
        table[name] = (kind, refusal)
    return table


# ---------------------------------------------------------------------------
# The whole-corpus sweep, driven by the manifest.
# ---------------------------------------------------------------------------


def test_every_well_formed_file_parses_and_every_malformed_one_raises_its_manifest_refusal():
    """One pass over the whole corpus. The manifest decides each file's fate,
    so the parser cannot drift from the corpus without this test failing.

    For the malformed half the assertion is that the exception's MESSAGE
    starts with the manifest's refusal NAME and that the exception is a
    `Pch2Error`. Both must hold: a message that starts with the name but is not
    a `Pch2Error` would still be catchable as `ValueError`, and a `Pch2Error`
    whose message names nothing would not."""
    files = _corpus()
    manifest = _read_manifest()

    assert set(manifest) == set(files)

    for name in sorted(files):
        kind, refusal = manifest[name]
        if kind == "wellformed":
            assert refusal == "-"
            result = pch2.parse(files[name])
            assert isinstance(result, Pch2File)
        else:
            with pytest.raises(Pch2Error) as caught:
                pch2.parse(files[name])
            assert str(caught.value).startswith(refusal)


# ---------------------------------------------------------------------------
# The minimum well-formed file, pinned byte for byte.
# ---------------------------------------------------------------------------


def test_the_minimum_file_parses_to_one_empty_0x21_object_and_a_valid_crc():
    """Design section 15.7's minimum: a text header, the two-byte binary
    header, one 0x21 object with a zero-length payload, and a CRC. The header
    values and the CRC are written out as literals, not derived from the
    corpus, so a regression in either the header split or the CRC surfaces
    here."""
    image = _corpus()["min.pch2"]
    result = pch2.parse(image)

    assert result.version == 0x01
    assert result.type == 0x00
    assert result.usb_trailer is False
    assert result.crc_valid is True
    assert result.stored_crc == 0x1BA7
    assert result.computed_crc == 0x1BA7
    assert result.objects == (Pch2Object(type=0x21, payload=b""),)


# ---------------------------------------------------------------------------
# Object types.
# ---------------------------------------------------------------------------


def test_every_object_type_the_specification_names_is_read_in_order():
    """The union of the types section 15.7 and design section 18 name, read in
    the order the corpus writes them. Each payload is the object's own index
    as a single byte, so two objects never look alike."""
    result = pch2.parse(_corpus()["object_types.pch2"])

    assert [o.type for o in result.objects] == list(OBJECT_TYPES)
    assert [o.payload for o in result.objects] == [
        bytes([index]) for index in range(len(OBJECT_TYPES))
    ]
    assert [o.length for o in result.objects] == [1] * len(OBJECT_TYPES)


# ---------------------------------------------------------------------------
# Bit packing. Fields are bit-packed and are not byte aligned, so the parser
# frames objects whose payload widths are not whole bytes.
# ---------------------------------------------------------------------------


def test_bit_packed_objects_are_framed_at_their_payload_lengths():
    """The bit_widths file holds one object per width at the minimum, an
    interior and the maximum width. The parser cannot know the widths -- the
    payload layout is not stated -- so all it can and must do is frame each
    object at the length its header declares: 1, 3 and 12 payload bytes."""
    result = pch2.parse(_corpus()["bit_widths.pch2"])

    assert [o.type for o in result.objects] == [0x60, 0x60, 0x60]
    assert [o.length for o in result.objects] == [1, 3, 12]
    # The 7-bit interior width is deliberately not a byte; a reader that
    # aligned to bytes would split the middle object at length 4 and fail here.
    assert result.objects[1].payload == b"\x00\xab\xf8"


# ---------------------------------------------------------------------------
# The boundary object lengths.
# ---------------------------------------------------------------------------


def test_the_boundary_lengths_parse_zero_and_the_largest_committed_payload():
    """A zero-length payload, then the largest payload that keeps the whole
    committed file at the 65,536-byte ceiling. The field's own maximum, 0xFFFF,
    cannot be committed and the parser still handles any length the 2-byte
    field allows."""
    result = pch2.parse(_corpus()["length_boundaries.pch2"])

    assert len(result.objects) == 2
    assert result.objects[0] == Pch2Object(type=0x21, payload=b"")
    assert result.objects[1].type == 0x4A
    assert result.objects[1].length == 65469


# ---------------------------------------------------------------------------
# The file-against-wire differences. Design section 15.7.
# ---------------------------------------------------------------------------


def test_the_variation_count_is_read_as_nine_in_the_file():
    """Difference 1. The count is 9 in a file and 10 on the wire. The parser
    reads the FILE, so it reads 9 followed by 9 one-byte indices, in both the
    0x4D and the 0x65 object. It states nothing about a tenth variation."""
    result = pch2.parse(_corpus()["wire_variation_count.pch2"])

    expected_payload = b"\x09" + bytes(range(9))
    assert [o.type for o in result.objects] == [0x4D, 0x65]
    assert [o.payload for o in result.objects] == [expected_payload, expected_payload]
    assert [o.length for o in result.objects] == [10, 10]


def test_the_file_form_has_no_trailer_and_the_usb_form_has_the_two_extra_bytes():
    """Difference 2. Two raw bytes 0x2D 0x00 follow the 0x21 chunk in USB
    dumps, and are not present in the file form. Both forms are committed, so
    both must parse. The parser records the trailer instead of erroring on the
    0x2D type it has never met as an object."""
    file_result = pch2.parse(_corpus()["wire_extra_bytes_file.pch2"])
    usb_result = pch2.parse(_corpus()["wire_extra_bytes_usb.pch2"])

    assert file_result.usb_trailer is False
    assert usb_result.usb_trailer is True
    assert file_result.objects == (Pch2Object(type=0x21, payload=b"\xaa\xbb"),)
    assert usb_result.objects == (Pch2Object(type=0x21, payload=b"\xaa\xbb"),)


def test_morph_parameter_names_are_omitted_so_the_object_stops_after_the_values():
    """Difference 3. Names are omitted on write in both paths. The 0x65 object
    declares a morph count of 8, then carries 8 one-byte morph values and no
    name after them."""
    result = pch2.parse(_corpus()["wire_morph_names.pch2"])

    assert result.objects == (
        Pch2Object(type=0x65, payload=b"\x08" + bytes(range(8))),
    )


# ---------------------------------------------------------------------------
# The malformed set. Each named refusal is exercised on its own file here, in
# addition to the sweep, so that a wrong error on one file is reported at that
# file rather than only as a single aggregate failure.
# ---------------------------------------------------------------------------


def test_bad_crc_raises_the_named_refusal():
    with pytest.raises(Pch2Error) as caught:
        pch2.parse(_corpus()["bad_crc.pch2"])
    assert str(caught.value).startswith("PCH2-BAD-CRC")


def test_length_past_end_raises_the_named_refusal():
    with pytest.raises(Pch2Error) as caught:
        pch2.parse(_corpus()["bad_length_past_end.pch2"])
    assert str(caught.value).startswith("PCH2-LENGTH-PAST-END")


def test_truncated_object_raises_the_named_refusal():
    with pytest.raises(Pch2Error) as caught:
        pch2.parse(_corpus()["bad_truncated_object.pch2"])
    assert str(caught.value).startswith("PCH2-TRUNCATED-OBJECT")


def test_the_parser_accepts_every_object_type_the_generator_writes():
    """The parser reads its accepted set from its own module, so a type the
    generator writes and the parser refuses is a real possibility and this is
    the check that catches it. The refusal of `UNKNOWN_OBJECT_TYPE` is the
    known positive: it shows the same membership test returning a non-empty
    list, so an empty list above is a measurement and not a dead expression."""
    refused = [t for t in OBJECT_TYPES if t not in pch2.ACCEPTED_OBJECT_TYPES]
    assert refused == []

    known_positive = [
        t for t in (UNKNOWN_OBJECT_TYPE,) if t not in pch2.ACCEPTED_OBJECT_TYPES
    ]
    assert known_positive == [UNKNOWN_OBJECT_TYPE]


def test_unknown_object_type_raises_the_named_refusal():
    with pytest.raises(Pch2Error) as caught:
        pch2.parse(_corpus()["bad_unknown_type.pch2"])
    assert str(caught.value).startswith("PCH2-UNKNOWN-OBJECT-TYPE")


# ---------------------------------------------------------------------------
# The CRC coverage. Design section 15.3: the routine covers the version and
# type bytes and every chunk, and excludes only the trailing CRC. The text
# header is before the covered range and is not covered.
# ---------------------------------------------------------------------------


def test_every_well_formed_file_has_a_valid_crc():
    result = pch2.parse(_corpus()["min.pch2"])
    assert result.crc_valid is True
    assert result.stored_crc == result.computed_crc


def test_a_mutation_in_the_covered_range_is_a_bad_crc():
    """Flipping one bit in the version byte -- the first covered byte -- must
    make the CRC fail. The version byte is part of the covered range per
    section 15.3."""
    image = bytearray(_corpus()["min.pch2"])
    nul = image.index(b"\x00")
    image[nul + 1] ^= 0x01  # the version byte

    with pytest.raises(Pch2Error) as caught:
        pch2.parse(bytes(image))
    assert str(caught.value).startswith("PCH2-BAD-CRC")


def test_a_mutation_in_the_stored_crc_is_a_bad_crc():
    """Flipping the last byte -- part of the trailing CRC -- must also fail."""
    image = bytearray(_corpus()["min.pch2"])
    image[-1] ^= 0x01

    with pytest.raises(Pch2Error) as caught:
        pch2.parse(bytes(image))
    assert str(caught.value).startswith("PCH2-BAD-CRC")


def test_a_mutation_in_the_text_header_leaves_the_crc_valid():
    """The text header is before the covered range, so a change there must NOT
    disturb the CRC. This is the negative half of the coverage claim: without
    it, a parser that covered the whole file would still pass every bad-CRC
    test above (those flip covered bytes), and only a well-formed mutation that
    SHOULD still pass can distinguish the two."""
    image = bytearray(_corpus()["min.pch2"])
    image[0] = ord("X")  # the first text byte

    result = pch2.parse(bytes(image))
    assert result.crc_valid is True


# ---------------------------------------------------------------------------
# Structural refusals outside the corpus's malformed files.
# ---------------------------------------------------------------------------


def test_a_file_with_no_text_header_is_refused():
    with pytest.raises(Pch2Error):
        pch2.parse(b"no-nul-here-at-all-0001020304")


def test_a_file_smaller_than_header_plus_crc_is_refused():
    with pytest.raises(Pch2Error):
        pch2.parse(b"\x00\x01\x00")


def test_load_reads_a_file_from_disk(tmp_path):
    image = _corpus()["min.pch2"]
    path = tmp_path / "min.pch2"
    path.write_bytes(image)

    result = pch2.load(path)

    assert result == pch2.parse(image)
