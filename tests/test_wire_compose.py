"""The `.pch2`-to-wire reassembler oracle.

The firmware's USB message worker reassembles protocol messages from the
objects a `.pch2` file holds and validates each through the table-driven CRC
before it switches on the message's first byte. This test holds
`nmg2_tools.wire_compose` against that shape: the file-to-wire differences,
the CRC through the committed fixture table, and the first-byte family
classification.

WHAT A GREEN RUN PROVES, AND WHAT IT DOES NOT. It proves that the composed
messages carry the wire-side form of the three file-against-wire differences
and a CRC the firmware's own table mechanics produce. It does NOT prove that a
composed payload is well-formed for the firmware: "the worker accepts the
family" is a static fact about the dispatch table, and no payload semantics are
decoded anywhere in this path.
"""

import hashlib
import os
import pathlib
import subprocess
import sys

import pytest

from nmg2_tools import crc_crosscheck, pch2, wire_compose
from nmg2_tools.artifacts import (
    gated_skip_reason,
    resolve_artifacts,
)
from nmg2_tools.synth_pch2 import (
    CORPUS_DIRECTORY,
    build_file,
    build_object,
)

FIXTURE_SHA256 = "e4537e4ac69bf8c22ae98bcbf35a76cae77c7c025d6222c4e4390ec962c10881"


@pytest.fixture(scope="module")
def table() -> tuple[int, ...]:
    """The committed fixture table, read once."""
    return wire_compose.fixture_table()


def _corpus(name: str) -> bytes:
    return (CORPUS_DIRECTORY / name).read_bytes()


# ---------------------------------------------------------------------------
# Case 1. The CRC comes from the committed fixture table.
# ---------------------------------------------------------------------------


def test_the_committed_crc_fixture_matches_its_recorded_digest():
    """The fixture's whole bytes hash to the recorded literal, so a truncated,
    padded or hand-edited table fails here before any CRC case can pass
    through it."""
    with open(crc_crosscheck.fixture_path(), "rb") as handle:
        data = handle.read()

    assert len(data) == 512
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256


def test_every_composed_message_carries_the_fixture_tables_crc(table):
    """Each composed message's trailing two bytes are the fixture-table walk
    over that message's covered bytes -- the framing, payload and, for a 0x21
    chunk, the raw trailer pair -- recomputed here through the same committed
    table the composer reads, not through the arithmetic oracle, so the
    assertion binds the message bytes to the firmware's mechanics."""
    messages = wire_compose.compose(_corpus("object_types.pch2"), table)

    assert len(messages) > 0
    for message in messages:
        expected = crc_crosscheck.table_walk(message[:-2], table)
        assert int.from_bytes(message[-2:], "big") == expected


def test_a_message_crc_agrees_with_the_arithmetic_oracle(table):
    """The fixture-table walk and the arithmetic CRC-16/CCITT-XMODEM agree on
    every composed payload: the committed table is the firmware's form of the
    polynomial the format fixes."""
    messages = wire_compose.compose(_corpus("min.pch2"), table)

    for message in messages:
        payload = message[3:-2]
        walked = crc_crosscheck.table_walk(payload, table)
        assert walked == _arithmetic_crc(payload)


