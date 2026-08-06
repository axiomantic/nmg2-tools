"""The synthesized `.pch2` corpus generator. Task TOOL-12.

Design section 15.7 is the format specification. Design section 15.3 gives the
CRC. This generator reads those two sections and NOTHING ELSE.

EVERY BYTE OF THIS CORPUS IS AUTHORED BY THIS PROJECT. No Clavia byte enters
this repository in any form: not a committed file, not an inline array, not
base64. `nmg2_tools/testdata/pch2_synth/` is the only directory in any public
repository of this project where a `*.pch2` file may live, and REPO-11's
`no-clavia-payload` step enforces that.

THE CORPUS IS REGENERATED, NEVER HAND-EDITED. `tests/test_synth_pch2.py`
asserts that a fresh run reproduces every committed byte, so an edit made by
hand fails the check.

WHAT A GREEN RUN AGAINST THIS CORPUS PROVES, AND WHAT IT DOES NOT.

Design section 15.7 states it and this docstring repeats it because a reader of
the generator is the reader most likely to over-read the result. A green run
proves that the parser handles every case THIS SPECIFICATION NAMES. **It proves
nothing about real-world patch variety**, because nobody wrote this corpus from
real patches. A construct that a real Clavia patch uses and that section 15.7
does not describe passes here and fails against the G2 Demo corpus, which is
private and informational by tier. That gap is known, stated and accepted.

WHAT THE SPECIFICATION FIXES, AND WHAT THIS GENERATOR AUTHORS.

Design section 15.7 fixes:

    a text header, a 2-byte binary header, then objects of
    [1-byte type][2-byte length][payload]. Fields are bit-packed and are not
    byte aligned.

Design section 15.3 fixes the CRC: CRC-16/CCITT, the XMODEM variant, polynomial
0x1021, most significant bit first, initial value 0, no final exclusive-or,
stored big-endian. In a `.pch2` file it covers the version and type bytes and
every chunk, and excludes only the trailing CRC. Section 15.3 also fixes the bit
order: the `0x39` LED payload is "the only reversed bit order in the protocol",
so every other bit-packed field is most significant bit first.

The specification fixes nothing else, and the rest is AUTHORED HERE. It is
listed so that a reader never mistakes an authored choice for a recovered fact:

    1. The text of the text header, and the NUL byte that ends it.
    2. The value of the version byte and of the type byte.
    3. The byte order of the 2-byte length field. Big-endian, because the CRC
       is stored big-endian and the target is a big-endian m68k.
    4. Every payload. Section 15.7 gives no payload layout for any object type,
       so each payload here states field WIDTHS and states no semantics.
    5. The names of the refusals in `MANIFEST.tsv`.

**Consequence, stated plainly:** this corpus proves framing, bit packing and the
CRC. It cannot prove payload semantics, because no authority in this project
states any.

WHICH OBJECT TYPES THE SPECIFICATION NAMES.

Section 15.7 names `0x21`, `0x4D` and `0x65` in its own text. Design section 18's
protocol test row names the bit-packed types as `0x21`, `0x4A`, `0x52`, `0x4D`,
`0x65`, `0x62`, `0x60` and `0x69`. `OBJECT_TYPES` is that union, sorted.

THE UPPER LENGTH BOUNDARY IS CAPPED BY A DIFFERENT RULE.

Section 15.7 asks for "the largest the 2-byte length field allows", which is a
payload of 0xFFFF bytes. REPO-11's PAYLOAD-CEILING fails a committed file above
65,536 bytes under `testdata/`, and 3 framing bytes plus 65,535 payload bytes
already exceed it. **The two rules cannot both hold for a committed file.** The
resolution: `length_boundaries.pch2` is exactly 65,536 bytes, which is the
largest a committed file may be, and `tests/test_synth_pch2.py` drives the true
0xFFFF boundary through `build_object` IN MEMORY, where no ceiling applies. The
boundary is therefore exercised and nothing over the ceiling is committed.
"""

from __future__ import annotations

import pathlib
from collections.abc import Iterable, Sequence

CORPUS_DIRECTORY = pathlib.Path(__file__).resolve().parent / "testdata" / "pch2_synth"

# REPO-11's PAYLOAD-CEILING. A committed file under `testdata/` may not exceed
# it. `nmg2_tools.payload_lint.SIZE_CEILING` carries the same number and this
# module states it again rather than importing it, because a corpus that
# silently followed a lint constant would change shape the day the lint moved.
SIZE_CEILING = 65_536

# Section 15.7 names 0x21, 0x4D and 0x65. Design section 18's protocol row names
# the other five bit-packed types. Sorted, so the tuple has one order.
OBJECT_TYPES = (0x21, 0x4A, 0x4D, 0x52, 0x60, 0x62, 0x65, 0x69)

# A type that no authority names. The malformed set uses it.
UNKNOWN_OBJECT_TYPE = 0xFF

# AUTHORED. The text header and the byte that ends it.
TEXT_HEADER = b"SYNTHESIZED PCH2 CORPUS\nGenerator=nmg2_tools.synth_pch2\n\x00"

