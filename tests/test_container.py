"""Task TOOL-3. Design section 7.3 steps 2, 3, 5 and 6.

WHERE THE CONTAINERS COME FROM.

Every container below is BUILT HERE, by `build_container`, from stated field
values. No Clavia byte appears in this file. The G2 firmware lives in the
PRIVATE `axiomantic/nmg2-artifacts` repository and must never enter a public
tree, as a fixture, as an inline array or as base64.

A green run therefore proves that this parser agrees with the container layout
that design section 7.3 states. It does NOT prove that the layout matches the
shipped `NMG2_128_OS.bin`. Task TOOL-4 reads the real firmware, is gated on the
artifacts, and is the first check that touches a Clavia byte.

WHERE THE COMPRESSED STREAMS COME FROM.

The three LZO1X streams below are the reference vectors of
`tests/test_lzo1x.py`. The reference implementation `liblzo2` 2.10 produced
them, outside this repository, and `tests/test_lzo1x.py` asserts the plain
bytes each one gives. They are repeated here rather than imported so that this
file states its own inputs and a change to the other file cannot move the
meaning of a container built here.
"""

import struct

import pytest

from nmg2_tools.checksum import checksum
from nmg2_tools.container import (
    ENTRY_STRIDE,
    HEADER_SIZE,
    Container,
    ContainerError,
    Section,
    load_section,
    load_sections,
    parse_header,
    version_text,
)
from nmg2_tools.lzo1x import Lzo1xError

# --- compressed streams, and the plain bytes each one gives -----------------

# 7 compressed bytes -> 3 plain bytes.
ABC_STREAM = bytes.fromhex("14616263110000")
ABC_PLAIN = b"abc"

# 21 compressed bytes -> 17 plain bytes.
DIGITS_STREAM = bytes.fromhex("223031323334353637383961626364656667110000")
DIGITS_PLAIN = b"0123456789abcdefg"

# 34 compressed bytes -> 5,000 plain bytes, a ratio of 147. Nothing in the
# stream announces the size it will produce, which is what makes the
# produced-length check load-bearing.
BOMB_STREAM = bytes.fromhex(
    "12412000000000000000e600002000000000000000e6000020000000690000110000"
)
BOMB_PLAIN = b"A" * 5000

# --- checksums stated as literals, not computed by the code under test ------
#
# Every expected error message below carries one of these. Computing the
# expected value with `checksum` would make the assertion agree with whatever
# `checksum` did, including a broken `checksum`. The arithmetic is written out
# so that a reader can check it without running anything.

# 'a' + 'b' + 'c' = 97 + 98 + 99 = 294 = 0x126.
ABC_PLAIN_CKSUM = 0xFFFFFED9
# 0x14 + 0x61 + 0x62 + 0x63 + 0x11 = 331 = 0x14B.
ABC_STREAM_CKSUM = 0xFFFFFEB4
# The same stream with three more bytes, 1 + 2 + 3, so 337 = 0x151.
ABC_OVERRUN_CKSUM = 0xFFFFFEAE
# The same stream with 0x61 changed to 0x60, so 330 = 0x14A.
ABC_DAMAGED_CKSUM = 0xFFFFFEB5
# '0'..'9' = 525, 'a'..'g' = 700, so 1225 = 0x4C9.
DIGITS_PLAIN_CKSUM = 0xFFFFFB36
# 5,000 * 'A' = 5000 * 65 = 325,000 = 0x4F588.
BOMB_PLAIN_CKSUM = 0xFFFB0A77


# --- the synthetic container builder ---------------------------------------


def build_entry(
    tag,
    *,
    file_offset,
    uncompressed_length,
    load_address,
    plain_checksum,
    compressed_length,
    compressed_checksum,
    reserved=0,
    padding=b"\x00" * 12,
):
    """One 0x2C-byte section table entry, every field stated.

    The first 0x20 bytes are the eight fields design section 7.3 names. The
    remaining 12 bytes carry no documented meaning; `padding` fills them and
    the tests below put non-zero bytes there on purpose.
    """
    fields = struct.pack(
        ">4s7I",
        tag,
        file_offset,
        uncompressed_length,
        load_address,
        plain_checksum,
        compressed_length,
        compressed_checksum,
        reserved,
    )
    assert len(fields) == 0x20
    return fields + padding