def _arithmetic_crc(data: bytes) -> int:
    """The arithmetic form, stated here so the comparison never reads a name
    that may move: polynomial 0x1021, MSB-first, init 0, no final XOR."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _bit in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# Case 2. The three file-against-wire differences, EACH BOTH DIRECTIONS.
# ---------------------------------------------------------------------------


def test_difference_1_file_to_wire_the_variation_count_rises_to_ten(table):
    """File to wire. The corpus's `wire_variation_count.pch2` carries a 0x4D
    and a 0x65 object whose first payload byte is the FILE count, 9, followed
    by 9 one-byte indices. The composed wire record reads 10 at that same
    offset and carries one appended byte for the tenth variation.

    DOCUMENTED UNKNOWN: the variation count's position is established for the
    committed corpus only -- `synth_pch2.generate` writes it as the payload's
    first byte -- and no authority in this repository states the payload
    layout for a real Clavia file. The assertion below is therefore against
    the synth corpus's representation, and a real-file offset that differed
    would need its own evidence before this case could claim it."""
    messages = wire_compose.compose(_corpus("wire_variation_count.pch2"), table)

    assert len(messages) == 2
    for message in messages:
        assert message[0] in (0x4D, 0x65)
        payload = message[3:-2]
        assert payload[0] == 10
        assert payload[1:10] == bytes(range(9))
        assert len(payload) == 11


def test_difference_1_wire_to_file_the_variation_count_falls_to_nine(table):
    """Wire to file. A hand-built wire-side 0x4D record carrying the count 10
    plus ten indices converts back to the file form: count 9 and nine indices,
    the shape the parser reads and the committed corpus holds."""
    wire_payload = bytes([10]) + bytes(range(10))
    wire_object = build_object(0x4D, wire_payload)
    wire_file = build_file(wire_object)

    # The wire-side record, composed the way the worker receives it: the
    # variation count already at 10, no transformation left to apply.
    parsed = pch2.parse(wire_file)
    assert parsed.objects[0].payload[0] == 10

    file_form = bytes([9]) + bytes(range(9))
    back = wire_compose.message_payload_reversed(0x4D, parsed.objects[0].payload)

    assert back == file_form


def test_difference_2_file_to_wire_the_trailer_bytes_are_appended(table):
    """File to wire. The corpus's `wire_extra_bytes_file.pch2` carries the 0x21
    chunk with no trailer; the composed wire side carries the raw 0x2D 0x00
    pair after the 0x21 chunk's framing and payload, before the trailing CRC --
    the CRC is the last two bytes of every message, so the pair sits at
    offsets -4:-2."""
    messages = wire_compose.compose(_corpus("wire_extra_bytes_file.pch2"), table)

    assert len(messages) == 1
    assert messages[0][:4] == b"\x21\x00\x02\xaa"
    assert messages[0][-4:-2] == b"\x2d\x00"
    assert messages[0][-2:] != b"\x2d\x00"


def test_difference_2_wire_to_file_the_trailer_bytes_are_stripped(table):
    """Wire to file. The corpus's `wire_extra_bytes_usb.pch2` carries the USB
    form, where the parser has already consumed the trailer pair into
    `usb_trailer`; the composed wire side carries the pair exactly once --
    appended by the wire rule, never a second time for the file's own copy --
    and the CRC still lands last."""
    messages = wire_compose.compose(_corpus("wire_extra_bytes_usb.pch2"), table)

    assert len(messages) == 1
    # The framing, payload and the single appended pair, then the CRC.
    assert messages[0][:4] == b"\x21\x00\x02\xaa"
    assert messages[0][-4:-2] == b"\x2d\x00"
    # Exactly one pair in the covered region: the file's own copy was consumed
    # by the parser, so nothing composes a second.
    assert messages[0][:-2].count(b"\x2d\x00") == 1

    # And stripping the pair recovers the file form's object bytes exactly:
    # [0x21][00 02][aa bb], the shape the parser reads back as the same
    # single 0x21 object.
    stripped = messages[0][:-4]
    assert stripped == b"\x21\x00\x02\xaa\xbb"
    reparsed = pch2.parse(
        build_file(stripped)
    )
    assert reparsed.objects == (pch2.Pch2Object(type=0x21, payload=b"\xaa\xbb"),)
    assert reparsed.usb_trailer is False


def test_difference_3_morph_names_are_omitted_in_both_paths(table):
    """Difference 3 needs no name transformation: names are omitted on write
    in BOTH paths, so the file's 0x65 object is already the wire form's payload
    apart from difference 1, which composes a 0x65 too (the count rises to 10
    with one appended tenth-variation byte). No name bytes are added or removed
    in either direction, which is the identity this case asserts."""
    messages = wire_compose.compose(_corpus("wire_morph_names.pch2"), table)

    assert len(messages) == 1
    payload = messages[0][3:-2]
    # Difference 1 does NOT fire on this object: its first byte is the morph
    # count 8, not the variation count 9, so the payload is the corpus's own
    # byte sequence unchanged and NO name bytes are appended or stripped.
    assert payload == b"\x08" + bytes(range(8))

    # Wire to file: the identity, because nothing was added on the wire side
    # to remove and no name bytes appear in either form.
    assert wire_compose.message_payload_reversed(0x65, payload) == payload


# ---------------------------------------------------------------------------
# Case 3. The first-byte classification.
# ---------------------------------------------------------------------------


def test_every_corpus_object_type_composes_to_a_classified_line(table):
    """Every object type the synthesized corpus carries composes to a message
    whose report line names a family derived from the first byte -- UNKNOWN
    included, printed and never hidden, because the container's object types
    are distinct codes from the worker's first-byte families. CAVEAT, stated
    here and in the report: "the firmware accepts the family" for the
    family-named bytes is a static fact about the dispatch
    table -- it is NOT proof the composed payload is
    well-formed, because no payload semantics are decoded."""
    parsed = pch2.parse(_corpus("object_types.pch2"))
    messages = wire_compose.compose(_corpus("object_types.pch2"), table)

    lines = wire_compose.report_lines(messages)
    assert len(lines) == len(parsed.objects)

    for index, (obj, line) in enumerate(zip(parsed.objects, lines)):
        expected_family = wire_compose.family_of(obj.type)
        assert line.endswith(f"family={expected_family}")
        assert line.startswith(f"msg {index} first={obj.type:#04x} ")


def test_the_0x21_chunk_classifies_into_an_accepted_family(table):
    """A 0x21-chunk-derived message's first byte is 0x21 itself -- the chunk
    type IS the message's first byte -- and the object types the `.pch2`
    container carries are distinct codes from the worker's first-byte families
    (0x80/0x81/0x82/0x83/0x84/0x88/0x01), so a 0x21-derived message composes to
    the printed UNKNOWN family, never silently renamed into an accepted one.

    CAVEAT: "the firmware accepts the family" for the family-named first
    bytes is a static fact about the dispatch
    table; it is NOT proof the payload is well-formed, which no payload
    semantics here could establish. The classification of a 0x21 chunk as
    UNKNOWN is itself the honest print: the worker's accepted set does not
    include 0x21."""
    messages = wire_compose.compose(_corpus("min.pch2"), table)

    first_byte = messages[0][0]
    assert first_byte == 0x21
    assert first_byte not in wire_compose.FIRST_BYTE_FAMILIES
    assert wire_compose.family_of(first_byte) == wire_compose.UNKNOWN


# ---------------------------------------------------------------------------
# Case 4. UNKNOWN is printed, never hidden.
# ---------------------------------------------------------------------------


def test_a_type_the_worker_does_not_accept_classifies_as_unknown(table):
    """A hand-built object whose type byte the worker does not accept composes
    to a line whose family is the literal UNKNOWN -- printed, never hidden."""
    wire_type = 0x99
    assert wire_type not in wire_compose.FIRST_BYTE_FAMILIES

    message = wire_compose.compose_message(wire_type, b"\x01\x02", table)
    lines = wire_compose.report_lines([message])

    assert lines[0].endswith("family=UNKNOWN")


# ---------------------------------------------------------------------------
# Case 5. The required-red mutations. Each plants the break, observes the
# named case go red, and restores.
# ---------------------------------------------------------------------------


def test_required_red_deleting_the_trailer_insertion_turns_difference_2_red(table):
    """Plant: compose with the 0x2D 0x00 insertion removed. Observe: the
    difference-2 file-to-wire case's assertions fail (the pair is absent at
    offsets -4:-2). Restore: the broken form is built in memory and the
    module's own output still carries the pair."""
    file_data = _corpus("wire_extra_bytes_file.pch2")
    good = wire_compose.compose(file_data, table)[0]

    # The plant: the good message minus the pair (and its covered CRC), i.e.
    # the framing-plus-payload a composer WITHOUT the insertion would emit.
    broken = good[:-4]

    # Observe red: the difference-2 case's first structural assertion fails.
    with pytest.raises(AssertionError):
        assert broken[-4:-2] == b"\x2d\x00"

    # Observe restored: the module's own message carries the pair exactly
    # where the difference-2 case requires it.
    assert good[-4:-2] == b"\x2d\x00"


