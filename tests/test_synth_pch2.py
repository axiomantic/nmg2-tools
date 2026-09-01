"""The synthesized `.pch2` corpus.

EVERY BYTE OF THIS CORPUS IS AUTHORED BY THIS PROJECT. No Clavia byte enters
this repository in any form: not a file, not an inline array, not base64.

WHAT A GREEN RUN HERE DOES NOT PROVE. A green run against the synthesized
corpus proves that the corpus matches the format specification. **It proves
nothing about real-world patch variety**, because nobody wrote this corpus from
real patches. A construct that a real patch uses and that the specification
does not describe passes here and fails against the G2 Demo corpus.

THE CRC EXPECTATIONS ARE NOT COMPUTED BY THE CODE UNDER TEST. This file carries
its own bitwise reference, written straight from the polynomial, and that
reference is anchored to the PUBLISHED CRC-16/XMODEM check value 0x31C3. A test
whose expectation comes from the function it tests cannot fail.
"""

import pathlib

import pytest

from nmg2_tools.synth_pch2 import (
    CORPUS_DIRECTORY,
    OBJECT_TYPES,
    SIZE_CEILING,
    SynthPch2Error,
    build_object,
    crc16_ccitt,
    generate,
    pack_bits,
)

# ---------------------------------------------------------------------------
# The independent reference. CRC-16/CCITT, the XMODEM
# variant. Polynomial 0x1021, most significant bit first, initial value 0, no
# final exclusive-or, stored big-endian.
# ---------------------------------------------------------------------------