def build_container(
    entries,
    payloads,
    *,
    version=0x00A2,
    second_word=0x0100,
    unresolved=0xDEADBEEF,
    gap=b"\x00" * 8,
    section_count=None,
):
    """A whole image: the 0x14-byte header, the table, then the payloads.

    `entries` are already-packed 0x2C-byte entries and `payloads` is the blob
    that follows the table. Both are given whole so that a test can state a
    field that disagrees with the payload it points at.
    """
    if section_count is None:
        section_count = len(entries)
    header = (
        struct.pack(">HH", version, second_word)
        + struct.pack(">I", unresolved)
        + gap
        + struct.pack(">I", section_count)
    )
    assert len(header) == 0x14
    return header + b"".join(entries) + payloads


def compressed_entry(tag, plain, stream, *, load_address, file_offset, **overrides):
    """An entry that describes `stream` honestly, before any override."""
    fields = {
        "file_offset": file_offset,
        "uncompressed_length": len(plain),
        "load_address": load_address,
        "plain_checksum": checksum(plain),
        "compressed_length": len(stream),
        "compressed_checksum": checksum(stream),
    }
    fields.update(overrides)
    return build_entry(tag, **fields)


def one_section_image(tag, plain, stream, *, load_address=0x30000400, **overrides):
    """An image with exactly one section whose payload follows the table.

    The payload sits directly after the one-entry table, so `file_offset`
    defaults to that position. An override replaces it.
    """
    overrides.setdefault("file_offset", HEADER_SIZE + ENTRY_STRIDE)
    entry = compressed_entry(
        tag,
        plain,
        stream,
        load_address=load_address,
        **overrides,
    )
    return build_container([entry], stream)


def test_the_stated_checksums_are_the_ones_the_checksum_module_produces():
    """The literals above are what every expected message below is built from.
    This is the one place they meet the implementation, so a change in
    `nmg2_tools.checksum` fails HERE and names itself, rather than moving both
    sides of a dozen other assertions together and staying green."""
    assert checksum(ABC_PLAIN) == ABC_PLAIN_CKSUM
    assert checksum(ABC_STREAM) == ABC_STREAM_CKSUM
    assert checksum(ABC_STREAM + b"\x01\x02\x03") == ABC_OVERRUN_CKSUM
    assert checksum(DIGITS_PLAIN) == DIGITS_PLAIN_CKSUM
    assert checksum(BOMB_PLAIN) == BOMB_PLAIN_CKSUM


# --- the header and the section table, design section 7.3 step 2 ------------


def test_the_header_offsets_and_the_entry_stride_are_the_documented_ones():
    """0x14 and 0x2C are the two numbers every other test depends on."""
    assert HEADER_SIZE == 0x14
    assert ENTRY_STRIDE == 0x2C


def test_the_parse_records_the_version_word_and_every_other_header_field():
    """Design section 7.3 step 6: record the version word. Section 15.5 item 5
    saves it in plugin state, so the raw 16-bit value is what is kept."""
    image = build_container([], b"")

    assert parse_header(image) == Container(
        version=0x00A2,
        second_word=0x0100,
        unresolved=0xDEADBEEF,
        sections=(),
    )


def test_the_version_word_reads_as_a_decimal_release_number():
    """Design section 7.3: `0x00A2` is 162, which is version 1.62. The word is
    read as a plain integer and then split at the hundreds, so an
    implementation that treats it as packed BCD returns something else."""
    assert version_text(0x00A2) == "1.62"
    assert version_text(0x0064) == "1.00"
    assert version_text(0x0001) == "0.01"
    assert version_text(0x00CB) == "2.03"


