"""The container checksum. Task TOOL-2, design section 7.3 step 4.

The loader adds all bytes of a block into a 32-bit accumulator and stores the
one's complement of that accumulator:

    cksum = (~sum(data)) & 0xFFFFFFFF

The container holds two such values for each section, one over the compressed
bytes and one over the plain bytes. Design section 7.3 step 3 verifies both.

The value is a sum, so it does not depend on the order of the bytes. It detects
a changed byte. It does not detect a permutation of the same bytes.
"""

from __future__ import annotations

MASK32 = 0xFFFFFFFF


def checksum(data: bytes | bytearray | memoryview) -> int:
    """Return the 32-bit container checksum of ``data``.

    The result is always in the range 0 to 0xFFFFFFFF.
    """
    return (~sum(memoryview(data).cast("B"))) & MASK32