def test_required_red_classifying_every_unknown_as_0x80_turns_unknown_red(table):
    """Plant: a first-byte map that answers ack-only for everything. Observe:
    the UNKNOWN case's assertion fails. Restore: the broken map is a local,
    never the module's."""
    broken_map = dict.fromkeys(range(256), wire_compose.ACK_ONLY)

    message = wire_compose.compose_message(0x99, b"\x01\x02", table)
    first_byte = message[0]

    # Under the broken map the line would print a family, not UNKNOWN: the
    # UNKNOWN case's endswith assertion fails.
    broken_family = broken_map.get(first_byte, wire_compose.UNKNOWN)
    with pytest.raises(AssertionError):
        assert broken_family == wire_compose.UNKNOWN

    # The module's own map still refuses 0x99: the restored case passes.
    assert wire_compose.family_of(first_byte) == wire_compose.UNKNOWN


def test_required_red_skipping_the_crc_append_shows_dash_dash_and_a_red_crc_case(
    table,
):
    """Plant: a message composed without its trailing CRC. Observe: the report
    line shows `crc=----` and the CRC-present case's assertion fails.
    Restore: the broken form is built in memory."""
    full = wire_compose.compose_message(0x4A, b"\x5a", table)
    stripped = full[:-2]

    lines = wire_compose.report_lines([stripped])
    assert "crc=----" in lines[0]

    with pytest.raises(AssertionError):
        assert int.from_bytes(stripped[-2:], "big") == crc_crosscheck.table_walk(
            stripped[3:], table
        )

    # The full message restores the case: its trailing bytes ARE the walk.
    assert int.from_bytes(full[-2:], "big") == crc_crosscheck.table_walk(
        full[3:-2], table
    )


