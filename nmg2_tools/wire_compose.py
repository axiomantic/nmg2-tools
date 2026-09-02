"""The `.pch2`-to-wire reassembler oracle.

This module reads a parsed `.pch2` file through :mod:`nmg2_tools.pch2` -- which
FRAMES objects and decodes NO payload semantics -- and re-emits each object in
the USB wire framing the firmware's message worker reassembles: one message per
object, `[1-byte type][2-byte big-endian length][payload]`, followed by the
CRC-16/CCITT-XMODEM (polynomial 0x1021, most significant bit first,
initial value 0, no final exclusive-or) computed over that message's payload
bytes and stored big-endian.

THE CRC COMES FROM THE FIRMWARE'S TABLE, NOT FROM THE ORACLE ARITHMETIC.
The checksum is computed through :func:`nmg2_tools.crc_crosscheck.table_walk`
over the committed fixture table at ``nmg2_tools/testdata/crc_table_firmware.bin``
-- the table the firmware's boot builder fills at ``0x3012C080``. The fixture is
DERIVED (the firmware builds the table at boot; it is not stored in the image),
and the test pins it by its recorded sha256 digest.

THE FILE-AGAINST-WIRE DIFFERENCES, and what this module does about each:

1. The variation count is 9 in a file and 10 on the wire, and it affects the
   0x4D and 0x65 objects. This module composes the record for the wire and
   applies the difference. It does NOT interpret the payload: the count byte is
   located at the payload's first byte, which is where the committed corpus
   writes it (``synth_pch2.generate`` writes ``bytes([9]) + indices`` for the
   ``wire_variation_count.pch2`` fixture), and a wire record carries 10 there.
   A 0x65 payload that decodes through the nine-variation bit layout gets a
   FULL tenth variation appended -- a copy of the last variation with its
   index renumbered -- by :func:`_morph_payload_tenth_variation`. A single
   filler byte does not work: the firmware's 0x65 reader (``FUN_3002DC84``)
   walks the section as a continuous bit stream, so a short tenth variation
   leaves it reading the FOLLOWING chunk's bytes as a parameter count and
   overshooting the section. Its per-variation footprint is an 8-bit index,
   MorphCount 7-bit fields, an 8-bit parameter count, then that many 29-bit
   parameters. A 0x4D payload, and any 0x65 the layout does not fully
   describe, still take the count rewrite plus one zero filler byte.
2. Two extra raw bytes, 0x2D 0x00, follow the 0x21 chunk on the wire. The
   parser records whether the file carried them (:attr:`Pch2File.usb_trailer`);
   the wire side ALWAYS carries them, so this module appends them after a 0x21
   object's message when the file form lacked them.
3. Morph parameter names are omitted on write in both paths. The file carries
   no name, so there is nothing to strip.

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
# file does (difference 1).
VARIATION_COUNT_TYPES = (0x4D, 0x65)

FILE_VARIATION_COUNT = 9
WIRE_VARIATION_COUNT = 10

# The appended representation of the tenth variation on a 0x4D object: one
# zero byte. The 0x4D reader (FUN_3002d962) consumed the +1-byte form
# normally in the 2026-08-30 run, so its appended byte stays minimal.
TENTH_VARIATION_BYTE = 0x00

# The 0x65 tenth-variation rule (decompile FUN_3002dc84 @ 0x3002dc84, the
# chunk dispatcher's 0x65 case; measured against the BackTo72 file). The
# firmware's reader walks a CONTINUOUS bit stream whose per-variation
# footprint is ``8-bit index + MorphCount x 7 bits + 8-bit ParamCount +
# ParamCount x 29 bits``, with the MorphCount reads covering the file form's
# Reserved0/1/2 bytes and the ParamCount read landing on the file form's
# per-variation MorphCount byte. A 0x65 whose file form opens with the 9
# variation count therefore needs a FULL tenth variation appended -- the
# copy of the LAST variation (the standard convention: a fresh patch has
# all variations identical unless edited) -- not a filler byte. With nine
# variations and a one-byte filler the reader's tenth pass reads the next
# chunk's bytes as a seventh ParamCount and overshoots by 37 bytes
# (measured: 329 consumed against a 292-byte frame, 2026-08-30 run).
MORPH_VARIATION_COUNT_TYPES = (0x65,)

# Difference 2: the raw two bytes that follow the 0x21 chunk on the wire. They
# are the parser's USB_TRAILER pair; the wire side always carries them.
TYPE_0X21 = pch2.TYPE_0X21

# ---------------------------------------------------------------------------
# The patch-load message level. The framing below is the message-level form
# the firmware's receive path reassembles, measured from two agreeing
# sources: the real wire captures (sirlenselot/g2fx, capture-008
# and capture-002, validated byte-for-byte against g2fx's own
# Usb.prepareSendBuffer) and g2fx's Patch.writeMessage / Performance
# .writeMessage. Pad-to-64 was an instrument artifact and does NOT apply here:
# totals are not 64-multiples on the real wire.
#
#     [2-byte BE total][body][2-byte BE CRC-16/CCITT-XMODEM over body]
#
# total counts the WHOLE frame INCLUDING the 2 prefix bytes; the CRC sits
# DIRECTLY after the body with no pad, big-endian, and the firmware's table
# walk (crc_crosscheck) is its algorithm.
#
# The BODY of a patch load:
#
#     [0x01][S_SLOT_REQ+slot][V_NEW_PATCH][0x37][0x00 0x00 0x00]
#     [entry name][object chain]
#
# 0x01 is M_CMD, 0x37 is O_CREATE (g2fx Codes.java), V_NEW_PATCH is 0x53,
# S_SLOT_REQ is 0x28 (slot 0), and the three 0x00 bytes are unexplained in
# g2fx too (its own source marks them `// ??`) but present in every capture.
# The entry name is g2fx's Protocol.EntryName field: a StringField(16,
# lengthWithTerm) whose wire form is the name's characters followed by a
# single 0x00 terminator, or exactly 16 characters with NO terminator when
# the name fills the field (measured: capture-002's 13-char perf name carries
# the terminator, capture-008's 16-char patch name does not).
#
# DIFFERENCE 2 DOES NOT FIRE ON THIS MESSAGE. The `0x2D 0x00`
# trailer was measured on the DEVICE-to-host dump family (capture-007's
# inbound 0x21 chunk carries it); the HOST-to-device O_CREATE chain of
# capture-008 carries no 2D 00 anywhere in its 861-byte body, and its CRC
# validates over the bytes as they stand. The per-object
# :func:`compose_message` keeps its insertion for the dump direction; the
# message-level composer below appends none.

M_CMD = 0x01
O_CREATE = 0x37
S_SLOT_REQ = 0x28
S_PERF_REQ = 0x2C
V_NEW_PATCH = 0x53
V_NEW_PERF = 0x42

ENTRY_NAME_LENGTH = 16


def entry_name_field(name: str) -> bytes:
    """The wire form of g2fx's Protocol.EntryName field for ``name``.

    The field is a StringField(16, lengthWithTerm) (g2fx Protocol.java:584):
    the name's characters, then a single 0x00 terminator, or exactly 16
    characters with NO terminator when the name fills the field. A name
    longer than 16 characters raises ValueError: g2fx truncates with a log
    warning, and a silently short field would misalign the chain behind it.
    """
    if len(name) > ENTRY_NAME_LENGTH:
        raise ValueError(
            f"entry name {name!r} exceeds the 16-character field length"
        )
    if len(name) == ENTRY_NAME_LENGTH:
        return name.encode("ascii")
    return name.encode("ascii") + b"\x00"


def compose_patch_load_body(
    file_data: bytes, name: str, slot: int = 0
) -> bytes:
    """The BODY of a patch-load message: header, entry name, object chain.

    The header is ``01 28+slot 53 37 00 00 00`` (M_CMD, S_SLOT_REQ+slot,
    V_NEW_PATCH, O_CREATE, three zeros). The chain is the `.pch2` file's
    object chain with the file-to-wire transformations of
    :func:`message_payload` applied (difference 1; difference 2 does not
    fire on the host-to-device form, see the module note).

    The chain carries NO per-object CRC: the message-level CRC below covers
    the whole body, so the object-level checksums the per-object composer
    appends would be bytes the firmware's chain walk reads as payload.
    """
    parsed = pch2.parse(file_data)
    chain = bytearray()
    for obj in parsed.objects:
        payload = message_payload(obj.type, obj.payload)
        chain += bytes([obj.type]) + len(payload).to_bytes(2, "big") + payload
    return (
        bytes([M_CMD, S_SLOT_REQ + slot, V_NEW_PATCH, O_CREATE, 0x00, 0x00, 0x00])
        + entry_name_field(name)
        + bytes(chain)
    )


def frame(body: bytes, table: tuple[int, ...]) -> bytes:
    """Frame a body at the message level: total prefix, body, trailing CRC.

    Returns ``[2-byte BE total][body][2-byte BE CRC]`` where total counts the
    WHOLE frame including the prefix (measured 865 and 14,664 on the real
    wire) and the CRC is the firmware's table walk over the body, big-endian,
    DIRECTLY after the body with no pad.
    """
    total = 2 + len(body) + 2
    return (
        total.to_bytes(2, "big")
        + body
        + crc_crosscheck.table_walk(body, table).to_bytes(2, "big")
    )


def compose_patch_load(
    pch2_path: str | pathlib.Path, name: str, slot: int = 0
) -> bytes:
    """The full patch-load message for the `.pch2` file at ``pch2_path``.

    One wire frame: the 0x01/0x37 body of :func:`compose_patch_load_body`
    inside the :func:`frame` envelope. NOT padded to 64; termination on the wire is the
    short last USB packet, which is the transport's business, not this
    function's.
    """
    body = compose_patch_load_body(pathlib.Path(pch2_path).read_bytes(), name, slot)
    return frame(body, fixture_table())


def compose_patch_load_transfer(
    pch2_path: str | pathlib.Path, name: str, slot: int = 0
) -> bytes:
    """The WHOLE-transfer form used by the runtime instrument.

    The transfer envelope wraps the message frame of
    :func:`compose_patch_load` once more:
    ``[2-byte BE total][body][2-byte BE CRC]`` where body is the
    0x01/0x37 message itself and total counts the whole transfer. This is
    the `[total][body][CRC]` shape at the transfer level, with the message
    level's own total and CRC carried INSIDE the body.
    """
    message = compose_patch_load(pch2_path, name, slot)
    body = message
    total = 2 + len(body) + 2
    return (
        total.to_bytes(2, "big")
        + body
        + crc_crosscheck.table_walk(body, fixture_table()).to_bytes(2, "big")
    )


def fixture_table() -> tuple[int, ...]:
    """The committed fixture table, read as 256 big-endian entries.

    The test pins the fixture's bytes by sha256, so a truncated, padded or
    hand-edited fixture fails there rather than silently checksumming through
    a reshaped table.
    """
    with open(crc_crosscheck.fixture_path(), "rb") as handle:
        return crc_crosscheck.table_from_bytes(handle.read())


class _BitReader:
    """An MSB-first bit reader over ``bytes`` -- the g2fx/protocol bit order."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def get(self, count: int) -> int:
        value = 0
        for _ in range(count):
            value = (
                (value << 1)
                | ((self._data[self._pos >> 3] >> (7 - (self._pos & 7))) & 1)
            )
            self._pos += 1
        return value

    def get_position(self) -> int:
        """The bit position the next :meth:`get` reads from."""
        return self._pos


