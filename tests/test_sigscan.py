"""The descriptor signature scanner. Task TOOL-6, design 7.13, logbook 3.1,
trap 7.2.

WHAT RUNS WHERE.

The scanner itself is a pure function of image bytes and a load address, and is
exercised here with SYNTHETIC images built in this file, so those tests run
everywhere and need no Clavia byte. The end-to-end claim -- that the scan
recovers every record from the real ``CODE_30000400.bin`` and that the
validation identity holds for every record that carries an X pointer -- does
touch real Clavia bytes and is gated on ``NMG2_ARTIFACTS`` via the
``artifacts_dir`` fixture.

WHY THE NON-GATED HALF MATTERS (plan section 18.7, in this task's own words):
a test that passes when the code is broken is worse than no test. The gated
half cannot run in most environments, so the scanner needs its own, ungated
proof here -- and the properties it proves (2-byte granularity, no fixed
stride, the in-range P-pointer test) are the very traps the task warns about.

THE RECORD LAYOUT (logbook ``AGENTS.md`` section 3.1), read as 32-bit
big-endian longwords over base ``B``:

    +0x08  pointer to X data
    +0x0C  pointer to Y data
    +0x10  pointer to P program
    +0x14  0xFF000000 terminator
    +0x1C  X word count
    +0x20  Y word count
    +0x24  P word count
"""

import struct

import pytest

from nmg2_tools.sigscan import TERMINATOR, ModuleDescriptor, scan

# The CODE section of the G2 OS image loads here (design section 7.3 step 1).
# The scanner needs the load address so "in range" means "inside the image".
BASE = 0x30000400


def _u32(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFFFF)


def _place(image: bytearray, offset: int, x_ptr, y_ptr, p_ptr, x_words, y_words, p_words):
    """Write one descriptor record at ``offset`` (relative to the image)."""
    struct.pack_into(
        ">IIII", image, offset + 0x08, x_ptr, y_ptr, p_ptr, TERMINATOR
    )
    struct.pack_into(
        ">III", image, offset + 0x1C, x_words, y_words, p_words
    )


# ---------------------------------------------------------------------------
# Ungated: the scanner recovers records placed at non-uniform, non-0x28 gaps,
# including records at 2 mod 4. A fixed-stride (0x28) walk and a 4-byte-only
# walk both fail on this image. Logbook 3.1: "0x28 is only the MODAL stride",
# and trap 7.2: many blobs are at 2 mod 4.
# ---------------------------------------------------------------------------

def _synthetic_nonuniform():
    image = bytearray(0x300)
    # Three records at deliberately non-modal, non-uniform gaps. Two of the
    # three bases are at 2 mod 4.
    #   A at 0x10 (0 mod 4)
    #   B at 0x10 + 0x30 = 0x40 (gap 0x30)
    #   C at 0x40 + 0x2A = 0x6A (gap 0x2A, base 2 mod 4)
    pA = BASE + 0x200
    _place(image, 0x10, pA - 4 * (2 + 1), pA - 4, pA, 2, 1, 9)
    pB = BASE + 0x240
    _place(image, 0x40, pB - 4 * (3 + 2), pB - 12, pB, 3, 2, 28)
    pC = BASE + 0x280
    _place(image, 0x6A, pC - 4 * (1 + 1), pC - 4, pC, 1, 1, 7)
    return bytes(image)


def test_scan_reports_records_in_address_order():
    recs = scan(_synthetic_nonuniform(), BASE)
    assert [r.record_addr for r in recs] == [BASE + 0x10, BASE + 0x40, BASE + 0x6A]


def test_scan_recovers_nonuniform_gaps_not_the_modal_stride():
    """The three gaps (0x10->0x40 is 0x30, 0x40->0x6A is 0x2A) are neither the
    0x28 modal stride nor uniform, so only a signature scan -- never a
    fixed-stride walk -- recovers all three."""
    recs = scan(_synthetic_nonuniform(), BASE)
    assert len(recs) == 3
    # The modal stride 0x28 would land at 0x10+0x28=0x38, 0x60, 0x88... which
    # holds none of the three records. Assert the recovered addresses confirm
    # no stride was used.
    for r in recs:
        assert r.record_addr % 4 in (0, 2)
    assert recs[1].record_addr - recs[0].record_addr == 0x30
    assert recs[2].record_addr - recs[1].record_addr == 0x2A


