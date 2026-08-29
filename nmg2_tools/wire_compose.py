"""The `.pch2`-to-wire reassembler oracle. Task TOOL-17, plan section 12.

This module reads a parsed `.pch2` file through :mod:`nmg2_tools.pch2` -- which
FRAMES objects and decodes NO payload semantics -- and re-emits each object in
the USB wire framing the firmware's message worker reassembles: one message per
object, `[1-byte type][2-byte big-endian length][payload]`, followed by the
PROTO-1 CRC-16/CCITT-XMODEM (polynomial 0x1021, most significant bit first,
initial value 0, no final exclusive-or) computed over that message's payload
bytes and stored big-endian.

THE CRC COMES FROM THE FIRMWARE'S TABLE, NOT FROM THE ORACLE ARITHMETIC.
The checksum is computed through :func:`nmg2_tools.crc_crosscheck.table_walk`
over the committed fixture table at ``nmg2_tools/testdata/crc_table_firmware.bin``
-- the table the firmware's boot builder fills at ``0x3012C080`` (TOOL-15). A
CRC this module emits is therefore the arithmetic the firmware's own worker
applies, entry for entry. The fixture is DERIVED (the firmware builds the table
at boot; it is not stored in the image), and the test pins it by its recorded
sha256 digest.

THE THREE FILE-AGAINST-WIRE DIFFERENCES (design section 15.7), and what this
module does about each:

1. The variation count is 9 in a file and 10 on the wire, and it affects the
   0x4D and 0x65 objects. This module composes the record for the wire and
   applies the difference. It does NOT interpret the payload: the count byte is
   located at the payload's first byte, which is where the committed corpus
   writes it (``synth_pch2.generate`` writes ``bytes([9]) + indices`` for the
   ``wire_variation_count.pch2`` fixture), and a wire record carries 10 there.
   What the tenth variation holds is not stated by any authority in this
   repository, so the appended representation is a zero byte and nothing more
   is claimed about it.
2. Two extra raw bytes, 0x2D 0x00, follow the 0x21 chunk on the wire. The
   parser records whether the file carried them (:attr:`Pch2File.usb_trailer`);
   the wire side ALWAYS carries them, so this module appends them after a 0x21
   object's message when the file form lacked them.
3. Morph parameter names are omitted on write in both paths. The file carries
   no name, so there is nothing to strip: this module needs no branch for the
   difference, and states that here rather than in dead code.

FIRST-BYTE FAMILIES. The firmware's USB message worker switches on the first
byte of each reassembled message; this module classifies each composed message
by that byte against the worker's accepted set:

    0x80                  ack-only
    0x81 / 0x82 / 0x83    store
    0x84 / 0x88           ack
    0x01                  slot-message
    anything else         UNKNOWN (printed, never hidden)

The classification is derived from the FIRST BYTE only. That a family is
accepted by the worker is a static fact about the dispatch table; it is NOT
proof that the payload this module composed is well-formed, because no payload
semantics are decoded here. The test states that caveat next to its assertion.
"""

from __future__ import annotations

import pathlib
import sys

from nmg2_tools import crc_crosscheck, pch2

# The message families the firmware worker accepts, keyed by first byte. The
# values are the family names the report prints.
ACK_ONLY = "ack-only"
STORE = "store"
ACK = "ack"
SLOT_MESSAGE = "slot-message"
UNKNOWN = "UNKNOWN"

FIRST_BYTE_FAMILIES: dict[int, str] = {
    0x80: ACK_ONLY,
    0x81: STORE,
    0x82: STORE,
    0x83: STORE,
    0x84: ACK,
    0x88: ACK,
    0x01: SLOT_MESSAGE,
}

# The object types whose variation count the wire carries one higher than the
# file does (design section 15.7, difference 1).
VARIATION_COUNT_TYPES = (0x4D, 0x65)

FILE_VARIATION_COUNT = 9
WIRE_VARIATION_COUNT = 10

# The appended representation of the tenth variation. No authority in this
# repository states what the tenth variation holds, so nothing is claimed for
# this byte beyond its presence.
TENTH_VARIATION_BYTE = 0x00

# Difference 2: the raw two bytes that follow the 0x21 chunk on the wire. They
# are the parser's USB_TRAILER pair; the wire side always carries them.
TYPE_0X21 = pch2.TYPE_0X21


def fixture_table() -> tuple[int, ...]:
    """The committed fixture table, read as 256 big-endian entries.

    The fixture is the one TOOL-15 committed; the test pins its bytes by
    sha256, so a truncated, padded or hand-edited fixture fails there and
    never silently checksums through a reshaped table.
    """
    with open(crc_crosscheck.fixture_path(), "rb") as handle:
        return crc_crosscheck.table_from_bytes(handle.read())


