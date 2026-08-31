"""The LZO1X decompressor.

WHERE THE VECTORS COME FROM, and why that matters.

Every compressed byte string below was produced by, or confirmed against, the
reference LZO implementation `liblzo2` 2.10 driven through `python-lzo` 1.15.
That run happened OUTSIDE this repository, in a throwaway environment. The
byte strings are opaque test data.

The point of using the reference implementation is that the expected outputs
are NOT this project's own reading of the format. A decoder tested only
against streams that the same author hand-encoded proves that the author is
self-consistent, not that the author is right.

WHAT THESE VECTORS DO NOT COVER: no Clavia byte appears here. The G2 firmware
lives in the PRIVATE `axiomantic/nmg2-artifacts` repository and must never
enter a public tree in any form. A green run therefore proves that this
decompressor agrees with `liblzo2` on synthetic input. It does not prove that
the G2 loader's m68k port agrees with `liblzo2` on the shipped OS image; the
updater-extraction tests read the real firmware and are gated on the
artifacts.
"""

import pytest

from nmg2_tools.lzo1x import Lzo1xError, decompress

END_MARKER = bytes.fromhex("110000")


def pseudo_random(n: int) -> bytes:
    """A deterministic, poorly compressible byte sequence.

    A linear congruential generator, written out rather than taken from
    `random`, so that the sequence cannot move when a Python release changes
    the standard generator and silently invalidate every vector below.
    """
    state = 0x12345678
    out = bytearray()
    for _ in range(n):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        out.append((state >> 16) & 0xFF)
    return bytes(out)


# --- vectors the reference compressor produced -----------------------------

THREE_LITERALS = bytes.fromhex("14616263110000")

SEVENTEEN_LITERALS = bytes.fromhex(
    "223031323334353637383961626364656667110000"
)

EIGHTEEN_LITERALS = bytes.fromhex(
    "23303132333435363738396162636465666768110000"
)

REPEATED_WORDS = bytes.fromhex("1768656c6c6f2030140002776f726c642a1400110000")

# 273 and 300 literals. The reference compressor emitted exactly
# header + the literal payload + the end marker for both, which was checked
# byte for byte outside this repository, so the payload is spliced in here
# rather than repeated as 600 characters of hexadecimal.
LITERAL_RUN_273 = bytes.fromhex("00ff") + pseudo_random(273) + END_MARKER
LITERAL_RUN_300 = bytes.fromhex("00001b") + pseudo_random(300) + END_MARKER

FIVE_THOUSAND_A = bytes.fromhex(
    "12412000000000000000e600002000000000000000e6000020000000690000110000"
)

COUNTING_BYTES_X4 = bytes.fromhex(
    "00ee000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f4041"
    "42434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60616263"
    "6465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f808182838485"
    "868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9fa0a1a2a3a4a5a6a7"
    "a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebfc0c1c2c3c4c5c6c7c8c9"
    "cacbcccdcecfd0d1d2d3d4d5d6d7d8d9dadbdcdddedfe0e1e2e3e4e5e6e7e8e9eaeb"
    "ecedeeeff0f1f2f3f4f5f6f7f8f9fafbfcfdfeff200000e1fc03110000"
)

FAR_MATCH_20000 = bytes.fromhex(
    "2b4d41524b45522d6661722d64697374616e63652d70726f62650020000000000000"
    "00e600002000000000000000e600002000000000000000e600002000000000000000"
    "e600002000000000000000e600002000000000000000e600002000000000000000e6"
    "00002000000000000000e600002000000000000000e6000020000000000000040000"
    "1010e438110000"
)

FAR_MATCH_40000 = bytes.fromhex(
    "2b4d41524b45522d6661722d64697374616e63652d70726f62650020000000000000"
    "00e600002000000000000000e600002000000000000000e600002000000000000000"
    "e600002000000000000000e600002000000000000000e600002000000000000000e6"
    "00002000000000000000e600002000000000000000e600002000000000000000e600"
    "002000000000000000e600002000000000000000e600002000000000000000e60000"
    "2000000000000000e600002000000000000000e600002000000000000000e6000020"
    "00000000000000e600002000000000000000e600002000000000000000e600002000"
    "00000022000018106471110000"
)

