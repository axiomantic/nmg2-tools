"""An LZO1X decompressor.

The G2 loader holds an m68k port of LZO1X. Each section of the firmware
container is an LZO1X stream, and the loader decompresses it between two
checksum verifications.

HOW THIS FILE WAS WRITTEN, because the licence makes it matter.

`nmg2-tools` is MIT. The reference LZO implementations, `liblzo2` and
`minilzo`, are GPL-2.0. No line of either is copied, transliterated or
paraphrased here. This file is a clean-room implementation from the
description of the wire format: the instruction encoding, the rules for the
length of a literal run and of a match, and the three distance encodings.
Those are facts about the data. The reference code is a different expression
of them and is not used.

THE FORMAT.

A stream is a sequence of instructions. Each instruction starts with one
opcode byte. The opcode selects one of five forms.

  Opcode 0 to 15, at the top of the stream or after a match with no trailing
  literals: a LITERAL RUN. The run holds `opcode + 3` bytes. An opcode of 0
  means the length continues in an extension chain with a base of 15.

  Opcode 0 to 15, immediately after a literal run: a SHORT MATCH of 3 bytes
  at a distance of `2049 + (opcode >> 2) + (next byte << 2)`.

  Opcode 0 to 15, immediately after trailing literals: a SHORT MATCH of
  2 bytes at a distance of `1 + (opcode >> 2) + (next byte << 2)`.

  Opcode 16 to 31: a LONG-DISTANCE MATCH. The length is `(opcode & 7) + 2`,
  with an extension chain with a base of 7 when `opcode & 7` is 0. Two bytes
  hold a little-endian word; `word >> 2` plus `(opcode & 8) << 11` gives the
  distance above a base of 16384. When both parts are 0 the instruction is the
  END MARKER and the stream stops.

  Opcode 32 to 63: a MEDIUM MATCH. The length is `(opcode & 31) + 2`, with an
  extension chain with a base of 31 when `opcode & 31` is 0. Two bytes hold a
  little-endian word and `1 + (word >> 2)` gives the distance.

  Opcode 64 to 255: a SHORT MATCH. The length is `(opcode >> 5) + 1` and the
  distance is `1 + ((opcode >> 2) & 7) + (next byte << 3)`.

An extension chain reads bytes while they are 0 and adds 255 for each. The
first byte that is not 0 is added to the base and stops the chain.

Every match instruction also carries a count of TRAILING LITERALS in the low
two bits of its last byte. The two-byte forms carry it in the first of the two
distance bytes, because the distance uses only the upper 14 bits of that word.
Trailing literals are copied at once, and the byte after them is the opcode of
another match, never of a literal run.

The first byte of the stream is a special case. A value above 17 means the
stream opens with a literal run of `first byte - 17` bytes.

A match may reach back a shorter distance than its own length. The source and
the destination then overlap, and the result is the last `distance` bytes
repeated. This is a property of the format, not an accident, and the
compressor uses it to encode a long run of one value.
"""

from __future__ import annotations

# A long-distance match is above this base, and the same instruction form with
# a distance of 0 is the end of the stream.
LONG_DISTANCE_BASE = 0x4000

# A short match that follows a literal run reaches back at least this far.
HEAD_MATCH_BASE = 0x0801


class Lzo1xError(ValueError):
    """A stream that this decompressor refuses to decode.

    The message starts with a name: `LZO-TRUNCATED-INPUT`,
    `LZO-MISSING-END-MARKER` or `LZO-DISTANCE-BEFORE-START`. A caller stops
    the load and prints the name. A truncated stream is always this error and
    never a partial result.
    """