def test_the_section_table_reads_every_field_of_every_entry():
    """Every integer below is stated here and read back. A parser that shifted
    one field, or that read a field at the wrong width, changes at least one
    of them."""
    first = build_entry(
        b"SRAM",
        file_offset=0x00001000,
        uncompressed_length=1946,
        load_address=0x20000800,
        plain_checksum=0x11223344,
        compressed_length=0x00000321,
        compressed_checksum=0x55667788,
        reserved=0,
    )
    second = build_entry(
        b"CODE",
        file_offset=0x00002000,
        uncompressed_length=1220560,
        load_address=0x30000400,
        plain_checksum=0x99AABBCC,
        compressed_length=0x000A0B0C,
        compressed_checksum=0xDDEEFF00,
        reserved=0,
    )
    image = build_container([first, second], b"")

    assert parse_header(image).sections == (
        Section(
            tag="SRAM",
            file_offset=0x00001000,
            uncompressed_length=1946,
            load_address=0x20000800,
            plain_checksum=0x11223344,
            compressed_length=0x00000321,
            compressed_checksum=0x55667788,
            reserved=0,
        ),
        Section(
            tag="CODE",
            file_offset=0x00002000,
            uncompressed_length=1220560,
            load_address=0x30000400,
            plain_checksum=0x99AABBCC,
            compressed_length=0x000A0B0C,
            compressed_checksum=0xDDEEFF00,
            reserved=0,
        ),
    )


def test_every_word_is_big_endian():
    """The G2 runs an m68k. Each value below reads as a different number when
    the same bytes are taken little-endian, so a byte-order slip cannot pass:
    `0x30000400` would become `0x00040030` and `0x00A2` would become `0xA200`.
    """
    entry = build_entry(
        b"CODE",
        file_offset=0x00000014,
        uncompressed_length=0x00010203,
        load_address=0x30000400,
        plain_checksum=0x01020304,
        compressed_length=0x04030201,
        compressed_checksum=0x0A0B0C0D,
    )
    parsed = parse_header(build_container([entry], b"", version=0x00A2))

    assert parsed.version == 0x00A2
    assert parsed.sections[0].load_address == 0x30000400
    assert parsed.sections[0].uncompressed_length == 0x00010203
    assert parsed.sections[0].compressed_length == 0x04030201
    assert parsed.sections[0].compressed_checksum == 0x0A0B0C0D


def test_the_entry_stride_is_0x2c_and_the_last_twelve_bytes_are_not_read():
    """0x20 bytes hold the eight documented fields and the stride is 0x2C, so
    12 bytes of every entry carry no meaning this project knows. They are
    filled with a pattern that would parse as a plausible entry if the stride
    were 0x20, and the SECOND entry must still read correctly."""
    noise = build_entry(
        b"XXXX",
        file_offset=0xAAAAAAAA,
        uncompressed_length=0xBBBBBBBB,
        load_address=0xCCCCCCCC,
        plain_checksum=0xDDDDDDDD,
        compressed_length=0xEEEEEEEE,
        compressed_checksum=0xFFFFFFFF,
        reserved=0x99999999,
    )[:12]
    first = build_entry(
        b"SRAM",
        file_offset=1,
        uncompressed_length=2,
        load_address=3,
        plain_checksum=4,
        compressed_length=5,
        compressed_checksum=6,
        padding=noise,
    )
    second = build_entry(
        b"CODE",
        file_offset=7,
        uncompressed_length=8,
        load_address=9,
        plain_checksum=10,
        compressed_length=11,
        compressed_checksum=12,
    )

    parsed = parse_header(build_container([first, second], b""))

    assert parsed.sections == (
        Section(
            tag="SRAM",
            file_offset=1,
            uncompressed_length=2,
            load_address=3,
            plain_checksum=4,
            compressed_length=5,
            compressed_checksum=6,
            reserved=0,
        ),
        Section(
            tag="CODE",
            file_offset=7,
            uncompressed_length=8,
            load_address=9,
            plain_checksum=10,
            compressed_length=11,
            compressed_checksum=12,
            reserved=0,
        ),
    )


def test_the_word_at_0x04_is_recorded_and_never_verified():
    """Design section 7.3 calls it "not resolved. Most probably the begin
    checksum." A parser that checked a value it does not understand would
    reject containers for a reason this project cannot state, so every value
    parses and the word is handed back."""
    for value in (0x00000000, 0xDEADBEEF, 0xFFFFFFFF):
        image = build_container([], b"", unresolved=value)

        assert parse_header(image).unresolved == value


def test_the_zero_word_of_an_entry_is_recorded_and_never_verified():
    """Same reason. The field is documented as zero, so a non-zero value is
    worth carrying to the caller, but rejecting on it is a guess."""
    entry = build_entry(
        b"CODE",
        file_offset=0,
        uncompressed_length=0,
        load_address=0,
        plain_checksum=0,
        compressed_length=0,
        compressed_checksum=0,
        reserved=0x12345678,
    )

    parsed = parse_header(build_container([entry], b""))

    assert parsed.sections[0].reserved == 0x12345678


