"""The firmware-CRC cross-check.

The firmware's USB message worker validates every reassembled protocol
message through a table-driven CRC whose update step is the decompiled one
at ``0x300089DC``:

    crc = table[byte ^ (crc >> 8)] ^ (crc << 8)

These tests hold the committed fixture table (``crc_table_firmware.bin``)
against that step and against the arithmetic CRC ``nmg2_tools`` uses, so
that a checksum-mismatch hypothesis between emulator and firmware dies here
or is named. WHAT A GREEN RUN DOES NOT PROVE: that the emulator composes
the byte sequences the firmware checksums.

WHY THE TABLE IS THE FIRMWARE'S AND NOT THE ORACLE'S. The table address
``0x3012C080`` lies above the loaded image; the firmware's own builder at
``0x300088D4`` fills the table at boot and self-checks it by folding
``"1234"`` to ``0xD789`` — a check value this suite asserts independently
in ``test_the_boot_self_check_vector_folds_to_the_disassembled_literal``.
The fixture records that table's bytes once, and every case below reads the
COMMITTED bytes, so a change to the derivation cannot make the tests agree
with themselves.

Each comparison below has a required-red case beside it: a deliberately broken
table is run through the SAME case function the green cases run, so the red is
a property of the case and not of a separate weaker assertion.
"""

import hashlib
import os
import pathlib

import pytest

from nmg2_tools import crc_crosscheck, pch2
from nmg2_tools.artifacts import (
    gated_skip_reason,
    resolve_artifacts,
)
from nmg2_tools.checksum import checksum
from nmg2_tools.synth_pch2 import crc16_ccitt

FIXTURE_NAME = "crc_table_firmware.bin"

# The digest of the committed fixture, stated in full. This is the one
# hand-written Clavia-independent constant the module may carry: it is what
# makes a hand-edited or stale fixture fail instead of passing.
FIXTURE_SHA256 = "e4537e4ac69bf8c22ae98bcbf35a76cae77c7c025d6222c4e4390ec962c10881"

# The firmware's own boot-time self check folds these bytes against this
# literal, disassembled at ``0x30009560`` (``cmpil #55177``). Asserted here
# as the cross-check of the cross-check: the table whose bytes the fixture
# carries is the table the firmware's builder verifies.
BOOT_CHECK_INPUT = b"1234"
BOOT_CHECK_VALUE = 0xD789


@pytest.fixture(scope="module")
def fixture_table() -> tuple[int, ...]:
    """The committed fixture, read once, as 256 big-endian entries."""
    with open(crc_crosscheck.fixture_path(), "rb") as handle:
        return crc_crosscheck.table_from_bytes(handle.read())


# ---------------------------------------------------------------------------
# The fixture itself.
# ---------------------------------------------------------------------------

def test_the_committed_fixture_matches_the_recorded_digest():
    """The fixture's whole bytes hash to the recorded literal.

    This is the integrity case: a fixture that is truncated, padded,
    hand-edited or regenerated from a changed derivation fails here with a
    digest that names the difference, and no other case can pass a fixture
    this one refuses."""
    with open(crc_crosscheck.fixture_path(), "rb") as handle:
        data = handle.read()

    assert len(data) == 512
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256


def test_the_boot_self_check_vector_folds_to_the_disassembled_literal():
    """The arithmetic CRC folds ``"1234"`` to the boot builder's own check
    value ``0xD789``, disassembled at ``0x30009560``.

    This binds the fixture's derivation to the firmware's own verification
    rather than to this project's say-so: a polynomial, an endianness or a
    fold direction the firmware does not use produces a table whose builder
    would have failed its own boot check."""
    assert crc16_ccitt(BOOT_CHECK_INPUT) == BOOT_CHECK_VALUE


# ---------------------------------------------------------------------------
# Case (a): every table entry against the arithmetic form.
# ---------------------------------------------------------------------------

def test_every_table_entry_equals_the_arithmetic_form(fixture_table):
    """For all ``(byte, crc_high_byte)`` pairs the decompiled update step
    requires ``table[i] == poly_fold(i)``: with crc high byte ``h``, the
    step's index is ``i ^ h``, so the pair holds for every ``h`` exactly
    when the entry equals the fold of the bare byte. The comparison runs
    over the whole table and reports every disagreement with its offset."""
    mismatches = crc_crosscheck.compare_pairs(fixture_table)

    assert mismatches == [], (
        "table entries disagreeing with the arithmetic form "
        f"(index, table, arithmetic): {mismatches}"
    )