def message_payload(object_type: int, payload: bytes) -> bytes:
    """Return the payload the WIRE message carries for one file object.

    The only payload transformation is difference 1: for a 0x4D or 0x65 object
    whose payload opens with the FILE variation count, the count is rewritten
    to the wire's 10 and one appended byte represents the added variation.
    The predicate is the count byte itself, because the payloads stay opaque:
    a 0x65 whose first byte is NOT the file count is not demonstrating the
    variation-count form (the committed `wire_morph_names.pch2` opens a 0x65
    with a morph count of 8), and raising it would corrupt a field the
    difference does not name. Every other byte passes through unchanged.
    """
    if (
        object_type in VARIATION_COUNT_TYPES
        and payload
        and payload[0] == FILE_VARIATION_COUNT
    ):
        return bytes([WIRE_VARIATION_COUNT]) + payload[1:] + bytes([TENTH_VARIATION_BYTE])
    return payload


def compose_message(object_type: int, payload: bytes, table: tuple[int, ...]) -> bytes:
    """Return one wire message for one object: framing, payload, trailing CRC.

    The CRC covers the message's payload bytes (type, length and payload per
    the PROTO-1 framing the firmware reassembles) and is computed through the
    firmware's table walk, then stored big-endian after the payload.
    """
    payload = message_payload(object_type, payload)
    body = bytes([object_type]) + len(payload).to_bytes(2, "big") + payload
    return body + crc_crosscheck.table_walk(payload, table).to_bytes(2, "big")


def message_payload_reversed(object_type: int, wire_payload: bytes) -> bytes:
    """Return the FILE payload a wire payload converts back to (difference 1).

    The inverse of :func:`message_payload` for a 0x4D or 0x65 object opening
    with the wire count: the count falls to the file's 9 and the appended
    tenth-variation byte is dropped, so the round trip recovers the file's
    own bytes. Every other byte passes through unchanged.
    """
    if (
        object_type in VARIATION_COUNT_TYPES
        and len(wire_payload) >= 2
        and wire_payload[0] == WIRE_VARIATION_COUNT
    ):
        return bytes([FILE_VARIATION_COUNT]) + wire_payload[1:-1]
    return wire_payload


def compose(file_data: bytes, table: tuple[int, ...]) -> list[bytes]:
    """Parse a `.pch2` file and return its wire messages, one per object.

    The raw 0x2D 0x00 trailer bytes follow the 0x21 chunk on the wire ALWAYS,
    so they are appended after that chunk's framing-plus-payload whatever the
    file form carried: a file-form chunk gains the pair (difference 2), and a
    USB-form chunk's own pair was consumed by the parser into ``usb_trailer``,
    so appending once recreates the wire bytes exactly and nothing is
    double-appended. The trailing CRC covers the message's covered bytes --
    framing, payload and, for a 0x21 chunk, the pair -- and is the LAST two
    bytes of every composed message.
    """
    parsed = pch2.parse(file_data)
    messages = []
    for obj in parsed.objects:
        payload = message_payload(obj.type, obj.payload)
        body = bytes([obj.type]) + len(payload).to_bytes(2, "big") + payload
        if obj.type == TYPE_0X21:
            body += pch2.USB_TRAILER
        messages.append(
            body + crc_crosscheck.table_walk(body, table).to_bytes(2, "big")
        )
    return messages


def family_of(first_byte: int) -> str:
    """The worker family a message's first byte names, or ``UNKNOWN``."""
    return FIRST_BYTE_FAMILIES.get(first_byte, UNKNOWN)


def report_lines(messages: list[bytes]) -> list[str]:
    """The one-line-per-message table: index, first byte, length, CRC, family.

    The CRC is read back out of the composed message's last two bytes, so the
    line reports what the message carries rather than what the composer
    intended: a message too short to hold framing plus a CRC reports ``----``.
    """
    lines = []
    for index, message in enumerate(messages):
        first = message[0]
        if len(message) >= 5:
            crc = f"{int.from_bytes(message[-2:], 'big'):#06x}"
        else:
            crc = "----"
        lines.append(
            f"msg {index} first={first:#04x} len={len(message)} crc={crc} "
            f"family={family_of(first)}"
        )
    return lines


def hex_dump(messages: list[bytes]) -> str:
    """The messages as one hex block, blank-line separated per message."""
    return "\n\n".join(message.hex() for message in messages)


def run(path: str | pathlib.Path) -> int:
    """Compose the file at ``path`` and print the table and hex dump.

    Returns 0 on a parseable file. A malformed file raises the parser's own
    named :class:`pch2.Pch2Error`, which ``main`` turns into exit 2 with the
    error's message on stderr.
    """
    table = fixture_table()
    messages = compose(pathlib.Path(path).read_bytes(), table)

    output = [*report_lines(messages), "", hex_dump(messages)]
    sys.stdout.write("\n".join(output) + "\n")
    return 0


def main(argv: list[str]) -> int:
    """The module entry point: exit 0 always on a parseable file, 2 otherwise."""
    if len(argv) != 1:
        print("usage: python3 -m nmg2_tools.wire_compose <file.pch2>", file=sys.stderr)
        return 2
    try:
        return run(argv[0])
    except pch2.Pch2Error as error:
        print(f"wire_compose: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - the console entry point
    raise SystemExit(main(sys.argv[1:]))
