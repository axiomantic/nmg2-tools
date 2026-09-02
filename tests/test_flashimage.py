"""The CS2 flash image builder.

The test needs no artifact and reads no firmware byte, which is what makes it
T0.

THE EXPECTED CHECKSUMS ARE LITERALS AND THE ARITHMETIC IS WRITTEN OUT. A test
that obtains its expected value from the code under test cannot fail, because a
mutation moves the expectation with it. The rule is
``cksum = (~sum(data)) & 0xFFFFFFFF``.
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

# Release 1.62. The word is read in hexadecimal: 0x00A2 is 162.
VERSION_1_62 = 0x00A2

# sum(b"\x01\x02\x03\x04") = 1 + 2 + 3 + 4 = 10 = 0x0A.
# (~0x0A) & 0xFFFFFFFF = 0xFFFFFFF5.
CODE_BYTES = b"\x01\x02\x03\x04"
CODE_CHECKSUM = 0xFFFFFFF5
# The same number as the four big-endian bytes an entry holds. It is written
# out and not packed, because a pack taken from the code under test moves with
# a mutation of the byte order.
CODE_CHECKSUM_BYTES = b"\xff\xff\xff\xf5"

# sum(b"\xFF\xFF") = 255 + 255 = 510 = 0x1FE.
# (~0x1FE) & 0xFFFFFFFF = 0xFFFFFE01.
SRAM_BYTES = b"\xff\xff"
SRAM_CHECKSUM = 0xFFFFFE01

# 0x14 header bytes plus one 0x2C entry.
ONE_ENTRY_DATA_OFFSET = 0x40

# The first entry starts where the header ends. The
# plain checksum sits at +0x10 of an entry, the compressed length at +0x14, the
# compressed checksum at +0x18 and the trailing zero word at +0x1C. The four
# numbers are written out here, not derived from the module, because an offset
# taken from the code under test moves with a mutation of it.
FIRST_ENTRY_OFFSET = 0x14
PLAIN_CHECKSUM_OFFSET = FIRST_ENTRY_OFFSET + 0x10
COMPRESSED_LENGTH_OFFSET = FIRST_ENTRY_OFFSET + 0x14
COMPRESSED_CHECKSUM_OFFSET = FIRST_ENTRY_OFFSET + 0x18
RESERVED_OFFSET = FIRST_ENTRY_OFFSET + 0x1C


def test_the_builder_interface_declares_exactly_one_method():
    """One method, ``build(sections) -> bytes``. The seam for the
    undecided CS2 layout is the interface, so its width is the contract. A second
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
    override ``build`` must fail at construction and never return an image.

    THE CAUSE IS PINNED AND NOT ONLY THE EXCEPTION TYPE. ``TypeError`` alone
    cannot tell "this class is abstract" from "this constructor wants an
    argument". An interface whose ``build`` had become concrete, and which
    merely took a version argument, would raise ``TypeError`` here and still
    return an image to anyone who passed one."""
    assert inspect.isabstract(Cs2ImageBuilder)

    with pytest.raises(TypeError) as caught:
        Cs2ImageBuilder()

    assert "abstract" in str(caught.value)


def test_container_layout_is_the_one_implementation_today():
    """One implementation today, ``ContainerLayout``, which is L1. A second
    implementation would be a guessed L2 header, which is forbidden.

    THE WALK IS RECURSIVE. ``__subclasses__`` returns DIRECT subclasses only, so
    a class that derived from ``ContainerLayout`` rather than from the interface
    would not appear in it and a guessed L2 could land unseen."""

    def every_subclass(root):
        found = set()
        for child in root.__subclasses__():
            found.add(child)
            found |= every_subclass(child)
        return found

    assert every_subclass(Cs2ImageBuilder) == {ContainerLayout}
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
    """``container`` is the reader and this is the writer. The two must agree on every
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


def test_two_sections_load_in_table_order_and_the_plain_checksum_verifies():
    """``load_sections`` performs the checksum verification, so a wrong checksum raises rather than returning.

    THE NAME SAYS ONE CHECKSUM AND NOT BOTH, BECAUSE ONLY ONE RUNS. Every
    section this builder writes is stored, so ``load_section`` takes the
    ``is_stored`` branch, and that branch never reaches the compressed-checksum
    verification at all. A test that asserted only the parsed field values would
    stay green with the whole plain-checksum check deleted. The failure half is
    asserted below, on the SECOND section, so a check that runs on the first
    section alone is caught too."""
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

    # THE FAILURE HALF. Without it every assertion above is satisfied by a
    # loader that verifies nothing, because they read only the parsed fields.
    # The byte flipped is in the SECOND section, so a verification that ran on
    # the first section alone does not pass here either. CODE starts at 0x6E,
    # and 0x01 becomes 0x02, so the sum is 11 and (~0x0B) & 0xFFFFFFFF is
    # 0xFFFFFFF4 against the stored 0xFFFFFFF5.
    damaged = bytearray(image)
    damaged[0x6E] = 0x02

    with pytest.raises(ContainerError) as caught:
        load_sections(bytes(damaged))

    assert str(caught.value) == (
        "CONTAINER-PLAIN-CHECKSUM: section CODE stored 0xFFFFFFF5, "
        "computed 0xFFFFFFF4"
    )