# AUTHORED. The 2-byte binary header: the version byte and the type byte. The
# CRC of a file starts here, per design section 15.3.
BINARY_HEADER = b"\x01\x00"

CRC_POLYNOMIAL = 0x1021

MAX_PAYLOAD = 0xFFFF
MIN_FIELD_WIDTH = 1
MAX_FIELD_WIDTH = 32

# The length `bad_length_past_end.pch2` declares. It is DELIBERATELY NOT
# `MAX_PAYLOAD`. That file writes its length through its own `to_bytes` call
# rather than through `build_object`, so it is a SECOND code site for the 2-byte
# length field and needs its own asymmetric value. 0xFFFF is a byte palindrome:
# written little-endian it is the same two bytes, so a byte order fault at this
# site would be invisible to every test in this repository, the
# regenerate-against-the-tree check included. 0xFF01 is not a palindrome, and it
# still runs far past the end of a file of a few dozen bytes.
PAST_END_LENGTH = 0xFF01


class SynthPch2Error(ValueError):
    """A corpus byte this generator refuses to write.

    The message starts with a name: `SYNTHPCH2-BAD-OBJECT-TYPE`,
    `SYNTHPCH2-PAYLOAD-TOO-LONG`, `SYNTHPCH2-BAD-WIDTH` or
    `SYNTHPCH2-VALUE-TOO-WIDE`.
    """