# --- named failures of the header parse -------------------------------------


def test_a_second_word_that_is_not_0x0100_is_a_named_failure():
    image = build_container([], b"", second_word=0x0200)

    with pytest.raises(ContainerError) as raised:
        parse_header(image)

    assert str(raised.value) == (
        "CONTAINER-BAD-SECOND-WORD: 0x0200 at offset 0x02, expected 0x0100"
    )


def test_an_image_shorter_than_the_header_is_a_named_failure():
    image = build_container([], b"")[:19]

    with pytest.raises(ContainerError) as raised:
        parse_header(image)

    assert str(raised.value) == (
        "CONTAINER-TRUNCATED-HEADER: 20 bytes needed, 19 available"
    )


def test_a_section_table_that_does_not_fit_the_image_is_a_named_failure():
    """A count of 0xFFFFFFFF asks for 189 gigabytes of table. The check is on
    the bytes present, so it costs one comparison and no allocation."""
    image = build_container([], b"", section_count=0xFFFFFFFF)

    with pytest.raises(ContainerError) as raised:
        parse_header(image)

    assert str(raised.value) == (
        "CONTAINER-TRUNCATED-SECTION-TABLE: 4294967295 entries need "
        "188978560980 bytes at offset 0x14, 0 available"
    )


def test_a_section_table_one_byte_short_is_a_named_failure():
    """The boundary, not only the absurd case."""
    image = build_container([build_entry(
        b"CODE",
        file_offset=0,
        uncompressed_length=0,
        load_address=0,
        plain_checksum=0,
        compressed_length=0,
        compressed_checksum=0,
    )], b"")[:-1]

    with pytest.raises(ContainerError) as raised:
        parse_header(image)

    assert str(raised.value) == (
        "CONTAINER-TRUNCATED-SECTION-TABLE: 1 entries need 44 bytes at "
        "offset 0x14, 43 available"
    )


def test_a_tag_that_is_not_ascii_is_a_named_failure():
    """The tag is `char[4]`. A non-ASCII tag means the table is not a table,
    and guessing an encoding would hide that."""
    entry = build_entry(
        b"\xff\xfe\xfd\xfc",
        file_offset=0,
        uncompressed_length=0,
        load_address=0,
        plain_checksum=0,
        compressed_length=0,
        compressed_checksum=0,
    )

    with pytest.raises(ContainerError) as raised:
        parse_header(build_container([entry], b""))

    assert str(raised.value) == (
        "CONTAINER-BAD-SECTION-TAG: entry 0 holds fffefdfc, which is not ASCII"
    )


# --- loading a section, design section 7.3 step 3 ---------------------------


def test_a_section_loads_the_exact_plain_bytes():
    image = one_section_image(b"CODE", ABC_PLAIN, ABC_STREAM)
    section = parse_header(image).sections[0]

    assert load_section(image, section) == b"abc"


def test_a_section_that_expands_thirty_four_bytes_to_five_thousand_loads_them():
    image = one_section_image(b"CODE", BOMB_PLAIN, BOMB_STREAM)
    section = parse_header(image).sections[0]

    assert load_section(image, section) == b"A" * 5000


def test_load_sections_returns_every_section_in_table_order_with_its_bytes():
    """Two sections, different lengths, both payloads in one image. A loader
    that used one offset for both, or that returned the table order reversed,
    changes this."""
    first_offset = HEADER_SIZE + 2 * ENTRY_STRIDE
    second_offset = first_offset + len(ABC_STREAM)
    first = compressed_entry(
        b"SRAM",
        ABC_PLAIN,
        ABC_STREAM,
        load_address=0x20000800,
        file_offset=first_offset,
    )
    second = compressed_entry(
        b"CODE",
        DIGITS_PLAIN,
        DIGITS_STREAM,
        load_address=0x30000400,
        file_offset=second_offset,
    )
    image = build_container([first, second], ABC_STREAM + DIGITS_STREAM)

    loaded = load_sections(image)

    assert loaded == [
        (
            Section(
                tag="SRAM",
                file_offset=first_offset,
                uncompressed_length=3,
                load_address=0x20000800,
                plain_checksum=checksum(ABC_PLAIN),
                compressed_length=7,
                compressed_checksum=checksum(ABC_STREAM),
                reserved=0,
            ),
            b"abc",
        ),
        (
            Section(
                tag="CODE",
                file_offset=second_offset,
                uncompressed_length=17,
                load_address=0x30000400,
                plain_checksum=checksum(DIGITS_PLAIN),
                compressed_length=21,
                compressed_checksum=checksum(DIGITS_STREAM),
                reserved=0,
            ),
            b"0123456789abcdefg",
        ),
    ]