class _Reader:
    """A bounds-checked cursor over the compressed bytes."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.pos = 0

    def instruction(self) -> int:
        """Read one opcode byte.

        The end of the input at this point is a stream with no end marker.
        Every well-formed stream stops at an end marker, so there is always
        one more opcode to read.
        """
        if self.pos >= len(self._data):
            raise Lzo1xError(
                f"LZO-MISSING-END-MARKER: input ended at offset {self.pos} "
                f"with no end marker"
            )
        value = self._data[self.pos]
        self.pos += 1
        return value

    def byte(self) -> int:
        return self.take(1)[0]

    def take(self, count: int) -> bytes:
        """Read `count` bytes of stream data."""
        end = self.pos + count
        if end > len(self._data):
            unit = "byte" if count == 1 else "bytes"
            raise Lzo1xError(
                f"LZO-TRUNCATED-INPUT: {count} {unit} needed at offset "
                f"{self.pos}, {len(self._data) - self.pos} available"
            )
        chunk = self._data[self.pos : end]
        self.pos = end
        return chunk

    def word(self) -> int:
        low, high = self.take(2)
        return low | (high << 8)

    def at_start_of_literal_run(self) -> bool:
        """Report the special case of the first byte of the stream."""
        return self.pos < len(self._data) and self._data[self.pos] > 17

    def extended_length(self, base: int) -> int:
        """Read a length that did not fit in the opcode."""
        extra = 0
        while True:
            value = self.byte()
            if value != 0:
                return base + extra + value
            extra += 255


def _copy_match(out: bytearray, distance: int, length: int) -> None:
    """Copy `length` bytes that start `distance` bytes back in `out`.

    A distance shorter than the length repeats the last `distance` bytes,
    which is what a byte-at-a-time copy produces.
    """
    if distance > len(out):
        raise Lzo1xError(
            f"LZO-DISTANCE-BEFORE-START: distance {distance} is more than "
            f"the {len(out)} bytes written"
        )
    start = len(out) - distance
    if distance >= length:
        out += out[start : start + length]
        return
    period = bytes(out[start:])
    out += (period * (length // distance + 1))[:length]


def decompress(src: bytes | bytearray | memoryview) -> bytes:
    """Decompress one LZO1X stream and return the plain bytes.

    Raise `Lzo1xError` when the stream is truncated, when it holds no end
    marker, or when a match reaches before the start of the output.
    """
    reader = _Reader(bytes(src))
    out = bytearray()

    # The state names below are the positions the format distinguishes. A
    # literal run and a run of trailing literals are followed by different
    # readings of the same opcode value, so the position is part of the state.
    state = "start"
    opcode = 0
    trailing = 0

    while True:
        if state == "start":
            if reader.at_start_of_literal_run():
                count = reader.instruction() - 17
                out += reader.take(count)
                # A run of fewer than four bytes is a run of trailing
                # literals, and a match follows it.
                state = "after_literals" if count >= 4 else "before_match"
            else:
                state = "instruction"

        elif state == "instruction":
            opcode = reader.instruction()
            if opcode >= 16:
                state = "match"
                continue
            count = opcode if opcode != 0 else reader.extended_length(15)
            out += reader.take(count + 3)
            state = "after_literals"

        elif state == "after_literals":
            opcode = reader.instruction()
            if opcode >= 16:
                state = "match"
                continue
            distance = HEAD_MATCH_BASE + (opcode >> 2) + (reader.byte() << 2)
            _copy_match(out, distance, 3)
            trailing = opcode & 3
            state = "trailing"

        elif state == "before_match":
            opcode = reader.instruction()
            state = "match"

        elif state == "match":
            if opcode >= 64:
                length = (opcode >> 5) + 1
                distance = 1 + ((opcode >> 2) & 7) + (reader.byte() << 3)
                trailing = opcode & 3
            elif opcode >= 32:
                length = (opcode & 31) or reader.extended_length(31)
                length += 2
                word = reader.word()
                distance = 1 + (word >> 2)
                trailing = word & 3
            elif opcode >= 16:
                length = (opcode & 7) or reader.extended_length(7)
                length += 2
                word = reader.word()
                back = ((opcode & 8) << 11) + (word >> 2)
                if back == 0:
                    return bytes(out)
                distance = LONG_DISTANCE_BASE + back
                trailing = word & 3
            else:
                length = 2
                distance = 1 + (opcode >> 2) + (reader.byte() << 2)
                trailing = opcode & 3
            _copy_match(out, distance, length)
            state = "trailing"

        else:  # state == "trailing"
            if trailing == 0:
                state = "instruction"
                continue
            out += reader.take(trailing)
            state = "before_match"