def test_a_section_that_holds_no_bytes_round_trips():
    """The boundary. sum(b"") = 0, and (~0) & 0xFFFFFFFF = 0xFFFFFFFF.

    EVERY EXPECTATION OF THE EMPTY CASE IS DEGENERATE. The two lengths are zero,
    the file offset is the only one there is, and both checksums are the
    all-ones constant, so a ``checksum`` whose whole body was ``return
    0xFFFFFFFF`` satisfies all of them and the test cannot tell the function
    from a stub. The two one-byte sections below separate them: they differ
    from the constant and from each other."""
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

    # sum(b"\x00") = 0, so the checksum is the same all-ones value as the empty
    # section. The LENGTH is what separates this case from the one above.
    zero_byte = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=b"\x00")]
    )
    (zero_section, zero_data) = load_sections(zero_byte)[0]

    assert zero_data == b"\x00"
    assert zero_section.uncompressed_length == 1
    assert zero_section.plain_checksum == 0xFFFFFFFF

    # sum(b"\x01") = 1, and (~1) & 0xFFFFFFFF = 0xFFFFFFFE. This is the value a
    # constant checksum cannot produce.
    one_byte = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=b"\x01")]
    )
    (one_section, one_data) = load_sections(one_byte)[0]

    assert one_data == b"\x01"
    assert one_section.uncompressed_length == 1
    assert one_section.plain_checksum == 0xFFFFFFFE
    assert one_section.compressed_checksum == 0xFFFFFFFE


def test_a_flipped_data_byte_makes_the_plain_checksum_fail():
    """The check must be able to fail. Without it a builder that wrote a
    constant checksum would satisfy the assertions above."""
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
    field of the entry that follows it.

    BOTH SIDES OF THE LENGTH, because the guard is an inequality. A guard that
    refused a SHORT tag alone leaves a long one to the ``>4s`` pack format,
    which truncates it in silence: `CODES` would be written as `CODE` and the
    image would name a section the caller never asked for."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="OS", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-SECTION-TAG: section 0 holds 'OS', which is not four "
        "ASCII characters"
    )

    # The long side. `>4s` truncates rather than raising, so nothing below the
    # builder would report this.
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CODES", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-SECTION-TAG: section 0 holds 'CODES', which is not "
        "four ASCII characters"
    )


def test_a_tag_outside_ascii_is_refused():
    """Four characters is not four bytes. The reader decodes the tag as ASCII and
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
    """The loader's own message is `No OS detected`. An image
    with no section is that state, and building one silently would produce a
    flash the board cannot boot from."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build([])

    assert str(caught.value) == "FLASHIMAGE-NO-SECTIONS: an image needs at least one section"