def test_a_stored_section_carries_its_plain_bytes_and_no_stream():
    """A compressed length of 0 means the section is stored, so the bytes at
    the file offset ARE the plain bytes and only the plain checksum applies.
    Handing a stored section to the decompressor would raise a truncation
    error on a container that is legal."""
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"SRAM",
        file_offset=offset,
        uncompressed_length=len(DIGITS_PLAIN),
        load_address=0x20000800,
        plain_checksum=checksum(DIGITS_PLAIN),
        compressed_length=0,
        compressed_checksum=0,
    )
    image = build_container([entry], DIGITS_PLAIN)
    section = parse_header(image).sections[0]

    assert section.is_stored is True
    assert load_section(image, section) == b"0123456789abcdefg"


def test_a_compressed_section_is_not_reported_as_stored():
    """The positive control for the assertion above."""
    image = one_section_image(b"CODE", ABC_PLAIN, ABC_STREAM)

    assert parse_header(image).sections[0].is_stored is False


# --- both checksum verifications are mandatory ------------------------------


def test_a_wrong_compressed_checksum_stops_the_load_and_names_the_section():
    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, compressed_checksum=0x00000000
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-COMPRESSED-CHECKSUM: section CODE stored 0x00000000, "
        "computed 0xFFFFFEB4"
    )


def test_a_changed_compressed_byte_stops_the_load_before_the_decompressor():
    """The stored checksum is right for the stream the container SHOULD hold.
    One byte of the payload is changed, so the compressed check must fire, and
    it must fire before the plain check: the changed byte makes the stream
    decode to different bytes, and a loader that verified only the plain
    checksum would report the wrong one of the two errors."""
    damaged = bytearray(ABC_STREAM)
    damaged[1] ^= 0x01
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"CODE",
        file_offset=offset,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=checksum(ABC_PLAIN),
        compressed_length=len(ABC_STREAM),
        compressed_checksum=checksum(ABC_STREAM),
    )
    image = build_container([entry], bytes(damaged))
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-COMPRESSED-CHECKSUM: section CODE stored 0xFFFFFEB4, "
        "computed 0xFFFFFEB5"
    )


def test_a_wrong_plain_checksum_stops_the_load_and_names_the_section():
    """The compressed checksum is correct here, so the load reaches the
    decompressor and the SECOND check is what fires. This is the assertion
    that proves both verifications run and not only the first."""
    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, plain_checksum=0x00000000
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-PLAIN-CHECKSUM: section CODE stored 0x00000000, "
        "computed 0xFFFFFED9"
    )


def test_a_stored_section_with_a_wrong_plain_checksum_is_a_named_failure():
    """A stored section skips the decompressor, so it must not skip the check
    that remains."""
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"SRAM",
        file_offset=offset,
        uncompressed_length=len(DIGITS_PLAIN),
        load_address=0x20000800,
        plain_checksum=0x00000000,
        compressed_length=0,
        compressed_checksum=0,
    )
    image = build_container([entry], DIGITS_PLAIN)
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-PLAIN-CHECKSUM: section SRAM stored 0x00000000, "
        "computed 0xFFFFFB36"
    )