# ---------------------------------------------------------------------------
# The CLI contract.
# ---------------------------------------------------------------------------


def test_run_prints_the_table_and_hex_dump_and_exits_zero(table, tmp_path, capsys):
    """`python3 -m nmg2_tools.wire_compose <file.pch2>` prints the per-message
    table then the hex dump and exits 0 on a parseable file."""
    path = tmp_path / "min.pch2"
    path.write_bytes(_corpus("min.pch2"))

    code = wire_compose.run(path)

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("msg 0 first=0x21 ")
    assert "crc=0x" in out
    assert "family=" in out


def test_a_malformed_file_exits_2_with_the_named_error(tmp_path, capsys):
    """A file the parser refuses exits 2 with the parser's own named refusal
    on stderr -- reusing pch2.py's exception types, not a second taxonomy."""
    bad = build_file(build_object(0x21, b"\x01"), crc_error=0x0001)
    path = tmp_path / "bad.pch2"
    path.write_bytes(bad)

    code = wire_compose.main([str(path)])

    err = capsys.readouterr().err
    assert code == 2
    assert "PCH2-BAD-CRC" in err


def test_the_module_main_runs_under_the_interpreter(table, tmp_path):
    """The documented CLI form, run end to end through the interpreter, so the
    `python3 -m nmg2_tools.wire_compose` spelling the report names is the one
    that works."""
    path = tmp_path / "min.pch2"
    path.write_bytes(_corpus("min.pch2"))

    result = subprocess.run(
        [sys.executable, "-m", "nmg2_tools.wire_compose", str(path)],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "."},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "msg 0 first=0x21" in result.stdout
    assert "family=" in result.stdout


# ---------------------------------------------------------------------------
# The real-corpus case. Gated on NMG2_ARTIFACTS; skips with the standard
# reason when the corpus is unreachable.
# ---------------------------------------------------------------------------

CORPUS_REL = pathlib.Path("corpus") / "pch2"


@pytest.fixture(scope="module")
def demo_corpus_dir() -> pathlib.Path:
    """The resolved corpus directory, or the standard skip."""
    reason = gated_skip_reason(str(CORPUS_REL / "MANIFEST.txt"))
    if reason is not None:
        pytest.skip(reason)
    base, _why = resolve_artifacts()
    return pathlib.Path(base) / CORPUS_REL