def crc16_ccitt(data: bytes) -> int:
    """Return the CRC-16/CCITT (XMODEM) of `data`.

    Design section 15.3: polynomial 0x1021, most significant bit first, initial
    value 0, no final exclusive-or. The published check value over the ASCII
    bytes `123456789` is 0x31C3, and the test asserts it against its own
    reference rather than against this function.
    """
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _bit in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC_POLYNOMIAL) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack_bits(fields: Sequence[tuple[int, int]]) -> bytes:
    """Pack `(width, value)` pairs, most significant bit first.

    Fields are bit-packed and are NOT byte aligned, so a field may cross a byte
    boundary. The result is padded with zero bits to the next whole byte.
    """
    accumulator = 0
    total = 0
    for index, (width, value) in enumerate(fields):
        if not MIN_FIELD_WIDTH <= width <= MAX_FIELD_WIDTH:
            raise SynthPch2Error(
                f"SYNTHPCH2-BAD-WIDTH: field {index} declares {width} bits, "
                f"and a width runs from {MIN_FIELD_WIDTH} to {MAX_FIELD_WIDTH}"
            )
        if not 0 <= value < (1 << width):
            raise SynthPch2Error(
                f"SYNTHPCH2-VALUE-TOO-WIDE: field {index} holds {value}, "
                f"which does not fit {width} bits"
            )
        accumulator = (accumulator << width) | value
        total += width

    if total == 0:
        return b""

    padding = (-total) % 8
    accumulator <<= padding
    return accumulator.to_bytes((total + padding) // 8, "big")


def build_object(type_: int, payload: bytes) -> bytes:
    """Return one object: `[1-byte type][2-byte length][payload]`.

    The length is the payload byte count, big-endian.
    """
    if not 0 <= type_ <= 0xFF:
        raise SynthPch2Error(
            f"SYNTHPCH2-BAD-OBJECT-TYPE: 0x{type_:X} does not fit the "
            f"1-byte type field"
        )
    if len(payload) > MAX_PAYLOAD:
        raise SynthPch2Error(
            f"SYNTHPCH2-PAYLOAD-TOO-LONG: {len(payload)} bytes do not fit the "
            f"2-byte length field"
        )
    return bytes([type_]) + len(payload).to_bytes(2, "big") + payload


def build_file(body: bytes, *, crc_error: int = 0) -> bytes:
    """Return a whole file: text header, binary header, `body`, trailing CRC.

    `crc_error` is exclusive-or'd into the stored CRC. A non-zero value writes a
    file whose CRC is wrong on purpose, which is one of the four malformed cases
    section 15.7 requires.
    """
    covered = BINARY_HEADER + body
    stored = crc16_ccitt(covered) ^ crc_error
    return TEXT_HEADER + covered + stored.to_bytes(2, "big")


def generate() -> dict[str, bytes]:
    """Return the whole corpus as `{file name: bytes}`, `MANIFEST.tsv` included.

    The result depends on nothing outside this module. No clock, no environment
    and no set iteration order takes part, so two calls give the same bytes and
    so does a call on another machine.
    """
    files: dict[str, bytes] = {}

    # The minimum well-formed file: one object of type 0x21 with no payload.
    files["min.pch2"] = build_file(build_object(0x21, b""))

    # Every object type the specification names, each with a one-byte payload
    # that carries the type's own index so that two objects never look alike.
    files["object_types.pch2"] = build_file(
        b"".join(
            build_object(type_, bytes([index]))
            for index, type_ in enumerate(OBJECT_TYPES)
        )
    )

    # Every bit-packed field at its minimum width, one interior width and its
    # maximum width. The interior width is 7, which is deliberately not a byte:
    # a reader that aligned to bytes disagrees on this file. Each object holds
    # that width's minimum value, an interior value and its maximum value.
    files["bit_widths.pch2"] = build_file(
        build_object(0x60, pack_bits([(1, 0), (1, 1), (1, 1)]))
        + build_object(0x60, pack_bits([(7, 0), (7, 0x2A), (7, 0x7F)]))
        + build_object(
            0x60, pack_bits([(32, 0), (32, 0x0F0F0F0F), (32, 0xFFFFFFFF)])
        )
    )

    # The boundary object lengths. A zero-length payload, then the largest
    # payload that keeps the whole file at the byte ceiling. The true field
    # maximum of 0xFFFF cannot be committed and the test drives it in memory.
    zero_length = build_object(0x21, b"")
    overhead = len(TEXT_HEADER) + len(BINARY_HEADER) + len(zero_length) + 3 + 2
    files["length_boundaries.pch2"] = build_file(
        zero_length + build_object(0x4A, b"\x5a" * (SIZE_CEILING - overhead))
    )

    # Difference 1. The variation count is 9 in a file and 10 on the wire, and
    # it affects 0x4D and 0x65. The corpus states the FILE count. Nobody knows
    # what the tenth variation holds, so nothing here states anything about it.
    variations = bytes([9]) + bytes(range(9))
    files["wire_variation_count.pch2"] = build_file(
        build_object(0x4D, variations) + build_object(0x65, variations)
    )

    # Difference 2. Two extra bytes, 0x2D 0x00, follow the 0x21 chunk in USB
    # dumps. They are RAW bytes and not an object, because an object header is
    # three bytes. Both forms are committed, so a parser must accept each.
    chunk_21 = build_object(0x21, b"\xaa\xbb")
    files["wire_extra_bytes_file.pch2"] = build_file(chunk_21)
    files["wire_extra_bytes_usb.pch2"] = build_file(chunk_21 + b"\x2d\x00")

    # Difference 3. Morph parameter names are omitted on write in both paths,
    # so the corpus carries the omitted form and never the present one.
    files["wire_morph_names.pch2"] = build_file(
        build_object(0x65, bytes([8]) + bytes(range(8)))
    )

    # The malformed set. Section 15.7: the parser must reject each with a NAMED
    # error, and `MANIFEST.tsv` is where the corpus states which name.
    #
    # A truncated object. The header is complete and the payload stops early.
    files["bad_truncated_object.pch2"] = build_file(
        bytes([0x4A]) + (8).to_bytes(2, "big") + b"\x01\x02\x03"
    )

    # A length that runs past the END OF THE FILE, which is a different fault
    # from a payload that merely stops early. The length is `PAST_END_LENGTH`
    # and not `MAX_PAYLOAD`, for the byte-order reason stated where that
    # constant is declared.
    files["bad_length_past_end.pch2"] = build_file(
        bytes([0x4A]) + PAST_END_LENGTH.to_bytes(2, "big")
    )

    # An unknown object type.
    files["bad_unknown_type.pch2"] = build_file(
        build_object(UNKNOWN_OBJECT_TYPE, b"\x00")
    )

    # A bad CRC. One bit is flipped in the low byte, so the file is wrong on
    # purpose and is not random.
    files["bad_crc.pch2"] = build_file(build_object(0x21, b"\x01"), crc_error=0x0001)

    files["MANIFEST.tsv"] = _manifest(files)
    return files


def write(directory: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Write the corpus and return the paths written, sorted by name."""
    target = CORPUS_DIRECTORY if directory is None else directory
    target.mkdir(parents=True, exist_ok=True)

    written = []
    for name, data in sorted(generate().items()):
        path = target / name
        path.write_bytes(data)
        written.append(path)
    return written


# The refusal each malformed file expects. The names are AUTHORED here, and
# TOOL-10 raises them.
_REFUSALS = {
    "bad_crc.pch2": "PCH2-BAD-CRC",
    "bad_length_past_end.pch2": "PCH2-LENGTH-PAST-END",
    "bad_truncated_object.pch2": "PCH2-TRUNCATED-OBJECT",
    "bad_unknown_type.pch2": "PCH2-UNKNOWN-OBJECT-TYPE",
}


def _manifest(files: Iterable[str]) -> bytes:
    """Return `MANIFEST.tsv`: one row for each corpus file.

    A malformed file names the refusal a parser must raise for it. Without this
    the parser test would carry the four names itself, and a corpus that changed
    shape could no longer disagree with it.
    """
    rows = [
        "# Task TOOL-12. Every byte of this corpus is authored by this project.",
        "# file\tkind\texpected_refusal",
    ]
    for name in sorted(files):
        refusal = _REFUSALS.get(name)
        kind = "malformed" if refusal else "wellformed"
        rows.append(f"{name}\t{kind}\t{refusal or '-'}")
    return ("\n".join(rows) + "\n").encode("ascii")


if __name__ == "__main__":  # pragma: no cover - a convenience entry point
    for written_path in write():
        print(written_path)