MIXED_TEXT = bytes.fromhex(
    "3154686520717569636b2062726f776e20666f78206a756d7073206f766572207458"
    "03076c617a7920646f672e2020edb000001671471d94ec8993c744bcd8cfcb3cc5a6"
    "6819a8e6caa4e23b69bd418941da1edc4ed83613c682494c2066b802110000"
)

NEAR_MATCH = bytes.fromhex(
    "2f71471d94ec8993c744bcd8cfcb3cc5a66819a8e6caa4e23b69bd418941da2a7400"
    "110000"
)

# --- vectors hand-built here and then run through the reference DECOMPRESSOR,
# --- which is what fixes the expected output. They reach instruction forms
# --- the reference compressor never emits for these inputs.

SHORT_MATCH = bytes.fromhex("124102004243110000")
HEAD_LITERAL_RUN = pseudo_random(3000)
HEAD_SHORT_MATCH = (
    bytes([0x00]) + bytes(11) + bytes([0xB1])
    + HEAD_LITERAL_RUN
    + bytes([0x00, 0x00])
    + END_MARKER
)
TWO_BIT_LENGTH_MATCH = bytes.fromhex("1961626364656667686000110000")
TRAILING_LITERALS = bytes.fromhex("196162636465666768630058595a110000")

# A medium match, opcode 0x24, that carries two trailing literals. The count
# rides in the low two bits of the first distance byte, which the distance
# itself does not use. The reference compressor did not emit this form for any
# input above, so the instruction is built here and the reference DECOMPRESSOR
# fixes the expected output.
MEDIUM_MATCH_TRAILING = bytes.fromhex("1961626364656667682402005051110000")

# The same point for the long-distance form. This is the 20000-byte vector
# with the first distance byte moved from 0xE4 to 0xE5. The distance uses only
# the upper 14 bits of the word, so it does not move; the trailing count goes
# from 0 to 1 and one more literal follows.
FAR_MATCH_TRAILING = (
    FAR_MATCH_20000[:-7] + bytes.fromhex("1010e538") + b"Z" + END_MARKER
)

# An opening literal run of exactly three bytes, then an opcode below 16. A run
# of fewer than four bytes at the head of a stream is a run of TRAILING
# literals, so the opcode is an ordinary short match with a base distance of 1
# and not a head match with a base distance of 2049.
OPENING_RUN_OF_THREE = bytes.fromhex("146162630000") + END_MARKER

# The same shape with a run of four bytes, which crosses the boundary. The
# opcode is then a head match, the distance is 2049, and four written bytes
# cannot satisfy it. The reference implementation rejects this stream.
OPENING_RUN_OF_FOUR = bytes.fromhex("15616263640000") + END_MARKER

# Trailing literals followed by an opcode below 16. The byte after trailing
# literals is always a match instruction, never a literal run.
TRAILING_THEN_SHORT_MATCH = (
    bytes.fromhex("196162636465666768630058595a0000") + END_MARKER
)

FOX = b"The quick brown fox jumps over the lazy dog. "