def test_a_permuted_payload_passes_the_plain_verification():
    """The checksum is a sum, so it does not depend on the order of the bytes.
    A stored section whose payload is a PERMUTATION of the bytes the table
    describes therefore loads, and hands back bytes that are not the ones the
    container meant. This states the limit of the two verifications rather than
    leaving a reader to assume they are stronger than they are.

    The second half is the positive control, in the same run: one CHANGED byte,
    at the same length, IS refused. Without it this test would still pass
    against a loader that verified nothing at all."""
    permuted = bytearray(DIGITS_PLAIN)
    permuted[0], permuted[1] = permuted[1], permuted[0]
    assert bytes(permuted) != DIGITS_PLAIN

    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"SRAM",
        file_offset=offset,
        uncompressed_length=len(DIGITS_PLAIN),
        load_address=0x20000800,
        plain_checksum=DIGITS_PLAIN_CKSUM,
        compressed_length=0,
        compressed_checksum=0,
    )

    image = build_container([entry], bytes(permuted))
    section = parse_header(image).sections[0]
    assert load_section(image, section) == b"1023456789abcdefg"

    changed = bytearray(DIGITS_PLAIN)
    changed[0] ^= 0x01
    image = build_container([entry], bytes(changed))
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-PLAIN-CHECKSUM: section SRAM stored 0xFFFFFB36, "
        "computed 0xFFFFFB35"
    )


# --- the consumed length against the declared compressed length -------------


def test_a_section_that_declares_more_bytes_than_the_stream_uses_is_a_failure():
    """THE CHECK THAT WOULD OTHERWISE BE IMPOSSIBLE TO FAIL.

    The decompressor stops at the end marker and ignores what follows. Here the
    table declares an extent that covers three junk bytes past the end marker,
    AND the compressed checksum is computed over that whole extent, so it
    agrees. The plain checksum agrees too, because the decoded bytes are right.
    Both mandated verifications pass. Only the consumed-length check refuses
    this container."""
    overrun = ABC_STREAM + b"\x01\x02\x03"
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"CODE",
        file_offset=offset,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=ABC_PLAIN_CKSUM,
        compressed_length=len(overrun),
        compressed_checksum=ABC_OVERRUN_CKSUM,
    )
    image = build_container([entry], overrun)
    section = parse_header(image).sections[0]

    # Both mandated verifications agree with this container. Stated here so
    # that the refusal below cannot be mistaken for a checksum catching it.
    assert checksum(overrun) == section.compressed_checksum
    assert checksum(ABC_PLAIN) == section.plain_checksum

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-TRAILING-BYTES: section CODE declared 10 compressed bytes, "
        "the stream ended before the last of them"
    )


def test_one_junk_byte_past_the_end_marker_is_enough_to_refuse_the_section():
    """The boundary. A single ignored byte is still a container that does not
    describe itself, and the check is exact rather than tolerant."""
    overrun = ABC_STREAM + b"\x00"
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"CODE",
        file_offset=offset,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=ABC_PLAIN_CKSUM,
        compressed_length=len(overrun),
        compressed_checksum=checksum(overrun),
    )
    image = build_container([entry], overrun)
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-TRAILING-BYTES: section CODE declared 8 compressed bytes, "
        "the stream ended before the last of them"
    )


def test_a_section_that_uses_every_declared_byte_is_accepted():
    """The positive control for the refusals above. Without it, a check that
    refused EVERY section would pass them."""
    image = one_section_image(b"CODE", ABC_PLAIN, ABC_STREAM)
    section = parse_header(image).sections[0]

    assert section.compressed_length == 7
    assert load_section(image, section) == b"abc"


def test_a_stored_section_is_not_asked_what_it_consumed():
    """A stored section runs no decompressor, so there is no cursor to check
    and its plain bytes are its whole declared extent."""
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"SRAM",
        file_offset=offset,
        uncompressed_length=len(DIGITS_PLAIN),
        load_address=0x20000800,
        plain_checksum=DIGITS_PLAIN_CKSUM,
        compressed_length=0,
        compressed_checksum=0,
    )
    image = build_container([entry], DIGITS_PLAIN + b"trailing junk")
    section = parse_header(image).sections[0]

    assert load_section(image, section) == b"0123456789abcdefg"


# --- the produced length against the declared length ------------------------