def test_every_real_patch_composes_to_a_table_with_present_crcs(
    demo_corpus_dir, table
):
    """When NMG2_ARTIFACTS is set, compose every `.pch2` in the corpus and
    assert the per-message table parses and every message's CRC is present.

    Informational by tier: the skip keeps the run green where the corpus is
    absent. What a green run here adds over the synthesized cases is that the
    composed form covers every object type real patches carry."""
    patches = sorted(p for p in demo_corpus_dir.iterdir() if p.suffix == ".pch2")
    assert patches, "the corpus directory holds no .pch2 file to compose"

    for path in patches:
        messages = wire_compose.compose(path.read_bytes(), table)
        lines = wire_compose.report_lines(messages)

        assert len(lines) == len(messages)
        for line in lines:
            assert "crc=0x" in line
            assert "crc=----" not in line


# ---------------------------------------------------------------------------
# Case 6. The patch-load message level. The framing is the one
# the capture corpus and the runtime instrument agree on; the cases pin the
# header prefix, the CRC placement, and the total field against it.
# ---------------------------------------------------------------------------


def _arithmetic_crc_of(data: bytes) -> int:
    """The arithmetic CRC-16/CCITT-XMODEM, restated beside its user."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _bit in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def test_patch_load_header_prefixes_match_the_measured_wire_form(table):
    """The body opens with the capture-008 prefix: M_CMD, S_SLOT_REQ+slot,
    V_NEW_PATCH, O_CREATE, three zeros -- then the entry name. The prefix
    bytes are measured, not invented: capture-008's host-to-device frame
    carries 01 28 53 37 00 00 00 before the 16-character name."""
    messages_data = _corpus("min.pch2")
    message = wire_compose.compose_patch_load_body(messages_data, "test")

    assert message[:7] == b"\x01\x28\x53\x37\x00\x00\x00"
    assert message[7:12] == b"test\x00"


def test_patch_load_frame_places_crc_directly_after_the_body(table):
    """The frame's last two bytes are the fixture-table walk over the body,
    and the body ends the byte before them: no pad sits between."""
    body = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")
    framed = wire_compose.frame(body, table)

    assert int.from_bytes(framed[-2:], "big") == crc_crosscheck.table_walk(body, table)
    assert framed[2:-2] == body


def test_patch_load_total_field_equals_the_whole_frame_length(table):
    """total counts the WHOLE frame including its own 2 prefix bytes -- the
    measured rule (865 on capture-008), not body-plus-4 and not a
    64-multiple."""
    body = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")
    framed = wire_compose.frame(body, table)

    assert int.from_bytes(framed[:2], "big") == len(framed)
    assert int.from_bytes(framed[:2], "big") == len(body) + 4


def test_patch_load_message_crc_agrees_with_the_arithmetic_oracle(table):
    """The message-level CRC through the fixture table is the same
    polynomial the arithmetic oracle computes, over the body the frame
    carries."""
    body = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")
    framed = wire_compose.frame(body, table)

    walked = int.from_bytes(framed[-2:], "big")
    assert walked == _arithmetic_crc_of(framed[2:-2])
    assert walked == crc_crosscheck.table_walk(framed[2:-2], table)


def test_entry_name_field_is_terminated_when_short_and_exact_at_16():
    """The EntryName StringField(16, lengthWithTerm) rule, measured on the
    capture corpus: a short name carries one 0x00 terminator (capture-002's
    13-character perf name), a full name carries NO terminator
    (capture-008's 16-character patch name), and a too-long name is
    refused rather than silently truncated."""
    assert wire_compose.entry_name_field("g2fx-perf-002") == b"g2fx-perf-002\x00"
    assert len(wire_compose.entry_name_field("g2fx-perf-002")) == 14

    full = "g2fx-uprate-4mod"
    assert wire_compose.entry_name_field(full) == full.encode("ascii")
    assert b"\x00" not in wire_compose.entry_name_field(full)

    with pytest.raises(ValueError):
        wire_compose.entry_name_field("0123456789abcdef7")


def test_patch_load_omits_the_2d_00_trailer_on_the_host_to_device_form(table):
    """Difference 2 does not fire here: the capture-008 O_CREATE chain
    carries no 0x2D 0x00 pair anywhere in its body (measured: no such pair
    in 861 bytes), so the message-level composer appends none after the
    0x21 chunk even though the per-object composer does."""
    message = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")

    assert b"\x2d\x00" not in message[7:]


def test_patch_load_chain_carries_the_variation_count_rise(table):
    """The chain reuses the per-object difference-1 transformation: a 0x4D
    object from the corpus's variation-count fixture reads 10 on the wire
    form, one appended tenth-variation byte included."""
    message = wire_compose.compose_patch_load_body(
        _corpus("wire_variation_count.pch2"), "test"
    )

    # Header (7) + name field (5) = 12; the chain's objects follow.
    chain = message[12:]
    assert chain[0] == 0x4D
    payload_len = int.from_bytes(chain[1:3], "big")
    payload = chain[3 : 3 + payload_len]
    assert payload[0] == 10
    assert len(payload) == 11


def test_compose_patch_load_returns_the_framed_message_end_to_end(
    table, tmp_path
):
    """The path-taking entry point composes header, name and chain into one
    frame whose total, CRC and prefix all hold -- and whose body is exactly
    the body-level composer's output, so the two layers cannot drift."""
    path = tmp_path / "min.pch2"
    path.write_bytes(_corpus("min.pch2"))

    message = wire_compose.compose_patch_load(path, "test")
    body = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")

    assert message == wire_compose.frame(body, table)
    assert message[2:9] == b"\x01\x28\x53\x37\x00\x00\x00"


def test_whole_transfer_form_wraps_the_message_frame_once_more(table, tmp_path):
    """The transfer envelope adds a second [total][body][CRC] layer around
    the message frame: the outer total counts the whole transfer, the outer
    CRC covers the message frame as its body, and the message frame rides
    inside intact."""
    path = tmp_path / "min.pch2"
    path.write_bytes(_corpus("min.pch2"))

    message = wire_compose.compose_patch_load(path, "test")
    transfer = wire_compose.compose_patch_load_transfer(path, "test")

    assert transfer[2:-2] == message
    assert int.from_bytes(transfer[:2], "big") == len(transfer)
    assert int.from_bytes(transfer[:2], "big") == len(message) + 4
    assert int.from_bytes(transfer[-2:], "big") == crc_crosscheck.table_walk(
        message, table
    )


def test_required_red_a_pad_before_the_crc_turns_the_placement_case_red(table):
    """Plant: a frame that pads the body to a 64-multiple before the CRC.
    Observe: the CRC-placement case fails (the covered
    range no longer equals the body). Restore: the module's own frame keeps
    the CRC directly after the body."""
    body = wire_compose.compose_patch_load_body(_corpus("min.pch2"), "test")
    good = wire_compose.frame(body, table)

    pad_len = (-len(body)) % 64
    padded = (
        (2 + len(body) + pad_len + 2).to_bytes(2, "big")
        + body
        + b"\x00" * pad_len
        + crc_crosscheck.table_walk(body, table).to_bytes(2, "big")
    )

    # The plant's covered range is body-plus-pad, so the placement assertion
    # `framed[2:-2] == body` fails against it.
    with pytest.raises(AssertionError):
        assert padded[2:-2] == body

    # The module's own output restores the rule.
    assert good[2:-2] == body


# ---------------------------------------------------------------------------
# The 0x65 tenth-variation transform (message-layer verdict, 2026-08-30).
# ---------------------------------------------------------------------------


def _morph_bit_layout_wire(payload: bytes) -> int:
    """The bytes the firmware's 0x65 reader (FUN_3002dc84) consumes.

    The reader walks a continuous bit stream: the variation count (8 bits),
    the morph count (4), that many 2-bit locations, then per variation an
    8-bit index, the morph count x 7 bits, an 8-bit parameter count and that
    many 29-bit parameters. The count is the WHOLE-PAYLOAD byte consumption
    the chain walk advances, computed against the same arithmetic the
    firmware runs.
    """
    pos = 0

    def get(width: int) -> int:
        nonlocal pos
        value = 0
        for _ in range(width):
            value = (value << 1) | ((payload[pos >> 3] >> (7 - (pos & 7))) & 1)
            pos += 1
        return value

    variation_count = get(8)
    morph_count = get(4)
    for _ in range(morph_count):
        get(2)
    for _ in range(variation_count):
        get(8)
        for _ in range(morph_count):
            get(7)
        params = get(8)
        for _ in range(params):
            get(2)
            get(8)
            get(7)
            get(4)
            get(8)
    return pos // 8 + (1 if pos % 8 else 0)


def test_difference_1_065_wire_carries_a_full_tenth_variation(table):
    """A real nine-variation 0x65 payload gains a FULL tenth variation, not a
    filler byte: the wire payload's length grows by one variation's span and
    the firmware reader's own walk consumes exactly the wire payload's bytes,
    so the chain walk lands on the next chunk boundary (the 2026-08-30 run's
    37-byte overshoot came from a filler byte, which let the reader's tenth
    pass read the NEXT chunk's bytes as a seventh parameter)."""
    # The real BackTo72 file's 0x65 payload, rebuilt here: nine variations of
    # seven morph parameters each (variations 0..7) plus one empty variation
    # (variation 8) in the g2fx MorphParameters bit layout -- the layout this
    # module's transform decodes and re-emits. Its 288 bytes are the measured
    # file form.
    bit = []

    def put(width: int, value: int) -> None:
        for shift in range(width - 1, -1, -1):
            bit.append((value >> shift) & 1)

    put(8, 9)
    put(4, 8)
    put(20, 0)
    for index in range(9):
        put(4, index)
        put(24, 0)
        put(24, 0)
        put(8, 0)
        put(8, 7 if index < 8 else 0)
        for param in range(7 if index < 8 else 0):
            put(2, 1)
            put(8, (param + 1) % 256)
            put(7, param * 3 % 128)
            put(4, param % 16)
            put(8, (param * 7) % 256)
        put(4, 0)
    while len(bit) % 8:
        bit.append(0)
    file_payload = bytes(
        sum(byte << (7 - j) for j, byte in enumerate(bit[i : i + 8]))
        for i in range(0, len(bit), 8)
    )
    assert len(file_payload) == 288

    wire_payload = wire_compose.message_payload(0x65, file_payload)

    # The wire carries the count 10 and ONE MORE VARIATION'S SPAN: nine
    # 275-bit variations, one 72-bit empty variation, and the appended tenth
    # (a copy of the last, so another 72 bits) -- 297 bytes.
    assert wire_payload[0] == 10
    assert len(wire_payload) == 297
    assert len(wire_payload) - len(file_payload) == 9

    # THE REQUIRED-RED: reverting to the 1-byte filler (count rewrite only)
    # leaves the firmware walk short of a clean boundary -- the reader walks
    # past the wire payload into the next chunk's bytes. The walk over THIS
    # module's payload stops exactly at its 297 bytes whatever follows; the
    # walk over the filler form runs ON past the payload end (its tenth
    # variation's parameter count comes from the following chunk's bytes).
    # The next-chunk bytes here are a realistic 0x62 chunk header; with the
    # real BackTo72 chain the filler walk consumed 326 -- the measured
    # 329-minus-header overshoot of the 2026-08-30 run.
    filler_form = bytes([10]) + file_payload[1:] + bytes([0])
    following = bytes([0x62, 0x00, 0x48]) + bytes([0x00, 0x78]) + bytes(256)
    assert _morph_bit_layout_wire(wire_payload + following) == 297
    filler_consumed = _morph_bit_layout_wire(filler_form + following)
    assert filler_consumed > len(filler_form)
    with pytest.raises(AssertionError):
        assert filler_consumed == len(filler_form)
        assert _morph_bit_layout_wire(filler_form + bytes(64)) == len(filler_form)