def test_scan_finds_a_record_at_2_mod_4():
    """Trap 7.2: a sweep that tests only 4-byte alignment sees noise and misses
    the 2-mod-4 records. The scanner must find a record whose base is 2 mod 4
    even when it is the only record in the image."""
    image = bytearray(0x200)
    # A single record at the 2-mod-4 base 0x12. A 4-byte-only walk (offsets
    # 0x10, 0x14, ...) steps over it; the 2-byte scan lands on it.
    p = BASE + 0x180
    _place(image, 0x12, p - 4 * (4 + 2), p - 16, p, 4, 2, 11)
    recs = scan(bytes(image), BASE)
    assert len(recs) == 1
    assert recs[0].record_addr == BASE + 0x12
    assert recs[0].record_addr % 4 == 2


# ---------------------------------------------------------------------------
# Ungated: the in-range P-pointer criterion. A terminator alone, or a
# plausible pointer alone, is not a record -- it is the conjunction.
# ---------------------------------------------------------------------------

def _synthetic_with_terminator_only():
    image = bytearray(0x200)
    # A bare terminator at +0x14 of offset 0x60, no in-range P pointer at +0x10.
    struct.pack_into(">I", image, 0x60 + 0x14, TERMINATOR)
    # An in-range-looking pointer at +0x10 of offset 0xA0, no terminator.
    struct.pack_into(">I", image, 0xA0 + 0x10, BASE + 0x100)
    return bytes(image)


def test_scan_requires_terminator_together_with_in_range_p_pointer():
    recs = scan(_synthetic_with_terminator_only(), BASE)
    assert recs == []


def test_scan_rejects_an_out_of_range_p_pointer():
    """A P pointer that does not point inside the image's address span is not a
    valid descriptor, even with the terminator present."""
    image = bytearray(0x200)
    struct.pack_into(">II", image, 0x10 + 0x08, 0, 0)
    struct.pack_into(">II", image, 0x10 + 0x10, BASE + 0x100000, TERMINATOR)
    struct.pack_into(">III", image, 0x10 + 0x1C, 1, 1, 1)
    recs = scan(bytes(image), BASE)
    assert recs == []


def test_scan_reports_field_values():
    recs = scan(_synthetic_nonuniform(), BASE)
    r = recs[0]
    assert isinstance(r, ModuleDescriptor)
    assert r.p_ptr == BASE + 0x200
    assert r.x_ptr == BASE + 0x200 - 4 * (2 + 1)
    assert r.y_ptr == BASE + 0x200 - 4
    assert r.x_words == 2
    assert r.y_words == 1
    assert r.p_words == 9
    assert r.carries_x is True


# ---------------------------------------------------------------------------
# Gated: the real firmware image. The validation identity holds for every
# record that carries an X pointer, with zero exceptions. Skip
# where NMG2_ARTIFACTS is unset, with section 18.5's reason, via the
# `artifacts_dir` fixture.
# ---------------------------------------------------------------------------

CODE_IMAGE_NAME = "CODE_30000400.bin"
N_DESCRIPTORS = 194
N_WITH_X = 173


def _load_code_image(artifacts_dir):
    """The image is read from the path the test DECLARES and the tree is not
    searched for a file of that name. A body that hunts for its input cannot be
    gated on it: the gate would answer RUN and the open would then raise where
    section 18.5 requires a skip WITH A REASON naming the expected path."""
    import os

    with open(os.path.join(artifacts_dir, CODE_IMAGE_NAME), "rb") as fh:
        return fh.read()


@pytest.mark.artifacts(CODE_IMAGE_NAME)
def test_scan_recovers_all_194_descriptors(artifacts_dir):
    image = _load_code_image(artifacts_dir)
    recs = scan(image, BASE)
    assert len(recs) == N_DESCRIPTORS


@pytest.mark.artifacts(CODE_IMAGE_NAME)
def test_validation_identity_holds_for_every_record_with_an_x_pointer(artifacts_dir):
    """X_ptr + 4*(X_words + Y_words) == P_ptr for every record that carries an
    X pointer, with zero exceptions. Logbook 3.1 fixes the zero-exception
    requirement."""
    image = _load_code_image(artifacts_dir)
    recs = scan(image, BASE)
    with_x = [r for r in recs if r.carries_x]
    assert len(with_x) == N_WITH_X
    for r in with_x:
        assert r.x_ptr + 4 * (r.x_words + r.y_words) == r.p_ptr