def test_the_derived_form_agrees_with_the_oracle_crc16_over_one_byte():
    """Over a single byte from init 0 the decompiled step reduces to
    ``table[byte]``, so the table form and the oracle must give the same
    answer for every byte value — the one-byte reduction of case (b)."""
    table = crc_crosscheck.table_from_bytes(crc_crosscheck.derive_table_bytes())

    for byte in range(256):
        walked = crc_crosscheck.table_walk(bytes([byte]), table)
        assert walked == crc16_ccitt(bytes([byte])), byte


# ---------------------------------------------------------------------------
# Case (b): the corpus, checksummed by both forms.
# ---------------------------------------------------------------------------

def _corpus_inputs() -> list[tuple[str, bytes]]:
    """The fixed corpus the two forms must agree on.

    The synthetic cases run everywhere. The largest-object case is gated:
    its input is the largest single object payload in the real demo corpus,
    derived at run time from the corpus itself and never written down here.
    """
    inputs: list[tuple[str, bytes]] = [
        ("empty", b""),
        ("one byte 0xA5", b"\xA5"),
        ("64-byte pattern", bytes((i * 7 + 0x31) & 0xFF for i in range(64))),
    ]
    return inputs


def _largest_corpus_payload(corpus: pathlib.Path) -> tuple[str, bytes]:
    """The largest object payload in the corpus, with the file that holds it.

    The parse is framing only: object payloads stay opaque bytes."""
    best_name, best_payload = "", b""
    for path in sorted(corpus.glob("*.pch2")):
        for obj in pch2.parse(path.read_bytes()).objects:
            if len(obj.payload) > len(best_payload):
                best_name, best_payload = path.name, obj.payload
    if not best_payload:
        pytest.fail("the corpus holds no object payload to checksum")
    return f"largest payload ({best_name})", best_payload


@pytest.fixture(scope="module")
def corpus_inputs() -> list[tuple[str, bytes]]:
    """The synthetic inputs, which need no Clavia byte.

    They are NOT behind the artifact gate. A fixture that skips before
    returning them takes every case that asks for them dark on a runner with
    no artifacts, which is every runner this repository's CI has."""
    return _corpus_inputs()


@pytest.fixture(scope="module")
def gated_corpus_inputs() -> list[tuple[str, bytes]]:
    """The synthetic inputs plus the largest real corpus payload. The skip is
    the standard one: an artifact-gated input that cannot be reached skips
    WITH A REASON and never fails for that reason."""
    reason = gated_skip_reason()
    if reason is not None:
        pytest.skip(reason)
    base, _why = resolve_artifacts()
    corpus = pathlib.Path(base) / "corpus" / "pch2"
    if not corpus.is_dir():
        # A root that resolves but does not hold the corpus is a second,
        # distinct skip reason, as in tests/test_pch2_real_corpus.py: the
        # informational half stays green on machines without the private
        # corpus rather than failing.
        pytest.skip(
            "SKIPPED: the demo patch corpus is not present under "
            "NMG2_ARTIFACTS (corpus/pch2 missing)"
        )
    return _corpus_inputs() + [_largest_corpus_payload(corpus)]


def test_the_oracle_and_the_table_form_agree_on_the_whole_corpus(
    fixture_table, corpus_inputs
):
    """Every corpus input checksums to the same value through the oracle's
    arithmetic CRC and through the fixture table with the decompiled update
    step. Each case names its input, so a disagreement says which byte
    sequence broke, not merely that one did."""
    for label, data in corpus_inputs:
        arithmetic = crc16_ccitt(data)
        walked = crc_crosscheck.table_walk(data, fixture_table)
        assert walked == arithmetic, f"the two forms disagree on {label}"


def test_the_table_walk_is_the_crc_and_not_the_container_sum(
    fixture_table, corpus_inputs
):
    """:mod:`nmg2_tools.checksum` is the additive container sum, not the CRC.
    Each input is walked through the fixture table and held against BOTH: it
    must equal the CRC oracle and differ from the container sum. Asserting
    only that the two oracles differ measures neither the table nor the walk,
    and stays green while the walk returns any constant at all."""
    for label, data in corpus_inputs:
        walked = crc_crosscheck.table_walk(data, fixture_table)
        assert walked == crc16_ccitt(data), f"the walk is not the CRC on {label}"
        assert walked != checksum(data), (
            f"the walk computed the container sum on {label}"
        )


