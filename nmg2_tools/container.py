"""The firmware container header and section table.

THE LAYOUT.

The image opens with a 0x14-byte header. The m68k is big-endian, so every
word and every longword below is big-endian.

    +0x00  u16  version. The value is a plain integer read in hexadecimal.
                `0x00A2` is 162, which is release 1.62.
    +0x02  u16  0x0100. The one fixed value in the header.
    +0x04  u32  not resolved. Most probably the begin checksum. It is
                recorded and it is never verified.
    +0x08       8 bytes with no known meaning. They are not read.
    +0x10  u32  the section count.
    +0x14       the section table.

Each table entry is 0x2C bytes. The first 0x20 hold eight fields:

    +0x00  char[4]  the tag, `SRAM` or `CODE`.
    +0x04  u32      the file offset of the section data.
    +0x08  u32      the uncompressed length.
    +0x0C  u32      the load address.
    +0x10  u32      the checksum of the plain bytes.
    +0x14  u32      the compressed length. A value of 0 means the section is
                    stored, so the bytes at the file offset are already plain.
    +0x18  u32      the checksum of the compressed bytes.
    +0x1C  u32      zero. It is recorded and it is never verified.

The last 12 bytes of every entry carry no meaning this project knows. They are
not read. **The stride is 0x2C and not 0x20**: a walk that used the size of
the known fields as the stride desynchronizes after the first entry.

The loader's own error strings confirm the order of the first five fields:
`Sect name error`, `Sect offs error`, `Sect size error`, `Sect addr error`,
`Sect chks error`.

LOADING A SECTION.

**Both checksum verifications are mandatory**, in this order:

1. Verify the compressed checksum over exactly `compressed_length` bytes.
2. Decompress with LZO1X.
3. Compare the produced length against `uncompressed_length`.
4. Compare the consumed length against `compressed_length`.
5. Verify the plain checksum over the produced bytes.

A failure stops the load and names the section.

WHY STEP 4 EXISTS, AND WHAT IT COSTS. The decompressor stops at the end marker
and IGNORES whatever follows it. Without step 4 a section whose declared
compressed extent is longer than the stream it holds decodes cleanly and
passes BOTH checksums, because the compressed checksum is computed over the
declared extent and therefore covers the junk as well. The check would then be
unable to fail. The reference decoder in the workspace returns its input cursor
and asserts the same identity; `nmg2_tools.lzo1x.decompress` returns only the
bytes, so the cursor is not available here.

Step 4 recovers the identity without that cursor. The decompressor stops at the
FIRST end marker, so no shorter prefix of the stream can decode. The stream
therefore consumed every declared byte if and only if the same stream one byte
shorter FAILS to decode. That is one extra decompression of the section, so
loading a section costs about twice what it otherwise would. A follow-up that
gave `decompress` a way to report its cursor would make step 4 a comparison
instead, and would remove that cost.

WHAT STEP 3 DOES AND DOES NOT DO. It DETECTS a stream that produces a different
number of bytes than the table declares. It is not a ceiling on the allocation:
the bytes are already produced when the comparison runs, and `decompress` takes
no maximum output size. The exposure is bounded and LINEAR: a length extension
chain adds 255 for each byte it reads, so output grows to about 255 bytes for
each byte of input and no further. A small stream is therefore not explosive,
and a large section is bounded by its own size times 255. Step 3
is still the only bound there is, which is why it must be able to fail.

WHAT THE CHECKSUM DOES AND DOES NOT DO. It is a plain sum, so it detects a
changed byte and it does not detect a permutation of the same bytes. See
`nmg2_tools.checksum`.
"""

from __future__ import annotations

import dataclasses
import struct

from nmg2_tools.checksum import checksum
from nmg2_tools.lzo1x import Lzo1xError, decompress

# The header ends, and the section table starts, at this offset.
HEADER_SIZE = 0x14

# One section table entry. 0x20 bytes of known fields and 12 that are not read.
ENTRY_STRIDE = 0x2C

# The fixed word at `+0x02`.
SECOND_WORD = 0x0100

_HEADER = struct.Struct(">HHI")
_ENTRY = struct.Struct(">4s7I")


class ContainerError(ValueError):
    """A container that this parser refuses to read.

    The message starts with a name: `CONTAINER-TRUNCATED-HEADER`,
    `CONTAINER-BAD-SECOND-WORD`, `CONTAINER-TRUNCATED-SECTION-TABLE`,
    `CONTAINER-BAD-SECTION-TAG`, `CONTAINER-SECTION-OUT-OF-RANGE`,
    `CONTAINER-COMPRESSED-CHECKSUM`, `CONTAINER-LENGTH-MISMATCH`,
    `CONTAINER-TRAILING-BYTES` or `CONTAINER-PLAIN-CHECKSUM`. The five that a
    section can raise name the section. A caller stops the load and prints the
    name.

    A stream that the decompressor refuses raises `nmg2_tools.lzo1x.Lzo1xError`
    and not this error, so that the caller can tell the two layers apart. Both
    are a `ValueError`.
    """


@dataclasses.dataclass(frozen=True)
class Section:
    """One row of the section table."""

    tag: str
    file_offset: int
    uncompressed_length: int
    load_address: int
    plain_checksum: int
    compressed_length: int
    compressed_checksum: int
    reserved: int

    @property
    def is_stored(self) -> bool:
        """Report a section that holds plain bytes and no LZO1X stream."""
        return self.compressed_length == 0


@dataclasses.dataclass(frozen=True)
class Container:
    """The parsed header and section table.

    `version` is the raw 16-bit word. It is saved in
    plugin state, so the value is kept as it was read and not as text.
    """

    version: int
    second_word: int
    unresolved: int
    sections: tuple[Section, ...]