def test_a_version_that_does_not_fit_the_word_is_refused():
    """The field is 16 bits. A wider value would silently truncate.

    BOTH ENDS OF THE RANGE. The guard is ``0 <= version <= MASK16``. Testing
    only the high end lets a guard that has lost its lower half pass, and a
    negative version then escapes the NAMED refusal and dies inside
    ``struct.pack`` instead, which names no field and no rule."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=0x10000).build(
            [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-VERSION: 0x10000 does not fit the 16-bit version word"
    )

    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=-1).build(
            [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-VERSION: 0x-1 does not fit the 16-bit version word"
    )


def test_a_load_address_that_does_not_fit_the_longword_is_refused():
    """The field is 32 bits, and the m68k address space is 32 bits.

    BOTH ENDS OF THE RANGE, for the reason the version test gives: a negative
    load address that escaped the named refusal would fail inside
    ``struct.pack`` with no field named."""
    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CODE", load_address=0x100000000, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-LOAD-ADDRESS: section 0 loads at 0x100000000, which "
        "does not fit the 32-bit field"
    )

    with pytest.raises(FlashImageError) as caught:
        ContainerLayout(version=VERSION_1_62).build(
            [Cs2Section(tag="CODE", load_address=-1, data=CODE_BYTES)]
        )

    assert str(caught.value) == (
        "FLASHIMAGE-BAD-LOAD-ADDRESS: section 0 loads at 0x-1, which does not "
        "fit the 32-bit field"
    )


def test_every_section_is_stored_because_this_repository_has_no_compressor():
    """``lzo1x`` decompresses and nothing in this repository compresses, so
    ``ContainerLayout`` writes the stored form the reader already accepts: a
    compressed length of zero means the bytes at the file offset are plain.
    This assertion is here so that a later compressing builder cannot land
    without a decision, because L1 pays one LZO1X decompression on every boot
    and a stored image does not.

    EVERY SECTION, so the image holds MORE THAN ONE. A single section cannot
    tell "every section is stored" from "the first section is stored": a builder
    that stored section 0 and compressed the rest would satisfy it."""
    image = ContainerLayout(version=VERSION_1_62).build(
        [
            Cs2Section(tag="SRAM", load_address=0x20000800, data=SRAM_BYTES),
            Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES),
        ]
    )

    sections = parse_header(image).sections

    assert len(sections) == 2
    assert [s.compressed_length for s in sections] == [0, 0]
    assert all(s.is_stored is True for s in sections)


def test_the_compressed_length_and_the_trailing_zero_sit_at_their_declared_offsets():
    """WHAT THIS TEST CAN PIN, AND WHAT NOTHING IN THIS REPOSITORY CAN.

    Two PAIRS of slots are DEGENERATE in an image this builder writes. Every
    section is stored, so the compressed length is always zero and the trailing
    zero word is always zero; and both checksums are the checksum of the same
    plain bytes, so the plain checksum always equals the compressed checksum.

    THE BUILDER SIDE OF EACH PAIR IS AN EQUIVALENT MUTANT. Two equal values
    cannot pin their own order. A builder that EXCHANGED the compressed length
    with the trailing zero, or the plain checksum with the compressed checksum,
    writes a byte-identical image for every input, so no test anywhere can turn
    either exchange red. Only a compressor, which this repository does not have
    and which `pyproject.toml` declares no dependency that could supply, would
    make the members of either pair differ and make the exchange visible.

    THE READER SIDE OF EACH PAIR IS OBSERVABLE, and that is what this test
    pins. Which BYTE OFFSET of the entry carries which name does not depend on
    the builder writing distinct values, because a probe can plant them. A
    distinct sentinel goes into each of the four slots of a built image and the
    reader must report each under the right name. A reader that exchanged
    either pair of offsets fails here. The whole-image assertion above cannot
    catch the length-and-zero exchange, because it compares zero against zero;
    and no assertion that read both checksums as `CODE_CHECKSUM` could catch
    the checksum exchange, for the same reason.

    The remaining four fields are asserted unmoved, and their values are
    distinct from each other and from all four sentinels, so a sentinel that
    landed in any of them is named rather than silently absorbed.
    """
    image = ContainerLayout(version=VERSION_1_62).build(
        [Cs2Section(tag="CODE", load_address=0x30000400, data=CODE_BYTES)]
    )

    # The builder writes zero into both length slots. That is the stored form.
    assert image[COMPRESSED_LENGTH_OFFSET : COMPRESSED_LENGTH_OFFSET + 4] == bytes(4)
    assert image[RESERVED_OFFSET : RESERVED_OFFSET + 4] == bytes(4)

    # The builder writes the SAME checksum into both checksum slots, because a
    # stored section compresses to itself. This is the degeneracy the sentinels
    # below exist to work around.
    assert (
        image[PLAIN_CHECKSUM_OFFSET : PLAIN_CHECKSUM_OFFSET + 4] == CODE_CHECKSUM_BYTES
    )
    assert (
        image[COMPRESSED_CHECKSUM_OFFSET : COMPRESSED_CHECKSUM_OFFSET + 4]
        == CODE_CHECKSUM_BYTES
    )

    # Four sentinels, distinct from each other and from every other value in
    # the entry, so a landing in the wrong field is visible rather than
    # plausible. `parse_header` reads the table and verifies no checksum, so a
    # checksum sentinel reaches the reader unchallenged.
    probe = bytearray(image)
    probe[PLAIN_CHECKSUM_OFFSET : PLAIN_CHECKSUM_OFFSET + 4] = b"\x99\xaa\xbb\xcc"
    probe[COMPRESSED_LENGTH_OFFSET : COMPRESSED_LENGTH_OFFSET + 4] = b"\x11\x22\x33\x44"
    probe[COMPRESSED_CHECKSUM_OFFSET : COMPRESSED_CHECKSUM_OFFSET + 4] = (
        b"\xdd\xee\xff\x01"
    )
    probe[RESERVED_OFFSET : RESERVED_OFFSET + 4] = b"\x55\x66\x77\x88"

    (section,) = parse_header(bytes(probe)).sections

    assert section.plain_checksum == 0x99AABBCC
    assert section.compressed_length == 0x11223344
    assert section.compressed_checksum == 0xDDEEFF01
    assert section.reserved == 0x55667788

    # Every other field of the entry is where it was.
    assert section.tag == "CODE"
    assert section.file_offset == ONE_ENTRY_DATA_OFFSET
    assert section.uncompressed_length == 4
    assert section.load_address == 0x30000400
