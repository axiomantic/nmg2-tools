"""The container checksum.

The loader adds all bytes of a block into a 32-bit accumulator and stores the
one's complement of that accumulator:

    cksum = (~sum(data)) & 0xFFFFFFFF

The container holds two such values for each section, one over the compressed
bytes and one over the plain bytes. The loader verifies both.

The value is a sum, so it does not depend on the order of the bytes. It detects
a changed byte. It does not detect a permutation of the same bytes.

WHAT THIS FILE IS, because the licence makes it matter.

`nmg2-tools` is MIT. The source of the algorithm above is INTERNAL: this
project's own specification states the sum and the one's complement in its own
words. That specification is not a third-party implementation, and no
implementation of this checksum by anyone else was consulted. No line of any other implementation is copied, transliterated or
paraphrased here, because none was read.

**This record is NOT a clean-room account and does not claim to be one.** A
clean-room account describes a derivation made against a reference held at
arm's length; here there is no reference. What the loader computes is a FACT
about a data format, and the code below is this project's own expression of
that fact.
"""

from __future__ import annotations

MASK32 = 0xFFFFFFFF


def checksum(data: bytes | bytearray | memoryview) -> int:
    """Return the 32-bit container checksum of ``data``.

    The result is always in the range 0 to 0xFFFFFFFF.
    """
    return (~sum(memoryview(data).cast("B"))) & MASK32
