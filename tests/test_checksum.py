"""Task TOOL-2. Design section 7.3 step 4.

The checksum is the one's complement of the 32-bit sum of all bytes. Every
assertion below states the full expected 32-bit value, because a checksum that
is off by a constant, or that is not complemented, or that is not truncated to
32 bits, still changes when a byte changes and would survive a
difference-only test.
"""

from nmg2_tools.checksum import checksum


def test_no_bytes_sum_to_zero_and_the_complement_is_all_ones():
    assert checksum(b"") == 0xFFFFFFFF


def test_a_zero_byte_gives_the_same_value_as_no_bytes():
    """The sum, not the length, drives the result."""
    assert checksum(b"\x00") == 0xFFFFFFFF
    assert checksum(b"\x00" * 64) == 0xFFFFFFFF


def test_one_byte_of_one_is_the_complement_of_one():
    assert checksum(b"\x01") == 0xFFFFFFFE


def test_four_maximum_bytes_sum_to_1020():
    # 4 * 255 = 1020 = 0x3FC. ~0x3FC & 0xFFFFFFFF = 0xFFFFFC03.
    assert checksum(b"\xff\xff\xff\xff") == 0xFFFFFC03


def test_ascii_vector_sums_every_byte_and_not_only_some():
    # 'A' + 'B' + 'C' = 65 + 66 + 67 = 198 = 0xC6. ~0xC6 & 0xFFFFFFFF.
    assert checksum(b"ABC") == 0xFFFFFF39


def test_the_section_tag_of_a_container_entry():
    # 'C' + 'O' + 'D' + 'E' = 67 + 79 + 68 + 69 = 283 = 0x11B.
    assert checksum(b"CODE") == 0xFFFFFEE4


def test_a_bytearray_and_a_memoryview_give_the_same_value_as_bytes():
    """The reader hands the container a slice, not always a `bytes`."""
    assert checksum(bytearray(b"ABC")) == 0xFFFFFF39
    assert checksum(memoryview(b"ABC")) == 0xFFFFFF39


def test_a_single_flipped_byte_changes_the_result():
    """Design section 7.3 step 3 verifies a section with this value, so a
    changed byte must change it. Both values are stated in full."""
    good = b"CODE\x10\x20\x30\x40"
    # 67+79+68+69+16+32+48+64 = 443 = 0x1BB.
    assert checksum(good) == 0xFFFFFE44

    flipped = b"CODE\x11\x20\x30\x40"  # 0x10 -> 0x11, one bit
    # The sum rises by exactly 1, so the complement falls by exactly 1.
    assert checksum(flipped) == 0xFFFFFE43
    assert checksum(good) != checksum(flipped)


def test_the_sum_is_truncated_to_32_bits_before_the_complement():
    """16,843,010 bytes of 0xFF sum to 4,294,967,550, which is 2**32 + 254.
    An implementation that keeps the full-width Python integer and only
    complements at the end still returns 0xFFFFFF01 here, but one that returns
    a negative number, or a value wider than 32 bits, does not."""
    total = 0xFF * 16843010
    assert total == 4294967550
    assert total > 0xFFFFFFFF

    result = checksum(b"\xff" * 16843010)

    assert result == 0xFFFFFF01
    assert 0 <= result <= 0xFFFFFFFF


def test_every_result_fits_in_32_unsigned_bits():
    for data in (b"", b"\x00", b"\xff" * 1000, b"CODE", bytes(range(256))):
        result = checksum(data)
        assert 0 <= result <= 0xFFFFFFFF, data
