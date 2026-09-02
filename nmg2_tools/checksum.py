"""The container checksum.

The loader adds all bytes of a block into a 32-bit accumulator and stores the
one's complement of that accumulator:

    cksum = (~sum(data)) & 0xFFFFFFFF

The container holds two such values for each section, one over the compressed
bytes and one over the plain bytes.

The value is a sum, so it does not depend on the order of the bytes. It detects
a changed byte. It does not detect a permutation of the same bytes.
"""

from __future__ import annotations

MASK32 = 0xFFFFFFFF


def checksum(data: bytes | bytearray | memoryview) -> int:
    """Return the 32-bit container checksum of ``data``."""
    return (~sum(memoryview(data).cast("B"))) & MASK32