# name -> (compressed stream, the bytes the reference implementation produces)
VECTORS = {
    "end marker alone": (END_MARKER, b""),
    "three literals": (THREE_LITERALS, b"abc"),
    "seventeen literals": (SEVENTEEN_LITERALS, b"0123456789abcdefg"),
    "eighteen literals": (EIGHTEEN_LITERALS, b"0123456789abcdefgh"),
    "repeated words": (
        REPEATED_WORDS,
        b"hello hello hello hello world world world",
    ),
    "literal run of 273": (LITERAL_RUN_273, pseudo_random(273)),
    "literal run of 300": (LITERAL_RUN_300, pseudo_random(300)),
    "five thousand A": (FIVE_THOUSAND_A, b"A" * 5000),
    "counting bytes four times": (COUNTING_BYTES_X4, bytes(range(256)) * 4),
    "match across 20000 bytes": (
        FAR_MATCH_20000,
        b"MARKER-far-distance-probe"
        + b"\x00" * 20000
        + b"MARKER-far-distance-probe",
    ),
    "match across 40000 bytes": (
        FAR_MATCH_40000,
        b"MARKER-far-distance-probe"
        + b"\x00" * 40000
        + b"MARKER-far-distance-probe",
    ),
    "mixed text": (MIXED_TEXT, FOX * 7 + pseudo_random(40) + FOX * 3),
    "near match": (NEAR_MATCH, pseudo_random(30) + pseudo_random(30)[:12]),
    "short match": (SHORT_MATCH, b"AAABC"),
    "short match at the head": (
        HEAD_SHORT_MATCH,
        HEAD_LITERAL_RUN + HEAD_LITERAL_RUN[3000 - 2049 : 3000 - 2049 + 3],
    ),
    "two bit length match": (TWO_BIT_LENGTH_MATCH, b"abcdefghhhhh"),
    "trailing literals": (TRAILING_LITERALS, b"abcdefghhhhhXYZ"),
    "medium match with trailing literals": (
        MEDIUM_MATCH_TRAILING,
        b"abcdefghhhhhhhPQ",
    ),
    "opening run of three": (OPENING_RUN_OF_THREE, b"abccc"),
    "trailing then short match": (
        TRAILING_THEN_SHORT_MATCH,
        b"abcdefghhhhhXYZZZ",
    ),
    "far match with trailing literals": (
        FAR_MATCH_TRAILING,
        b"MARKER-far-distance-probe"
        + b"\x00" * 20000
        + b"MARKER-far-distance-probe"
        + b"Z",
    ),
}


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_every_vector_reproduces_the_reference_output_exactly(name):
    compressed, expected = VECTORS[name]

    assert decompress(compressed) == expected


def test_the_end_marker_alone_gives_no_bytes():
    """The shortest legal stream. It is three bytes and it decodes to nothing.
    Stated on its own because a decoder that returned `None`, or that raised on
    a zero-length result, would pass a length-only check."""
    assert decompress(END_MARKER) == b""
    assert isinstance(decompress(END_MARKER), bytes)


def test_a_single_literal_run_copies_the_bytes_through_unchanged():
    assert decompress(EIGHTEEN_LITERALS) == b"0123456789abcdefgh"


def test_a_maximum_length_match_expands_five_thousand_bytes_from_thirty_four():
    """The match length runs off the end of the five-bit field and continues
    in a chain of 0xFF bytes. This vector needs six links of that chain."""
    result = decompress(FIVE_THOUSAND_A)

    assert result == b"A" * 5000
    assert len(FIVE_THOUSAND_A) == 34


def test_an_overlapping_match_repeats_a_growing_window():
    """A match whose distance is shorter than its length reads bytes that the
    same match is still writing. A decoder that copies the source slice once,
    instead of one byte at a time, gets this wrong."""
    assert decompress(FIVE_THOUSAND_A)[:10] == b"AAAAAAAAAA"
    assert decompress(TWO_BIT_LENGTH_MATCH) == b"abcdefghhhhh"


def test_a_match_carries_its_trailing_literal_count_in_its_last_bytes():
    """Each of the four match forms holds the count of the literals that
    follow it in the low two bits of its last byte. A decoder that ignores
    those bits reads the literals as an instruction and loses them."""
    # The one-byte-distance form. The count is in the opcode.
    assert decompress(TRAILING_LITERALS) == b"abcdefghhhhhXYZ"
    # The medium form. The count is in the first of the two distance bytes.
    assert decompress(MEDIUM_MATCH_TRAILING) == b"abcdefghhhhhhhPQ"
    # The long-distance form. Same two bits, and the distance does not move.
    assert decompress(FAR_MATCH_TRAILING) == (
        b"MARKER-far-distance-probe"
        + b"\x00" * 20000
        + b"MARKER-far-distance-probe"
        + b"Z"
    )
    assert decompress(FAR_MATCH_TRAILING)[:-1] == decompress(FAR_MATCH_20000)