def _reference_crc16(data: bytes) -> int:
    """A bitwise CRC-16/XMODEM, written from the polynomial and from nothing else."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _bit in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def test_the_reference_and_the_module_both_give_the_published_xmodem_check_value():
    """0x31C3 over b"123456789" is the published check value of CRC-16/XMODEM.
    It is external ground truth. BOTH the reference and the module are held
    against it, so this test binds the shipped code and not only the test's own
    arithmetic."""
    assert _reference_crc16(b"123456789") == 0x31C3
    assert crc16_ccitt(b"123456789") == 0x31C3


def test_the_module_crc_agrees_with_the_reference_on_every_vector():
    vectors = [
        b"",
        b"\x00",
        b"A",
        b"123456789",
        b"\x01\x00\x21\x00\x00",
        bytes(range(256)),
    ]

    assert [crc16_ccitt(v) for v in vectors] == [_reference_crc16(v) for v in vectors]


# ---------------------------------------------------------------------------
# The corpus.
# ---------------------------------------------------------------------------

CORPUS_FILES = [
    "bad_crc.pch2",
    "bad_length_past_end.pch2",
    "bad_truncated_object.pch2",
    "bad_unknown_type.pch2",
    "bit_widths.pch2",
    "length_boundaries.pch2",
    "min.pch2",
    "object_types.pch2",
    "wire_extra_bytes_file.pch2",
    "wire_extra_bytes_usb.pch2",
    "wire_morph_names.pch2",
    "wire_variation_count.pch2",
]

MALFORMED = {
    "bad_crc.pch2",
    "bad_length_past_end.pch2",
    "bad_truncated_object.pch2",
    "bad_unknown_type.pch2",
}


def test_the_committed_corpus_holds_exactly_these_files():
    """Exact equality, not membership. A file added without a row here is a
    file no one decided to publish, and this directory is the ONLY place in any
    public repository where a `.pch2` file may live."""
    committed = sorted(p.name for p in CORPUS_DIRECTORY.glob("*.pch2"))

    assert committed == CORPUS_FILES


def test_regenerating_the_corpus_reproduces_every_committed_byte():
    """Re-running the generator reproduces every byte identically. The corpus is
    regenerated, never hand-edited, so an edit made by hand fails here."""
    generated = generate()

    committed = {
        path.name: path.read_bytes()
        for path in CORPUS_DIRECTORY.iterdir()
        if path.name != ".gitkeep"
    }

    assert generated == committed


def test_the_generator_is_deterministic_across_two_calls():
    """Byte identity within one process as well as against the tree. A
    generator that read the clock or a set iteration order would pass the
    assertion above on the machine that wrote the files and fail elsewhere."""
    assert generate() == generate()


def test_the_minimum_file_is_exactly_these_bytes():
    """The whole file, byte for byte, so that the text header, the two-byte
    binary header, the object framing and the trailing CRC are all pinned."""
    assert generate()["min.pch2"] == (
        # The text header. ASCII lines, then one NUL byte.
        b"SYNTHESIZED PCH2 CORPUS\n"
        b"Generator=nmg2_tools.synth_pch2\n"
        b"\x00"
        # The two-byte binary header: the version byte and the type byte.
        b"\x01\x00"
        # One object: type 0x21, a length of zero, no payload.
        b"\x21\x00\x00"
        # CRC-16/XMODEM over b"\x01\x00\x21\x00\x00", stored big-endian.
        b"\x1b\xa7"
    )


def test_every_well_formed_file_carries_the_crc_the_reference_computes():
    """The routine covers the version and type bytes and
    every chunk, and excludes only the trailing CRC. The text header is before
    the covered range and is not covered."""
    generated = generate()

    for name in CORPUS_FILES:
        if name in MALFORMED:
            continue
        image = generated[name]
        covered = image[image.index(b"\x00") + 1 : -2]
        stored = int.from_bytes(image[-2:], "big")

        assert stored == _reference_crc16(covered), name


def test_the_bad_crc_file_stores_a_crc_the_reference_rejects():
    """The rejection half is not optional. A parser tested only on well-formed
    input passes by accepting everything."""
    image = generate()["bad_crc.pch2"]
    covered = image[image.index(b"\x00") + 1 : -2]
    stored = int.from_bytes(image[-2:], "big")

    assert stored != _reference_crc16(covered)
    # One bit flipped in the low byte, so the file is wrong and is not random.
    assert stored == _reference_crc16(covered) ^ 0x0001


def test_the_corpus_covers_every_object_type_the_specification_names():
    """The specified bit-packed types. The union is what `object_types.pch2`
    holds."""
    assert OBJECT_TYPES == (0x21, 0x4A, 0x4D, 0x52, 0x60, 0x62, 0x65, 0x69)

    image = generate()["object_types.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    seen = []
    cursor = 0
    while cursor < len(body):
        type_ = body[cursor]
        length = int.from_bytes(body[cursor + 1 : cursor + 3], "big")
        seen.append(type_)
        cursor += 3 + length

    assert cursor == len(body)
    assert tuple(seen) == OBJECT_TYPES


def test_the_length_boundaries_file_holds_a_zero_length_payload_and_reaches_the_ceiling():
    """The boundary object lengths, including a
    zero-length payload. The upper committed boundary is the payload lint's
    byte ceiling, not the field's own maximum; the next test covers that."""
    image = generate()["length_boundaries.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    assert body[0] == 0x21
    assert body[1:3] == b"\x00\x00"
    assert body[3] == 0x4A
    assert int.from_bytes(body[4:6], "big") == 65469
    assert len(image) == SIZE_CEILING == 65536


def test_no_committed_file_exceeds_the_size_ceiling_and_one_reaches_it():
    """A committed file under `testdata/` may not exceed 65,536 bytes, and this
    corpus lives under `testdata/`."""
    generated = generate()

    assert max(len(v) for v in generated.values()) == SIZE_CEILING


def test_the_largest_two_byte_length_is_reachable_and_is_not_committed():
    """The field's own maximum is 0xFFFF, and an object that carried it could
    not be committed: 3 framing bytes plus 65,535 payload bytes already exceed
    the 65,536-byte ceiling before any header. The generator can still build
    it, so the boundary is exercised here in memory."""
    largest = build_object(0x4A, b"\x00" * 0xFFFF)

    assert largest[:3] == b"\x4a\xff\xff"
    assert len(largest) == 3 + 0xFFFF
    assert len(largest) > SIZE_CEILING

    # 0xFFFF is a PALINDROME, so it reads the same in either byte order and
    # cannot detect a length field written little-endian. One byte below the
    # maximum can, and the boundary is only meaningful if its byte order is.
    assert build_object(0x4A, b"\x00" * 0xFF01)[:3] == b"\x4a\xff\x01"


def test_a_payload_longer_than_the_length_field_is_refused():
    """A REFUSAL above the field maximum AND AN ACCEPTANCE AT IT. The refusal
    alone leaves the comparison unpinned: a guard that had become `>=` refuses a
    payload of exactly 0xFFFF, which does fit the field, and the refusal half
    still passes."""
    with pytest.raises(SynthPch2Error) as caught:
        build_object(0x4A, b"\x00" * 0x10000)

    assert str(caught.value) == (
        "SYNTHPCH2-PAYLOAD-TOO-LONG: 65536 bytes do not fit the 2-byte length field"
    )

    # One byte fewer is the field maximum, and it must be accepted.
    assert len(build_object(0x4A, b"\x00" * 0xFFFF)) == 3 + 0xFFFF


def test_an_object_type_outside_a_byte_is_refused():
    """BOTH ENDS OF THE RANGE. The guard is `0 <= type_ <= 0xFF`. Testing only
    the high end lets a guard that has lost its lower half pass, and a negative
    type then escapes the NAMED refusal and dies inside `bytes([...])` instead,
    which names no field and no rule."""
    with pytest.raises(SynthPch2Error) as caught:
        build_object(0x100, b"")

    assert str(caught.value) == (
        "SYNTHPCH2-BAD-OBJECT-TYPE: 0x100 does not fit the 1-byte type field"
    )

    with pytest.raises(SynthPch2Error) as caught:
        build_object(-1, b"")

    assert str(caught.value) == (
        "SYNTHPCH2-BAD-OBJECT-TYPE: 0x-1 does not fit the 1-byte type field"
    )


# ---------------------------------------------------------------------------
# Bit packing. Fields are bit-packed and are not byte aligned. The 0x39 LED
# payload is the ONLY reversed bit order in the protocol, so every other field
# is most significant bit first.
# ---------------------------------------------------------------------------


def test_pack_bits_writes_the_most_significant_bit_first():
    assert pack_bits([(1, 1)]) == b"\x80"
    assert pack_bits([(1, 0), (1, 1)]) == b"\x40"
    assert pack_bits([(7, 0x7F), (1, 0)]) == b"\xfe"
    assert pack_bits([(32, 0xFFFFFFFF)]) == b"\xff\xff\xff\xff"

    # EVERY value above is a BIT-PALINDROME inside its own declared width: a
    # 1-bit field either way, 0x7F in 7 bits, 0xFFFFFFFF in 32. Each therefore
    # reads the same with the bits of its field reversed, so the four
    # assertions above cannot detect a field packed LEAST significant bit
    # first, which is the one thing this test is named for. The three below
    # can, because no value below equals its own reversal at its width.
    #
    # 1000 + 4 pad bits. Least significant bit first would write 0001 0000.
    assert pack_bits([(4, 0b1000)]) == b"\x80"
    # 0000 1111 exactly fills a byte. Least significant bit first gives 0xF0.
    assert pack_bits([(8, 0x0F)]) == b"\x0f"
    # The maximum width, asymmetric. Least significant bit first gives
    # 0xFFFF0000, so the width the corpus uses is held to the same rule.
    assert pack_bits([(32, 0x0000FFFF)]) == b"\x00\x00\xff\xff"


def test_pack_bits_crosses_a_byte_boundary_without_aligning():
    """3 bits then 12 bits is 15 bits. The result is padded to 16 with zeros:
    101 000011110000 0 is 1010 0001 1110 0000."""
    assert pack_bits([(3, 0b101), (12, 0x0F0)]) == b"\xa1\xe0"

    # 0b101 in 3 bits and 0x0F0 in 12 are BOTH BIT-PALINDROMES, so the
    # assertion above reads the same with the bits of each field reversed. A
    # crossing is only meaningful if the ORDER of the bits that cross is, and
    # that assertion cannot detect a field packed least significant bit first.
    # Neither value below equals its own reversal, and the 12-bit field still
    # straddles the byte boundary at the same place:
    # 110 000011110001 0 is 1100 0001 1110 0010. Least significant bit first
    # would write 011 100011110000 0, which is 0111 0001 1110 0000.
    assert pack_bits([(3, 0b110), (12, 0x0F1)]) == b"\xc1\xe2"


def test_pack_bits_of_nothing_is_nothing():
    assert pack_bits([]) == b""


def test_a_value_that_does_not_fit_its_width_is_refused():
    """BOTH ENDS OF THE RANGE. The guard is `0 <= value < (1 << width)`. A
    negative value that escaped it would be shifted into the accumulator and
    would set every bit ABOVE its own field, so the fault would appear in a
    neighbouring field rather than in this one."""
    with pytest.raises(SynthPch2Error) as caught:
        pack_bits([(3, 8)])

    assert str(caught.value) == (
        "SYNTHPCH2-VALUE-TOO-WIDE: field 0 holds 8, which does not fit 3 bits"
    )

    with pytest.raises(SynthPch2Error) as caught:
        pack_bits([(3, -1)])

    assert str(caught.value) == (
        "SYNTHPCH2-VALUE-TOO-WIDE: field 0 holds -1, which does not fit 3 bits"
    )


def test_a_width_outside_one_to_thirty_two_is_refused():
    """BOTH ENDS OF THE RANGE. Testing width 0 alone lets a guard that has lost
    `<= MAX_FIELD_WIDTH` pass, and `pack_bits([(33, 0)])` then returns five
    bytes for a field the corpus states runs to 32 bits."""
    with pytest.raises(SynthPch2Error) as caught:
        pack_bits([(0, 0)])

    assert str(caught.value) == (
        "SYNTHPCH2-BAD-WIDTH: field 0 declares 0 bits, and a width runs from 1 to 32"
    )

    with pytest.raises(SynthPch2Error) as caught:
        pack_bits([(33, 0)])

    assert str(caught.value) == (
        "SYNTHPCH2-BAD-WIDTH: field 0 declares 33 bits, and a width runs from 1 to 32"
    )


def test_the_bit_width_file_covers_the_minimum_the_interior_and_the_maximum_width():
    """Every bit-packed field at its minimum, maximum and
    one interior width. The interior width is 7, which is deliberately not a
    byte, so a reader that aligned to bytes would disagree here."""
    image = generate()["bit_widths.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    # Three objects, one for each width, each holding that width's minimum
    # value, an interior value and its maximum value. EVERY EXPECTED BYTE IS A
    # LITERAL with the bit arithmetic written out, because an expectation that
    # called `pack_bits` would move with a mutation of `pack_bits`.
    #
    # width 1:  0, 1, 1            -> 011 + 5 pad bits -> 0b0110_0000 = 0x60
    # width 7:  0, 0x2A, 0x7F      -> 0000000 0101010 1111111 + 3 pad bits
    #                              -> 00000000 10101011 11111000
    #                              -> 0x00 0xAB 0xF8
    # width 32: 0, 0x0F0F0F0F, max -> 96 bits, already whole bytes
    assert body == (
        b"\x60\x00\x01" + b"\x60"
        + b"\x60\x00\x03" + b"\x00\xab\xf8"
        + b"\x60\x00\x0c"
        + b"\x00\x00\x00\x00" + b"\x0f\x0f\x0f\x0f" + b"\xff\xff\xff\xff"
    )


# ---------------------------------------------------------------------------
# The file-against-wire differences.
# ---------------------------------------------------------------------------


def test_the_variation_count_is_nine_in_a_file_and_the_corpus_says_so():
    """Difference 1. The count is 9 in a file and 10 on the wire, and it
    affects 0x4D and 0x65. Nobody knows what the tenth variation holds, so the
    corpus states the file count and states nothing about the tenth."""
    image = generate()["wire_variation_count.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    # Each object is a 1-byte count of 9 followed by 9 one-byte indices.
    expected_payload = b"\x09" + bytes(range(9))

    assert body == (
        b"\x4d\x00\x0a" + expected_payload + b"\x65\x00\x0a" + expected_payload
    )


def test_the_usb_form_carries_two_extra_bytes_after_the_0x21_chunk_and_the_file_form_does_not():
    """Difference 2. `0x2D 0x00` follows the `0x21` chunk in USB dumps. They
    are two RAW bytes and not an object, because an object header is three
    bytes. Both forms are committed, so a parser must accept each."""
    generated = generate()

    file_body = generated["wire_extra_bytes_file.pch2"]
    usb_body = generated["wire_extra_bytes_usb.pch2"]

    head = file_body[: file_body.index(b"\x00") + 1]

    assert file_body == head + b"\x01\x00" + b"\x21\x00\x02\xaa\xbb" + file_body[-2:]
    assert usb_body == head + b"\x01\x00" + b"\x21\x00\x02\xaa\xbb\x2d\x00" + usb_body[-2:]
    assert file_body[-2:] != usb_body[-2:]


def test_morph_parameter_names_are_omitted_in_both_paths():
    """Difference 3. The names are omitted on write in both paths, so the
    corpus carries the omitted form and never the present one. The object
    declares a morph count and carries no name after it."""
    image = generate()["wire_morph_names.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    # A 1-byte morph count of 8, then 8 one-byte morph values, and no name.
    assert body == b"\x65\x00\x09" + b"\x08" + bytes(range(8))


# ---------------------------------------------------------------------------
# The malformed set. The parser must reject each with a
# NAMED error, and the manifest is where the corpus states which name.
# ---------------------------------------------------------------------------


def test_the_manifest_names_every_file_and_the_refusal_each_malformed_one_expects():
    assert generate()["MANIFEST.tsv"].decode("ascii") == (
        "# Task TOOL-12. Every byte of this corpus is authored by this project.\n"
        "# file\tkind\texpected_refusal\n"
        "bad_crc.pch2\tmalformed\tPCH2-BAD-CRC\n"
        "bad_length_past_end.pch2\tmalformed\tPCH2-LENGTH-PAST-END\n"
        "bad_truncated_object.pch2\tmalformed\tPCH2-TRUNCATED-OBJECT\n"
        "bad_unknown_type.pch2\tmalformed\tPCH2-UNKNOWN-OBJECT-TYPE\n"
        "bit_widths.pch2\twellformed\t-\n"
        "length_boundaries.pch2\twellformed\t-\n"
        "min.pch2\twellformed\t-\n"
        "object_types.pch2\twellformed\t-\n"
        "wire_extra_bytes_file.pch2\twellformed\t-\n"
        "wire_extra_bytes_usb.pch2\twellformed\t-\n"
        "wire_morph_names.pch2\twellformed\t-\n"
        "wire_variation_count.pch2\twellformed\t-\n"
    )


def test_the_truncated_object_declares_more_payload_than_the_file_holds():
    """The object header is complete and the payload stops early."""
    image = generate()["bad_truncated_object.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    # A declared payload of 8 bytes with 3 present.
    assert body == b"\x4a\x00\x08\x01\x02\x03"


def test_the_length_past_end_file_declares_a_length_beyond_the_whole_file():
    """Distinct from the truncated object: the declared length is not merely
    longer than the payload present, it is longer than the file.

    THE DECLARED LENGTH IS NOT 0xFFFF, AND THAT IS THE POINT. `generate` writes
    this length through its OWN `to_bytes` call and never through
    `build_object`, so it is a SECOND code site for the 2-byte length field.
    0xFFFF is a byte palindrome, so a length written little-endian there is the
    same two bytes and is invisible to every test in this repository, including
    the regenerate-against-the-tree check that compares whole files. 0xFF01 is
    not a palindrome, so the byte order at this site is pinned here."""
    image = generate()["bad_length_past_end.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    assert body == b"\x4a\xff\x01"
    assert len(image) < 0xFF01


def test_the_unknown_type_file_holds_a_type_the_specification_does_not_name():
    image = generate()["bad_unknown_type.pch2"]
    body = image[image.index(b"\x00") + 1 + 2 : -2]

    assert body == b"\xff\x00\x01\x00"
    assert 0xFF not in OBJECT_TYPES


def test_the_corpus_directory_is_nmg2_tools_testdata_pch2_synth():
    """A `*.pch2` file is allowed in exactly one directory of a public
    repository."""
    root = pathlib.Path(__file__).resolve().parents[1]

    assert CORPUS_DIRECTORY == root / "nmg2_tools" / "testdata" / "pch2_synth"
