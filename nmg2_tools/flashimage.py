"""The CS2 flash image builder. Task TOOL-5.

Design sections 7.4, 7.5 and 23.1.1.

WHAT THIS FILE IS, because the licence makes it matter.

`nmg2-tools` is MIT. The container layout this builder writes is a FACT about a
data format, and facts are not copyrightable. The layout is read from design
section 7.3 and from `nmg2_tools.container`, which is this project's own reader
for the same format. No line of any other implementation is copied,
transliterated or paraphrased here.

WHY THERE IS AN INTERFACE FOR ONE IMPLEMENTATION.

Design section 7.5 records that the on-flash layout of CS2 is NOT KNOWN. Two
candidates exist:

    L1  CS2 holds the update container verbatim. The loader verifies and
        decompresses on every boot.
    L2  CS2 holds the already-decompressed image plus a small header. The
        loader verifies a checksum and copies.

The evidence leans to L1 and a lean is not a proof. Spike exit criterion (g)
decides it. Design section 23.1.1 states the rule this file obeys: BUILD THE
SEAM, DO NOT BUILD THE OPTION. So `Cs2ImageBuilder` declares one method,
`build(sections) -> bytes`, and `ContainerLayout` is the one implementation
today. L2 adds a second implementation and one enumerator, and nothing in
`g2Lib` changes, because the board consumes a byte image and does not care how
the image was built.

**L2's header format cannot be written until criterion (g) reports it.** Design
section 7.5 says so in its own words. Do not guess it.

WHAT `ContainerLayout` WRITES, AND THE ONE THING IT DOES NOT.

The image is the container of design section 7.3: a 0x14-byte header, a section
table of 0x2C bytes for each entry, then the section data in table order.

Every section is written in the STORED form, which is a compressed length of
zero. `nmg2_tools.container` already reads that form: a compressed length of
zero means the bytes at the file offset are already plain. The reason is plain
too. `nmg2_tools.lzo1x` decompresses and nothing in this repository compresses,
so a builder that wrote LZO1X streams would need a compressor this project does
not have and `pyproject.toml` declares no dependency that could supply one.

**A stored image is a valid container and it is not a compressed one.** The
difference is a boot cost, not a format: design section 7.5 records that L1 pays
one LZO1X decompression of 530 KB on every boot. An image this builder produces
does not pay it. A later builder that compresses is a decision for whoever needs
the real boot cost.
"""

from __future__ import annotations

import abc
import dataclasses
import struct
from collections.abc import Sequence

from nmg2_tools.checksum import checksum
from nmg2_tools.container import ENTRY_STRIDE, HEADER_SIZE, SECOND_WORD

MASK16 = 0xFFFF
MASK32 = 0xFFFFFFFF

# The eight bytes at +0x08 have no known meaning and TOOL-3 does not read them.
_UNKNOWN_HEADER_BYTES = 8

# The last twelve bytes of an entry carry no meaning this project knows.
_UNUSED_ENTRY_BYTES = ENTRY_STRIDE - 0x20

_HEADER = struct.Struct(">HHI")
_ENTRY = struct.Struct(">4s7I")


class FlashImageError(ValueError):
    """An image this builder refuses to write.

    The message starts with a name: `FLASHIMAGE-NO-SECTIONS`,
    `FLASHIMAGE-BAD-VERSION`, `FLASHIMAGE-BAD-SECTION-TAG` or
    `FLASHIMAGE-BAD-LOAD-ADDRESS`. The two that a section can raise name the
    index of the section, because a tag that is already wrong cannot name it.
    """


@dataclasses.dataclass(frozen=True)
class Cs2Section:
    """One section the caller asks the builder to place in the image.

    `tag` is the four-character name, `SRAM` or `CODE`. `load_address` is where
    the loader puts the plain bytes. `data` is the plain bytes themselves; the
    builder computes both checksums and both lengths.
    """

    tag: str
    load_address: int
    data: bytes


class Cs2ImageBuilder(abc.ABC):
    """The seam for spike exit criterion (g).

    ONE METHOD. A caller holds this type and never a concrete one, so the day
    criterion (g) reports L2 the call site does not move.
    """

    @abc.abstractmethod
    def build(self, sections: Sequence[Cs2Section]) -> bytes:
        """Return the CS2 flash image that holds `sections`."""


class ContainerLayout(Cs2ImageBuilder):
    """L1. The image is the update container of design section 7.3."""

    def __init__(self, version: int) -> None:
        """Hold the version word the header carries at `+0x00`.

        Design section 15.5 item 5 saves the word in plugin state, so it is
        carried as it was given and never as text.
        """
        if not 0 <= version <= MASK16:
            raise FlashImageError(
                f"FLASHIMAGE-BAD-VERSION: 0x{version:X} does not fit the "
                f"16-bit version word"
            )
        self.version = version

    def build(self, sections: Sequence[Cs2Section]) -> bytes:
        """Return the image. Raise `FlashImageError` on a section it cannot write."""
        if not sections:
            raise FlashImageError(
                "FLASHIMAGE-NO-SECTIONS: an image needs at least one section"
            )

        tags = [_encode_tag(section, index) for index, section in enumerate(sections)]

        # The data area starts after the whole table, so every file offset is
        # known before the first entry is written.
        offset = HEADER_SIZE + len(sections) * ENTRY_STRIDE

        table = bytearray()
        payload = bytearray()
        for index, section in enumerate(sections):
            if not 0 <= section.load_address <= MASK32:
                raise FlashImageError(
                    f"FLASHIMAGE-BAD-LOAD-ADDRESS: section {index} loads at "
                    f"0x{section.load_address:X}, which does not fit the "
                    f"32-bit field"
                )

            # The stored form. The compressed extent IS the plain extent, so
            # the two checksums are the checksum of the same bytes, and the
            # compressed length is the zero that names the form.
            plain_checksum = checksum(section.data)
            table += _ENTRY.pack(
                tags[index],
                offset,
                len(section.data),
                section.load_address,
                plain_checksum,
                0,
                plain_checksum,
                0,
            )
            table += bytes(_UNUSED_ENTRY_BYTES)

            payload += section.data
            offset += len(section.data)

        header = bytearray()
        # The longword at +0x04 is not resolved. Design section 7.3 records it
        # as most probably the begin checksum, and TOOL-3 never verifies it.
        # Writing zero states that this builder computed nothing there.
        header += _HEADER.pack(self.version, SECOND_WORD, 0)
        header += bytes(_UNKNOWN_HEADER_BYTES)
        header += struct.pack(">I", len(sections))

        return bytes(header + table + payload)


def _encode_tag(section: Cs2Section, index: int) -> bytes:
    """Return the four ASCII bytes of a section tag.

    Four CHARACTERS is not four BYTES. A tag outside ASCII would encode to a
    different width and shift every field of the entry that follows it, so the
    two cases give one named refusal.
    """
    try:
        encoded = section.tag.encode("ascii")
    except UnicodeEncodeError:
        encoded = b""

    if len(encoded) != 4:
        raise FlashImageError(
            f"FLASHIMAGE-BAD-SECTION-TAG: section {index} holds "
            f"{section.tag!r}, which is not four ASCII characters"
        ) from None

    return encoded