def test_a_stream_that_produces_more_than_the_declared_length_is_a_failure():
    """THE ONLY BOUND THERE IS. A 34-byte stream produces 5,000 bytes. A
    container that declares 10 is either wrong or hostile, and the loader must
    not hand the caller 5,000 bytes for a section it said was 10.

    Design section 7.3 step 3 puts this check after the decompressor, which is
    where the m68k loader has it. It DETECTS the mismatch; it does not prevent
    the allocation, because the bytes are already produced when it runs, and
    `decompress` takes no maximum output size. The exposure that leaves is
    bounded and linear: a length extension chain adds 255 for each byte it
    reads, so output tops out at about 255 bytes per input byte. A small stream
    is not explosive; a large section is bounded by its own size."""
    image = one_section_image(
        b"CODE",
        BOMB_PLAIN,
        BOMB_STREAM,
        uncompressed_length=10,
        # 10 * 'A' = 650 = 0x28A.
        plain_checksum=0xFFFFFD75,
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-LENGTH-MISMATCH: section CODE declared 10 bytes, "
        "the stream produced 5000"
    )


def test_a_stream_that_produces_fewer_than_the_declared_length_is_a_failure():
    """The other direction. A short read that filled the rest of the load
    address with whatever was already there would be a silent corruption."""
    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, uncompressed_length=4096
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-LENGTH-MISMATCH: section CODE declared 4096 bytes, "
        "the stream produced 3"
    )


def test_the_length_check_runs_before_the_plain_checksum():
    """Both are wrong here. The length is the more specific fact, and a
    checksum computed over the wrong number of bytes says nothing, so the
    length must be the error the caller sees."""
    image = one_section_image(
        b"CODE",
        BOMB_PLAIN,
        BOMB_STREAM,
        uncompressed_length=10,
        plain_checksum=0x00000000,
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-LENGTH-MISMATCH: section CODE declared 10 bytes, "
        "the stream produced 5000"
    )


def test_a_stored_section_whose_length_disagrees_with_the_table_is_a_failure():
    """A stored section has no decompressor to bound it, so the length is
    checked against the bytes the file offset and the declared length reach."""
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"SRAM",
        file_offset=offset,
        uncompressed_length=64,
        load_address=0x20000800,
        plain_checksum=checksum(DIGITS_PLAIN),
        compressed_length=0,
        compressed_checksum=0,
    )
    image = build_container([entry], DIGITS_PLAIN)
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-SECTION-OUT-OF-RANGE: section SRAM needs 64 bytes at "
        "offset 0x40, 17 available"
    )


# --- a section that does not fit the image ----------------------------------


def test_a_section_that_reaches_past_the_end_of_the_image_is_a_failure():
    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, compressed_length=4096
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-SECTION-OUT-OF-RANGE: section CODE needs 4096 bytes at "
        "offset 0x40, 7 available"
    )


def test_a_file_offset_past_the_end_of_the_image_is_a_failure():
    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, file_offset=0x7FFFFFFF
    )
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-SECTION-OUT-OF-RANGE: section CODE needs 7 bytes at "
        "offset 0x7FFFFFFF, 0 available"
    )


def test_a_compressed_length_that_stops_short_holds_the_checksum_accountable():
    """The decompressor ignores whatever follows the end marker, so a
    compressed length that is too LONG cannot be caught by the decompressor.
    The compressed checksum covers exactly `compressed_length` bytes, so it is
    the field that catches it. Three extra bytes follow the stream here and
    the stored checksum is the one for the stream alone."""
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"CODE",
        file_offset=offset,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=checksum(ABC_PLAIN),
        compressed_length=len(ABC_STREAM) + 3,
        compressed_checksum=checksum(ABC_STREAM),
    )
    overrun = ABC_STREAM + b"\x01\x02\x03"
    image = build_container([entry], overrun)
    section = parse_header(image).sections[0]

    with pytest.raises(ContainerError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "CONTAINER-COMPRESSED-CHECKSUM: section CODE stored 0xFFFFFEB4, "
        "computed 0xFFFFFEAE"
    )


# --- a broken stream inside a well-formed container -------------------------


def test_a_truncated_stream_raises_the_decompressor_s_own_named_failure():
    """The container does not restate what the decompressor already names. A
    truncated stream is `LZO-MISSING-END-MARKER`, and swallowing that into a
    container-level message would lose which of the two layers failed."""
    truncated = ABC_STREAM[:-3]
    offset = HEADER_SIZE + ENTRY_STRIDE
    entry = build_entry(
        b"CODE",
        file_offset=offset,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=checksum(ABC_PLAIN),
        compressed_length=len(truncated),
        compressed_checksum=checksum(truncated),
    )
    image = build_container([entry], truncated)
    section = parse_header(image).sections[0]

    with pytest.raises(Lzo1xError) as raised:
        load_section(image, section)

    assert str(raised.value) == (
        "LZO-MISSING-END-MARKER: input ended at offset 4 with no end marker"
    )