def test_an_opening_run_of_three_bytes_is_a_run_of_trailing_literals():
    """Four bytes is the boundary. A shorter opening run makes the next opcode
    an ordinary short match, and a run of four or more makes it a head match
    with a base distance of 2049. The two readings of the same opcode give
    different output, and the second one cannot even be satisfied here."""
    assert decompress(OPENING_RUN_OF_THREE) == b"abccc"

    with pytest.raises(Lzo1xError) as caught:
        decompress(OPENING_RUN_OF_FOUR)

    assert str(caught.value) == (
        "LZO-DISTANCE-BEFORE-START: distance 2049 is more than the 4 bytes "
        "written"
    )


def test_the_byte_after_trailing_literals_is_always_a_match():
    """Reading it as a literal run instead loses the match and shifts every
    byte that follows."""
    assert decompress(TRAILING_THEN_SHORT_MATCH) == b"abcdefghhhhhXYZZZ"


# --- named failures --------------------------------------------------------


def test_no_input_at_all_is_a_named_failure():
    """An empty input is not an empty result. The shortest legal stream is the
    three-byte end marker, so nothing at all is a stream that ended early."""
    with pytest.raises(Lzo1xError) as caught:
        decompress(b"")

    assert str(caught.value) == (
        "LZO-MISSING-END-MARKER: input ended at offset 0 with no end marker"
    )


def test_a_stream_that_stops_before_the_end_marker_is_a_named_failure():
    """Three literals decode, then the input stops where an instruction byte
    must be. The three decoded bytes are discarded, not returned."""
    with pytest.raises(Lzo1xError) as caught:
        decompress(bytes.fromhex("14616263"))

    assert str(caught.value) == (
        "LZO-MISSING-END-MARKER: input ended at offset 4 with no end marker"
    )


def test_a_match_that_reaches_before_the_start_is_a_named_failure():
    """`12 41` writes one literal. Instruction `08 04` then asks for a match
    19 bytes behind an output that holds one byte."""
    with pytest.raises(Lzo1xError) as caught:
        decompress(bytes.fromhex("12410804") + END_MARKER)

    assert str(caught.value) == (
        "LZO-DISTANCE-BEFORE-START: distance 19 is more than the 1 bytes written"
    )


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_every_truncation_of_every_vector_is_a_named_failure(name):
    """The rule the task states: a truncated stream is a named failure, never
    a partial result. Every proper prefix of every vector is checked, so a
    decoder that returns what it managed to produce fails here whatever the
    truncation point."""
    compressed, expected = VECTORS[name]

    for cut in range(len(compressed)):
        prefix = compressed[:cut]
        with pytest.raises(Lzo1xError):
            decompress(prefix)


def test_the_named_failure_is_a_value_error_and_carries_a_named_code():
    """Callers stop the load and name the section. They need an
    exception type they can catch and a message they can print."""
    assert issubclass(Lzo1xError, ValueError)

    with pytest.raises(ValueError):
        decompress(b"")

    for bad in (b"", bytes.fromhex("14616263"), bytes.fromhex("11")):
        with pytest.raises(Lzo1xError) as caught:
            decompress(bad)
        assert str(caught.value).startswith("LZO-")


def test_a_truncated_literal_run_never_returns_the_bytes_it_did_read():
    """The literal payload is present and readable; only the count is short.
    A decoder that copies what it has and stops would return `b"abc"` here."""
    with pytest.raises(Lzo1xError) as caught:
        decompress(bytes.fromhex("1d616263"))

    assert str(caught.value) == (
        "LZO-TRUNCATED-INPUT: 12 bytes needed at offset 1, 3 available"
    )


def test_a_truncated_length_chain_is_a_named_failure():
    """The chain of zero extension bytes runs off the end of the input."""
    with pytest.raises(Lzo1xError) as caught:
        decompress(bytes.fromhex("0000000000"))

    assert str(caught.value) == (
        "LZO-TRUNCATED-INPUT: 1 byte needed at offset 5, 0 available"
    )


def test_the_input_may_be_a_bytearray_or_a_memoryview():
    assert decompress(bytearray(THREE_LITERALS)) == b"abc"
    assert decompress(memoryview(THREE_LITERALS)) == b"abc"