def test_the_gated_corpus_payload_agrees_through_both_forms(
    fixture_table, gated_corpus_inputs
):
    """The same agreement over the largest object payload the real demo
    corpus holds, which no synthetic input can stand in for."""
    for label, data in gated_corpus_inputs:
        walked = crc_crosscheck.table_walk(data, fixture_table)
        assert walked == crc16_ccitt(data), f"the two forms disagree on {label}"


# ---------------------------------------------------------------------------
# The required-red proofs. Each builds its own broken table from the fixture
# and runs the SAME case function the green cases run, so the red is a
# property of the case, not of a separate weaker assertion.
# ---------------------------------------------------------------------------

def _assert_pair_case_fails(table: tuple[int, ...], broken: tuple[int, ...],
                            expected_offsets: set[int]) -> None:
    """Run the pair comparison against a broken table and require that it
    fails, naming exactly the given offsets."""
    mismatches = crc_crosscheck.compare_pairs(broken)
    assert mismatches, "the broken table produced no mismatch: the case cannot go red"
    assert {m[0] for m in mismatches} == expected_offsets, mismatches


def test_the_pair_case_fails_naming_the_offset(fixture_table):
    """REQUIRED-RED: one perturbed entry turns the pair case red naming
    that entry's offset and no other."""
    broken = list(fixture_table)
    broken[0x7A] ^= 0x0001

    _assert_pair_case_fails(fixture_table, tuple(broken), {0x7A})


def test_an_all_zero_table_fails_both_comparisons():
    """REQUIRED-RED (the known-negative guard): a table of all zeros — the
    signature of a corrupt or empty extraction — fails the pair case AND
    the corpus case, with the failures named rather than summarized."""
    broken = tuple([0] * 256)

    pair = crc_crosscheck.compare_pairs(broken)
    assert len(pair) == 255, "entry 0 legitimately folds to 0; the other 255 must mismatch"
    assert {m[0] for m in pair} == set(range(1, 256))

    data = b"\xA5"
    walked = crc_crosscheck.table_walk(data, broken)
    arithmetic = crc16_ccitt(data)
    assert walked != arithmetic, (
        "an all-zero table checksummed the corpus the same as the oracle; "
        "a corrupt extraction cannot read as a pass"
    )


def test_two_swapped_entries_turn_the_pair_case_red_at_both_offsets(fixture_table):
    """REQUIRED-RED: swapping two adjacent entries fails the pair case at
    both offsets and at no others."""
    broken = list(fixture_table)
    broken[0x10], broken[0x11] = broken[0x11], broken[0x10]

    _assert_pair_case_fails(fixture_table, tuple(broken), {0x10, 0x11})


def test_a_reversed_corpus_walk_fails(fixture_table, corpus_inputs):
    """REQUIRED-RED: walking the corpus with the bytes reversed — the
    order-sensitivity the additive container sum lacks and the CRC has —
    turns the corpus case red on the inputs where reversal changes the
    bytes. The empty input has no order and is excluded by construction."""
    for label, data in corpus_inputs:
        if len(data) < 2 or data == data[::-1]:
            continue
        reversed_walk = crc_crosscheck.table_walk(data[::-1], fixture_table)
        arithmetic = crc16_ccitt(data)
        assert reversed_walk != arithmetic, (
            f"a reversed walk of {label} passed; the corpus case cannot "
            "detect a byte-order defect"
        )


# ---------------------------------------------------------------------------
# The extraction claim, kept honest.
# ---------------------------------------------------------------------------

@pytest.mark.artifacts("CODE_30000400.bin")
def test_the_image_extraction_reports_its_named_error(artifacts_dir):
    """``--extract``'s read of the table VMA fails with a NAMED error
    against the real image, because the region lies past EOF. A silent
    empty read, or an exception with no message, would leave the
    extraction path unverified in the direction it actually behaves."""
    path = os.path.join(artifacts_dir, "CODE_30000400.bin")
    with pytest.raises(ValueError) as excinfo:
        crc_crosscheck.extract_table_bytes(path)

    assert "CRCCROSSCHECK-EXTRACT-PAST-EOF" in str(excinfo.value)
    assert hex(crc_crosscheck.TABLE_VMA - crc_crosscheck.IMAGE_BASE) in str(excinfo.value)