# --- the error type -----------------------------------------------------


def test_the_named_failure_is_a_value_error():
    """A caller that catches `ValueError` catches every refusal of both
    layers, because `Lzo1xError` is one too."""
    assert issubclass(ContainerError, ValueError)
    assert issubclass(Lzo1xError, ValueError)


def test_every_named_failure_starts_with_its_code():
    """One run that reaches each refusal and states the code it carries. A
    message that lost its prefix would still be a `ContainerError`, and a
    caller that prints the name would print nothing useful."""
    seen = []

    with pytest.raises(ContainerError) as raised:
        parse_header(build_container([], b"")[:19])
    seen.append(str(raised.value).split(":")[0])

    with pytest.raises(ContainerError) as raised:
        parse_header(build_container([], b"", second_word=0x0200))
    seen.append(str(raised.value).split(":")[0])

    with pytest.raises(ContainerError) as raised:
        parse_header(build_container([], b"", section_count=4))
    seen.append(str(raised.value).split(":")[0])

    bad_tag = build_entry(
        b"\xff\xfe\xfd\xfc",
        file_offset=0,
        uncompressed_length=0,
        load_address=0,
        plain_checksum=0,
        compressed_length=0,
        compressed_checksum=0,
    )
    with pytest.raises(ContainerError) as raised:
        parse_header(build_container([bad_tag], b""))
    seen.append(str(raised.value).split(":")[0])

    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, compressed_length=4096
    )
    with pytest.raises(ContainerError) as raised:
        load_section(image, parse_header(image).sections[0])
    seen.append(str(raised.value).split(":")[0])

    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, compressed_checksum=0
    )
    with pytest.raises(ContainerError) as raised:
        load_section(image, parse_header(image).sections[0])
    seen.append(str(raised.value).split(":")[0])

    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, uncompressed_length=4096
    )
    with pytest.raises(ContainerError) as raised:
        load_section(image, parse_header(image).sections[0])
    seen.append(str(raised.value).split(":")[0])

    overrun = ABC_STREAM + b"\x01\x02\x03"
    entry = build_entry(
        b"CODE",
        file_offset=HEADER_SIZE + ENTRY_STRIDE,
        uncompressed_length=len(ABC_PLAIN),
        load_address=0x30000400,
        plain_checksum=ABC_PLAIN_CKSUM,
        compressed_length=len(overrun),
        compressed_checksum=ABC_OVERRUN_CKSUM,
    )
    image = build_container([entry], overrun)
    with pytest.raises(ContainerError) as raised:
        load_section(image, parse_header(image).sections[0])
    seen.append(str(raised.value).split(":")[0])

    image = one_section_image(
        b"CODE", ABC_PLAIN, ABC_STREAM, plain_checksum=0
    )
    with pytest.raises(ContainerError) as raised:
        load_section(image, parse_header(image).sections[0])
    seen.append(str(raised.value).split(":")[0])

    assert seen == [
        "CONTAINER-TRUNCATED-HEADER",
        "CONTAINER-BAD-SECOND-WORD",
        "CONTAINER-TRUNCATED-SECTION-TABLE",
        "CONTAINER-BAD-SECTION-TAG",
        "CONTAINER-SECTION-OUT-OF-RANGE",
        "CONTAINER-COMPRESSED-CHECKSUM",
        "CONTAINER-LENGTH-MISMATCH",
        "CONTAINER-TRAILING-BYTES",
        "CONTAINER-PLAIN-CHECKSUM",
    ]


def test_the_input_may_be_a_bytearray_or_a_memoryview():
    """The caller reads the image from a resource fork or a PE section and
    does not always hold a `bytes`."""
    image = one_section_image(b"CODE", ABC_PLAIN, ABC_STREAM)
    expected = parse_header(image)

    assert parse_header(bytearray(image)) == expected
    assert parse_header(memoryview(image)) == expected
    assert load_section(bytearray(image), expected.sections[0]) == b"abc"
    assert load_section(memoryview(image), expected.sections[0]) == b"abc"
