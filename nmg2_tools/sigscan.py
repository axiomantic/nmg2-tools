"""The descriptor signature scanner. Task TOOL-6, design 7.13, logbook ``AGENTS.md`` 3.1.

WHAT A MODULE DESCRIPTOR IS.

The G2 firmware carries DSP module descriptors, each naming three blobs of
DSP data: an X workspace, a Y workspace and a P program. ``AGENTS.md`` section
3.1 fixes the record layout, read as 32-bit big-endian longwords over a base
``B`` (the pointer-triple address minus 8):

    +0x08  pointer to X data      (0 means "no X blob")
    +0x0C  pointer to Y data      (0 means "no Y blob")
    +0x10  pointer to P program
    +0x14  0xFF000000 terminator
    +0x1C  X word count
    +0x20  Y word count
    +0x24  P word count

``+0x18`` is still unidentified and this module never reads it.

WHY A SIGNATURE SCAN AND NOT A FIXED STRIDE.

The descriptor table does not use a uniform stride. ``0x28`` is only the MODAL
stride; large gaps where blob data is interleaved break the table, and a
fixed-stride walk desynchronizes
(``(0x30108094 - 0x300ED56C) / 0x28 = 2733.8``, not an integer). The reliable
recovery is a *signature scan*: walk the image at 2-byte granularity and accept
a record where the terminator ``0xFF000000`` sits at ``+0x14`` **together with**
an in-range P pointer at ``+0x10``.

WHY 2-BYTE GRANULARITY (logbook trap 7.2).

Many blobs are stored at 2 mod 4. A sweep that tests only 4-byte alignment sees
that noise and misses those records. 16-bit alignment is legal for a 68k
``move.l``, so the scan must test every even offset.

WHY THE P POINTER IS THE RANGE TEST.

The terminator alone is not enough and an in-range P pointer alone is not
enough; it is the conjunction that separates a real record from a data-mine
false positive. ``0xFF000000`` appears in ordinary data and a plausible pointer
appears in ordinary data, but the two at the fixed internal offset, at a
2-byte step, with the pointer in the image's address range, mark a genuine
descriptor.

THE VALIDATION IDENTITY.

``X_ptr + 4*(X_words + Y_words) == P_ptr`` holds for every record that carries
an X pointer, with zero exceptions. This confirms the field meanings and that
blobs are stored 4 bytes per 24-bit word. Records with no X blob have
``x_ptr = 0`` and ``x_words = 0`` together -- a correctly encoded absence.

No byte of any Clavia image is embedded here. The scanner is a pure function
of the image bytes and the image's load address.

WHAT THIS FILE IS, because the licence makes it matter.

`nmg2-tools` is MIT. The source of the record layout above is INTERNAL: the
logbook, ``AGENTS.md`` section 3.1, is this project's own note of which field
sits at which offset, and design section 7.13 is this project's own
specification of the scan. Neither is a third-party implementation, and no
scanner written by anyone else was consulted. No line of any other
implementation is copied, transliterated or paraphrased here, because none was
read.

**This record is NOT a clean-room account and does not claim to be one.** A
clean-room account describes a derivation made against a reference held at
arm's length; here there is no reference. The offsets are FACTS about a data
format, and the search strategy below is this project's own expression of how
to find them.
"""

import struct
from dataclasses import dataclass

TERMINATOR = 0xFF000000

# The greatest byte offset a record reads is +0x24 (p_words), a 4-byte read, so
# a complete record occupies 0x28 bytes. ``0x28`` is a SIZE ceiling here, never
# a stride: the scanner must not and does not skip ahead by it.
RECORD_BYTES = 0x28


@dataclass(frozen=True)
class ModuleDescriptor:
    """One recovered module descriptor record.

    ``record_addr`` is the virtual address of the record base ``B`` (the
    pointer-triple address minus 8). ``x_ptr``, ``y_ptr`` and ``p_ptr`` are the
    three blob pointers read at ``+0x08``, ``+0x0C`` and ``+0x10``; a
    zero ``x_ptr`` means the record carries no X blob. ``x_words``, ``y_words``
    and ``p_words`` are the word counts at ``+0x1C``, ``+0x20`` and ``+0x24``.
    """

    record_addr: int
    x_ptr: int
    y_ptr: int
    p_ptr: int
    x_words: int
    y_words: int
    p_words: int

    @property
    def carries_x(self) -> bool:
        """True when the record carries an X blob (``x_ptr`` and ``x_words``
        are jointly non-zero)."""
        return self.x_ptr != 0 and self.x_words != 0


def _u32(image: bytes, offset: int) -> int:
    return struct.unpack(">I", image[offset : offset + 4])[0]


def scan(image: bytes, base: int) -> list[ModuleDescriptor]:
    """Recover every module descriptor record from ``image``.

    ``image`` is the firmware image, blobs packed 4 bytes per 24-bit word.
    ``base`` is the virtual address of ``image[0]``; the P-pointer range test
    needs it so an in-range pointer means "inside the image's address span".

    The walk steps 2 bytes at a time (``range(0, len-RECORD_BYTES+1, 2)``). A
    record is accepted iff the terminator reads ``0xFF000000`` at ``+0x14`` and
    the P pointer at ``+0x10`` lies in ``[base, base + len(image))``. No fixed
    stride is ever used; every even offset is a candidate.

    Returns the records in ascending address order.
    """
    end = base + len(image)
    records: list[ModuleDescriptor] = []
    last = len(image) - RECORD_BYTES + 1
    for offset in range(0, last, 2):
        terminator = _u32(image, offset + 0x14)
        if terminator != TERMINATOR:
            continue
        p_ptr = _u32(image, offset + 0x10)
        if not (base <= p_ptr < end):
            continue
        records.append(
            ModuleDescriptor(
                record_addr=base + offset,
                x_ptr=_u32(image, offset + 0x08),
                y_ptr=_u32(image, offset + 0x0C),
                p_ptr=p_ptr,
                x_words=_u32(image, offset + 0x1C),
                y_words=_u32(image, offset + 0x20),
                p_words=_u32(image, offset + 0x24),
            )
        )
    return records