class _BitWriter:
    """An MSB-first bit writer; the counterpart of :class:`_BitReader`."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._pos = 0

    def put(self, count: int, value: int) -> None:
        for shift in range(count - 1, -1, -1):
            if self._pos % 8 == 0:
                self._buf.append(0)
            if (value >> shift) & 1:
                self._buf[self._pos // 8] |= 0x80 >> (self._pos % 8)
            self._pos += 1

    def pad_to_byte(self) -> None:
        while self._pos % 8:
            self._pos += 1

    def bytes(self) -> bytes:
        return bytes(self._buf)


def _morph_payload_tenth_variation(payload: bytes) -> bytes:
    """The wire payload for a 0x65 object whose file form carries 9 variations.

    The file form is the g2fx ``MorphParameters`` layout: the variation count
    (8 bits), the morph count (4), twenty reserved bits, then per variation
    the variation index (4 bits), three reserved fields (24, 24, 8), the
    variation's morph count (8), that many 29-bit morph parameters (2+8+7+4+8)
    and a 4-bit reserved tail, with the whole section padded to a byte at the
    end. The transform decodes the nine variations, re-emits them with the
    count rewritten to 10, and appends the LAST variation again as the tenth
    with its variation index renumbered.

    A payload that does not decode exactly through that layout -- the
    committed synthetic corpus (`wire_variation_count.pch2`) opens a 0x65
    with the count byte plus nine one-byte indices, and some real corpus
    files carry fewer than nine fully-encoded variations -- raises
    ``ValueError``, and the caller falls back to the filler form: expanding
    a payload the layout does not fully describe would corrupt fields the
    transform does not name.
    """
    if len(payload) * 8 < 32 + 8 * 275 + 72:
        raise ValueError(
            "0x65 payload is too short to hold the nine-variation file layout"
        )
    reader = _BitReader(payload)
    reader.get(8)
    morph_count = reader.get(4)
    reserved = reader.get(20)
    variations = []
    for _ in range(9):
        if reader.get_position() + 72 > len(payload) * 8:
            raise ValueError(
                "0x65 payload ends inside the nine-variation layout"
            )
        index = reader.get(4)
        reserved0 = reader.get(24)
        reserved1 = reader.get(24)
        reserved2 = reader.get(8)
        var_morph_count = reader.get(8)
        if reader.get_position() + var_morph_count * 29 + 4 > len(payload) * 8:
            raise ValueError(
                "0x65 payload ends inside a variation's parameter list"
            )
        params = []
        for _ in range(var_morph_count):
            location = reader.get(2)
            module = reader.get(8)
            param = reader.get(7)
            morph = reader.get(4)
            rng = reader.get(8)
            params.append((location, module, param, morph, rng))
        tail = reader.get(4)
        variations.append((index, reserved0, reserved1, reserved2,
                           var_morph_count, params, tail))
    if reader.get_position() != len(payload) * 8:
        raise ValueError(
            "0x65 payload holds bytes beyond the nine-variation layout"
        )
    writer = _BitWriter()
    writer.put(8, WIRE_VARIATION_COUNT)
    writer.put(4, morph_count)
    writer.put(20, reserved)
    for index, reserved0, reserved1, reserved2, count, params, tail in (
        variations + [variations[-1]]
    ):
        writer.put(4, index)
        writer.put(24, reserved0)
        writer.put(24, reserved1)
        writer.put(8, reserved2)
        writer.put(8, count)
        for location, module, param, morph, rng in params:
            writer.put(2, location)
            writer.put(8, module)
            writer.put(7, param)
            writer.put(4, morph)
            writer.put(8, rng)
        writer.put(4, tail)
    writer.pad_to_byte()
    return writer.bytes()


def message_payload(object_type: int, payload: bytes) -> bytes:
    """Return the payload the WIRE message carries for one file object.

    Two payload transformations exist, both difference 1:

    - a 0x65 object whose payload opens with the FILE variation count gets
      the full tenth-variation transform of
      :func:`_morph_payload_tenth_variation`;
    - a 0x4D object whose payload opens with the FILE variation count gets
      the count rewritten to the wire's 10 and one appended byte.
    The predicate is the count byte itself, because the payloads stay opaque:
    a 0x65 whose first byte is NOT the file count is not demonstrating the
    variation-count form (the committed `wire_morph_names.pch2` opens a 0x65
    with a morph count of 8), and raising it would corrupt a field the
    difference does not name. Every other byte passes through unchanged.
    """
    if payload and payload[0] == FILE_VARIATION_COUNT:
        if object_type in MORPH_VARIATION_COUNT_TYPES:
            try:
                return _morph_payload_tenth_variation(payload)
            except ValueError:
                pass
        if object_type in VARIATION_COUNT_TYPES:
            return (
                bytes([WIRE_VARIATION_COUNT])
                + payload[1:]
                + bytes([TENTH_VARIATION_BYTE])
            )
    return payload


def compose_message(object_type: int, payload: bytes, table: tuple[int, ...]) -> bytes:
    """Return one wire message for one object: framing, payload, trailing CRC.

    The CRC covers the transformed payload alone — not the type and length
    framing bytes, unlike :func:`compose`, which walks the full body — and is
    computed through the firmware's table walk, then stored big-endian after
    the payload.
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
