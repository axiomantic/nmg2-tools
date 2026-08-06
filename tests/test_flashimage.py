"""The CS2 flash image builder. Task TOOL-5, design sections 7.4, 7.5, 23.1.1.

Every byte this file reads is authored here. The test needs no artifact and it
reads no Clavia byte, which is what makes it T0.

THE EXPECTED CHECKSUMS ARE LITERALS AND THE ARITHMETIC IS WRITTEN OUT. A test
that obtains its expected value from the code under test cannot fail, because a
mutation moves the expectation with it. Design section 7.3 step 4 gives the
rule: ``cksum = (~sum(data)) & 0xFFFFFFFF``.
"""

import inspect

import pytest

from nmg2_tools.container import Container, ContainerError, Section, load_sections, parse_header
from nmg2_tools.flashimage import (
    Cs2ImageBuilder,
    Cs2Section,
    ContainerLayout,
    FlashImageError,
)

# Release 1.62. Design section 7.3 reads the word in hexadecimal: 0x00A2 is 162.
VERSION_1_62 = 0x00A2

# sum(b"\x01\x02\x03\x04") = 1 + 2 + 3 + 4 = 10 = 0x0A.
# (~0x0A) & 0xFFFFFFFF = 0xFFFFFFF5.
CODE_BYTES = b"\x01\x02\x03\x04"
CODE_CHECKSUM = 0xFFFFFFF5

# sum(b"\xFF\xFF") = 255 + 255 = 510 = 0x1FE.
# (~0x1FE) & 0xFFFFFFFF = 0xFFFFFE01.
SRAM_BYTES = b"\xff\xff"
SRAM_CHECKSUM = 0xFFFFFE01

# 0x14 header bytes plus one 0x2C entry.
ONE_ENTRY_DATA_OFFSET = 0x40


def test_the_builder_interface_declares_exactly_one_method():
    """Plan TOOL-5: "one method, ``build(sections) -> bytes``". The seam for
    spike criterion (g) is the interface, so its width is the contract. A second
    method added here is a second thing an L2 implementation must supply."""
    public = sorted(
        name
        for name, _value in inspect.getmembers(Cs2ImageBuilder)
        if not name.startswith("_")
    )

    assert public == ["build"]
    assert Cs2ImageBuilder.__abstractmethods__ == frozenset({"build"})


def test_the_builder_interface_cannot_be_instantiated():
    """The interface is the seam and not a default. An L2 that forgot to
    override ``build`` must fail at construction and never return an image."""
    with pytest.raises(TypeError):
        Cs2ImageBuilder()


def test_container_layout_is_the_one_implementation_today():
    """Plan TOOL-5: "one implementation today, ``ContainerLayout``, which is
    L1". A second implementation before spike criterion (g) reports would be a
    guessed L2 header, which section 7.5 forbids."""
    assert Cs2ImageBuilder.__subclasses__() == [ContainerLayout]
    assert issubclass(ContainerLayout, Cs2ImageBuilder)


def test_one_section_builds_these_exact_bytes():
    """The whole image, byte for byte. A partial assertion here would accept a
    wrong offset, a wrong stride or a wrong byte order."""
    builder = ContainerLayout(version=VERSION_1_62)

    image = builder.build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
    )

    assert image == (
        # +0x00 version 0x00A2, +0x02 the fixed word 0x0100.
        b"\x00\xa2\x01\x00"
        # +0x04 the unresolved longword, written as zero.
        b"\x00\x00\x00\x00"
        # +0x08 eight bytes with no known meaning.
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        # +0x10 the section count.
        b"\x00\x00\x00\x01"
        # +0x14 the one entry. Tag, file offset, uncompressed length,
        # load address, plain checksum, compressed length, compressed
        # checksum, the zero word, then twelve unused bytes.
        b"CODE"
        b"\x00\x00\x00\x40"
        b"\x00\x00\x00\x04"
        b"\x30\x00\x04\x00"
        b"\xff\xff\xff\xf5"
        b"\x00\x00\x00\x00"
        b"\xff\xff\xff\xf5"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        # +0x40 the section data.
        + CODE_BYTES
    )


def test_the_built_image_parses_to_the_declared_header_and_table():
    """TOOL-3 is the reader and this is the writer. The two must agree on every
    field, so the whole parsed object is compared and not one field of it."""
    image = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
    )

    assert parse_header(image) == Container(
        version=VERSION_1_62,
        second_word=0x0100,
        unresolved=0,
        sections=(
            Section(
                tag="CODE",
                file_offset=ONE_ENTRY_DATA_OFFSET,
                uncompressed_length=4,
                load_address=0x30000400,
                plain_checksum=CODE_CHECKSUM,
                compressed_length=0,
                compressed_checksum=CODE_CHECKSUM,
                reserved=0,
            ),
        ),
    )