def version_text(version: int) -> str:
    """Return the release number that a version word states.

    `0x00A2` is 162, which is release 1.62. The word is a plain integer and
    the release splits it at the hundreds.
    """
    return f"{version // 100}.{version % 100:02d}"


def parse_header(image: bytes | bytearray | memoryview) -> Container:
    """Parse the container header and the whole section table.

    Raise `ContainerError` when the image is shorter than the header, when the
    fixed word at `+0x02` is wrong, when the table does not fit the image, or
    when a tag is not ASCII.
    """
    data = bytes(image)

    if len(data) < HEADER_SIZE:
        raise ContainerError(
            f"CONTAINER-TRUNCATED-HEADER: {HEADER_SIZE} bytes needed, "
            f"{len(data)} available"
        )

    version, second_word, unresolved = _HEADER.unpack_from(data, 0)
    if second_word != SECOND_WORD:
        raise ContainerError(
            f"CONTAINER-BAD-SECOND-WORD: 0x{second_word:04X} at offset 0x02, "
            f"expected 0x{SECOND_WORD:04X}"
        )

    (count,) = struct.unpack_from(">I", data, 0x10)
    needed = count * ENTRY_STRIDE
    available = len(data) - HEADER_SIZE
    if needed > available:
        raise ContainerError(
            f"CONTAINER-TRUNCATED-SECTION-TABLE: {count} entries need "
            f"{needed} bytes at offset 0x{HEADER_SIZE:02X}, "
            f"{available} available"
        )

    sections = tuple(
        _parse_entry(data, index) for index in range(count)
    )
    return Container(
        version=version,
        second_word=second_word,
        unresolved=unresolved,
        sections=sections,
    )


def load_section(
    image: bytes | bytearray | memoryview, section: Section
) -> bytes:
    """Return the plain bytes of one section, both checksums verified.

    Raise `ContainerError` when the section reaches past the end of the image,
    when either checksum disagrees, when the stream produces a different number
    of bytes than the table declares, or when it consumes fewer bytes than the
    table declares. Raise `nmg2_tools.lzo1x.Lzo1xError` when the stream itself
    is malformed.
    """
    data = bytes(image)

    if section.is_stored:
        plain = _slice(data, section, section.uncompressed_length)
    else:
        stream = _slice(data, section, section.compressed_length)
        computed = checksum(stream)
        if computed != section.compressed_checksum:
            raise ContainerError(
                f"CONTAINER-COMPRESSED-CHECKSUM: section {section.tag} stored "
                f"0x{section.compressed_checksum:08X}, "
                f"computed 0x{computed:08X}"
            )
        plain = decompress(stream)
        if len(plain) != section.uncompressed_length:
            raise ContainerError(
                f"CONTAINER-LENGTH-MISMATCH: section {section.tag} declared "
                f"{section.uncompressed_length} bytes, the stream produced "
                f"{len(plain)}"
            )
        _reject_trailing_bytes(stream, section)

    computed = checksum(plain)
    if computed != section.plain_checksum:
        raise ContainerError(
            f"CONTAINER-PLAIN-CHECKSUM: section {section.tag} stored "
            f"0x{section.plain_checksum:08X}, computed 0x{computed:08X}"
        )
    return plain


def load_sections(
    image: bytes | bytearray | memoryview,
) -> list[tuple[Section, bytes]]:
    """Parse the container and load every section, in table order."""
    data = bytes(image)
    return [
        (section, load_section(data, section))
        for section in parse_header(data).sections
    ]


def _reject_trailing_bytes(stream: bytes, section: Section) -> None:
    """Refuse a section that declares more compressed bytes than it uses.

    The decompressor stops at the first end marker and ignores what follows,
    so a declared extent that is too long decodes cleanly and passes both
    checksums. No shorter prefix of a well-formed stream can decode, because
    the end marker the decoder stops at is the first one. The stream therefore
    used every declared byte if and only if the stream one byte shorter fails.

    This costs one more decompression of the section. See the module docstring.
    """
    try:
        decompress(stream[:-1])
    except Lzo1xError:
        return
    raise ContainerError(
        f"CONTAINER-TRAILING-BYTES: section {section.tag} declared "
        f"{section.compressed_length} compressed bytes, the stream ended "
        f"before the last of them"
    )


def _parse_entry(data: bytes, index: int) -> Section:
    """Read the entry at `index`, at the 0x2C-byte stride."""
    offset = HEADER_SIZE + index * ENTRY_STRIDE
    (
        tag,
        file_offset,
        uncompressed_length,
        load_address,
        plain_checksum,
        compressed_length,
        compressed_checksum,
        reserved,
    ) = _ENTRY.unpack_from(data, offset)

    try:
        text = tag.decode("ascii")
    except UnicodeDecodeError:
        raise ContainerError(
            f"CONTAINER-BAD-SECTION-TAG: entry {index} holds {tag.hex()}, "
            f"which is not ASCII"
        ) from None

    return Section(
        tag=text,
        file_offset=file_offset,
        uncompressed_length=uncompressed_length,
        load_address=load_address,
        plain_checksum=plain_checksum,
        compressed_length=compressed_length,
        compressed_checksum=compressed_checksum,
        reserved=reserved,
    )


def _slice(data: bytes, section: Section, length: int) -> bytes:
    """Return `length` bytes at the section's file offset.

    The check is on the bytes present, so an offset or a length that the image
    cannot satisfy is a named failure and never a short read.
    """
    available = max(0, len(data) - section.file_offset)
    if length > available:
        raise ContainerError(
            f"CONTAINER-SECTION-OUT-OF-RANGE: section {section.tag} needs "
            f"{length} bytes at offset 0x{section.file_offset:02X}, "
            f"{available} available"
        )
    return data[section.file_offset : section.file_offset + length]