def test_two_sections_load_in_table_order_and_both_checksums_verify():
    """Plan TOOL-5: "asserts its checksums verify". ``load_sections`` performs
    that verification, so a wrong checksum raises rather than returning."""
    image = ContainerLayout(version=VERSION_1_62).build(
        [
            Cs2Section(tag="SRAM", load_address=0x20000800, data=SRAM_BYTES),
            Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES),
        ]
    )

    # 0x14 header bytes plus two 0x2C entries is 0x6C. SRAM is two bytes, so
    # CODE starts at 0x6E.
    assert load_sections(image) == [
        (
            Section(
                tag="SRAM",
                file_offset=0x6C,
                uncompressed_length=2,
                load_address=0x20000800,
                plain_checksum=SRAM_CHECKSUM,
                compressed_length=0,
                compressed_checksum=SRAM_CHECKSUM,
                reserved=0,
            ),
            SRAM_BYTES,
        ),
        (
            Section(
                tag="CODE",
                file_offset=0x6E,
                uncompressed_length=4,
                load_address=0x30000400,
                plain_checksum=CODE_CHECKSUM,
                compressed_length=0,
                compressed_checksum=CODE_CHECKSUM,
                reserved=0,
            ),
            CODE_BYTES,
        ),
    ]


def test_a_section_that_holds_no_bytes_round_trips():
    """The boundary. sum(b"") = 0, and (~0) & 0xFFFFFFFF = 0xFFFFFFFF."""
    image = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=b"")]
    )

    assert load_sections(image) == [
        (
            Section(
                tag="CODE",
                file_offset=ONE_ENTRY_DATA_OFFSET,
                uncompressed_length=0,
                load_address=0x30000400,
                plain_checksum=0xFFFFFFFF,
                compressed_length=0,
                compressed_checksum=0xFFFFFFFF,
                reserved=0,
            ),
            b"",
        )
    ]


def test_a_flipped_data_byte_makes_the_plain_checksum_fail():
    """The check must be able to fail. Without this the two assertions above
    would pass against a builder that wrote a constant checksum."""
    image = bytearray(
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
        )
    )

    # 0x01 becomes 0x02, so the sum is 11 and the stored 0xFFFFFFF5 is wrong.
    # (~0x0B) & 0xFFFFFFFF = 0xFFFFFFF4.
    image[ONE_ENTRY_DATA_OFFSET] = 0x02

    with pytest.raises(ContainerError) as caught:
        load_sections(bytes(image))

    assert str(caught.value) == (
        "CONTAINER-PLAIN-CHECKSUM: section CODE stored 0xFFFFFFF5, "
        "computed 0xFFFFFFF4"
    )


def test_a_tag_that_is_not_four_ascii_characters_is_refused():
    """The tag is a fixed four-byte field. A shorter one would shift every
    field of the entry that follows it."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="OS", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-SECTION-TAG: section 0 holds 'OS', which is not four "
        "ASCII characters"
    )


def test_a_tag_outside_ascii_is_refused():
    """Four characters is not four bytes. TOOL-3 decodes the tag as ASCII and
    names the entry when it cannot."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CÖDE", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-SECTION-TAG: section 0 holds 'CÖDE', which is not "
        "four ASCII characters"
    )


def test_an_image_with_no_section_is_refused():
    """Design section 7.5 quotes the loader's own `No OS detected`. An image
    with no section is that state, and building one silently would produce a
    flash the board cannot boot from."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build([])

    assert str(caught.value) == "FLASHIMAGE-NO-SECTIONS: an image needs at least one section"


def test_a_version_that_does_not_fit_the_word_is_refused():
    """The field is 16 bits. A wider value would silently truncate."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=0x10000).build(
            [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-VERSION: 0x10000 does not fit the 16-bit version word"
    )


def test_a_load_address_that_does_not_fit_the_longword_is_refused():
    """The field is 32 bits, and the m68k address space is 32 bits."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CODE", load_address=0x100000000, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-LOAD-ADDRESS: section 0 loads at 0x100000000, which "
        "does not fit the 32-bit field"
    )


def test_every_section_is_stored_because_this_repository_has_no_compressor():
    """TOOL-1 decompresses and nothing in this repository compresses, so
    ``ContainerLayout`` writes the stored form that TOOL-3 already reads: a
    compressed length of zero means the bytes at the file offset are plain.
    This assertion is here so that a later compressing builder cannot land
    without a decision, because L1 pays one LZO1X decompression on every boot
    and a stored image does not."""
    image = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
    )

    (section,) = parse_header(image).sections

    assert section.compressed_length == 0
    assert section.is_stored is True
