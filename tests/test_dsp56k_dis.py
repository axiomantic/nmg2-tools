"""The DSP56300 disassembler. Task TOOL-7, design sections 11.3 and 20.2.

Every word here is HAND-ASSEMBLED and every expected string is a LITERAL. The
test needs no artifact and reads no firmware byte, which is what makes it T0.

HOW THE EXPECTED DECODES WERE OBTAINED. Each one was checked against the
in-tree C++ disassembler, `dsp56kDisassemble`, built from the `dsp56300` clone.
That tool is GPL-3.0, so it was used as an ORACLE and never as a source: it was
run over these words and its ANSWERS were read. No line of it was read, copied
or paraphrased. The oracle is not a dependency of this test, and it cannot be:
this repository declares no runtime dependency and this check must run in a
public repository with no build step. The oracle therefore fixed the facts once,
and the facts are pinned here as literals.

TRAP 7.10 IS THE REASON THIS FILE EXISTS IN THIS SHAPE. `AGENTS.md` section 8
records that reading the `MOVEP` operand byte as the peripheral address produced
`X:$FFFFA6`, `X:$FFFFA5` and `X:$FFFF9D`, which are plausible-looking and wrong.
The real registers are DDR2 at `X:$FFFFE6`, DCO2 at `X:$FFFFE5` and DCO4 at
`X:$FFFFDD`. Each real address is the operand byte's low SIX bits added to
`$FFFFC0`, and the oracle confirms all three.
"""

import pytest

from nmg2_tools.dsp56k_dis import (
    Dsp56kDisassembleError,
    Instruction,
    decode,
    disassemble,
)

# ---------------------------------------------------------------------------
# Trap 7.10. The three real DMA routing registers.
# ---------------------------------------------------------------------------


# WHY EACH TEST BELOW CARRIES A SECOND OPERAND BYTE.
#
# The three operand bytes trap 7.10 records -- 0xA6, 0xA5 and 0x9D -- all have
# BIT 6 CLEAR. A six-bit mask and a seven-bit mask therefore give the SAME
# answer for every one of them, so the three registers the trap is about cannot
# detect a decoder that masked seven bits. That is the mask-width variant of
# trap 7.10 itself, and the tests that exist because of the trap were blind to
# it.
#
# Each test below adds the SAME low six bits with BIT 6 SET. This states no new
# fact about the processor: `test_the_operand_window_...` already pins, from the
# oracle, that 0x40 to 0x7F, 0x80 to 0xBF and 0xC0 to 0xFF all fold onto the
# same 64 words, so 0x66 and 0xA6 answer alike. A seven-bit mask answers
# $1000026 for 0x66 and is caught here.


def test_movep_decodes_the_ddr2_register_at_x_ffffe6():
    """`08 F4 A6`. The operand byte's low six bits are 0x26, and
    $FFFFC0 + $26 = $FFFFE6. The oracle answers `x:<<M_DDR2` for this word."""
    assert decode([0x08F4A6, 0x123456]) == Instruction(
        words=(0x08F4A6, 0x123456),
        text="movep #$123456,X:$FFFFE6",
    )

    # 0x66 carries the same low six bits with bit 6 SET. A seven-bit mask
    # answers $1000026 here and a six-bit mask answers $FFFFE6.
    assert decode([0x08F466, 0x123456]) == Instruction(
        words=(0x08F466, 0x123456),
        text="movep #$123456,X:$FFFFE6",
    )


def test_movep_decodes_the_dco2_register_at_x_ffffe5():
    """`08 F4 A5`. Low six bits 0x25, and $FFFFC0 + $25 = $FFFFE5. The oracle
    answers `x:<<M_DCO2`."""
    assert decode([0x08F4A5, 0x00000F]) == Instruction(
        words=(0x08F4A5, 0x00000F),
        text="movep #$00000F,X:$FFFFE5",
    )

    # 0x65 is the same low six bits with bit 6 set. A seven-bit mask gives
    # $1000025.
    assert decode([0x08F465, 0x00000F]) == Instruction(
        words=(0x08F465, 0x00000F),
        text="movep #$00000F,X:$FFFFE5",
    )


def test_movep_decodes_the_dco4_register_at_x_ffffdd():
    """`08 F4 9D`. Low six bits 0x1D, and $FFFFC0 + $1D = $FFFFDD. The oracle
    answers `x:<<M_DCO4`."""
    assert decode([0x08F49D, 0xABCDEF]) == Instruction(
        words=(0x08F49D, 0xABCDEF),
        text="movep #$ABCDEF,X:$FFFFDD",
    )

    # 0x5D is the same low six bits with bit 6 set. A seven-bit mask gives
    # $100001D.
    assert decode([0x08F45D, 0xABCDEF]) == Instruction(
        words=(0x08F45D, 0xABCDEF),
        text="movep #$ABCDEF,X:$FFFFDD",
    )


def test_the_three_addresses_trap_7_10_recorded_as_wrong_never_appear():
    """The negative half of trap 7.10, stated as a test rather than as a
    comment. Each wrong address is the operand byte read as an address, so a
    decoder that repeated the mistake would print it."""
    texts = [
        decode([0x08F4A6, 0]).text,
        decode([0x08F4A5, 0]).text,
        decode([0x08F49D, 0]).text,
    ]

    assert texts == [
        "movep #$000000,X:$FFFFE6",
        "movep #$000000,X:$FFFFE5",
        "movep #$000000,X:$FFFFDD",
    ]
    for wrong in ("$FFFFA6", "$FFFFA5", "$FFFF9D"):
        assert not any(wrong in text for text in texts)

    # The same three registers reached through an operand whose bit 6 is SET.
    # Bit 6 is clear in all three bytes above, so without these the mask width
    # is unpinned and a seven-bit mask passes the whole trap 7.10 group.
    bit_six_set = [
        decode([0x08F466, 0]).text,
        decode([0x08F465, 0]).text,
        decode([0x08F45D, 0]).text,
    ]

    assert bit_six_set == texts


def test_the_memory_space_comes_from_the_first_word_and_not_from_the_operand():
    """MEASURED AGAINST THE ORACLE, AND IT CONTRADICTS A PLAIN READING OF THE
    PLAN. The plan describes the operand byte as `1Spppppp`, which places the
    space bit in the operand. It is not there: `08 F4 A6` and `08 F4 E6` both
    answer `x:$FFFFE6`, and the Y space comes from `09` in the FIRST word."""
    assert decode([0x08F4A6, 0x000001]).text == "movep #$000001,X:$FFFFE6"
    assert decode([0x08F4E6, 0x000001]).text == "movep #$000001,X:$FFFFE6"
    assert decode([0x09F4A6, 0x000001]).text == "movep #$000001,Y:$FFFFE6"
    assert decode([0x09F4E6, 0x000001]).text == "movep #$000001,Y:$FFFFE6"


def test_the_operand_window_is_the_sixty_four_words_from_ffffc0_to_ffffff():
    """The address is the low SIX bits added to $FFFFC0, so the window is
    exactly 64 words. A decoder that masked seven or eight bits would fold one
    of these onto another address."""
    assert decode([0x08F440, 0]).text == "movep #$000000,X:$FFFFC0"
    assert decode([0x08F47F, 0]).text == "movep #$000000,X:$FFFFFF"
    assert decode([0x08F480, 0]).text == "movep #$000000,X:$FFFFC0"
    assert decode([0x08F4BF, 0]).text == "movep #$000000,X:$FFFFFF"
    assert decode([0x08F4C0, 0]).text == "movep #$000000,X:$FFFFC0"
    assert decode([0x08F4FF, 0]).text == "movep #$000000,X:$FFFFFF"


def test_an_operand_below_0x40_is_not_this_instruction():
    """MEASURED. The oracle decodes operand bytes 0x40 to 0xFF as `movep` and
    answers `dc` for 0x00 to 0x3F, so the top two bits are not spare and at
    least one of them must be set. BIT 7 is not required: 0x7F decodes and 0x26
    does not."""
    assert decode([0x08F43F, 0]).text == "undecoded $08F43F"
    assert decode([0x08F426, 0]).text == "undecoded $08F426"
    assert decode([0x08F400, 0]).text == "undecoded $08F400"
    assert decode([0x08F440, 0]).text == "movep #$000000,X:$FFFFC0"


def test_a_movep_with_no_immediate_word_after_it_is_refused():
    """The immediate form is two words. A buffer that ends inside it is a named
    failure and never a guess."""
    with pytest.raises(Dsp56kDisassembleError) as caught:
        decode([0x08F4A6])

    assert str(caught.value) == (
        "DSP56K-TRUNCATED-INSTRUCTION: the word at index 0 needs 2 words, "
        "1 available"
    )


# ---------------------------------------------------------------------------
# The rest of the covered set. Each entry was answered by the oracle.
# ---------------------------------------------------------------------------


def test_the_one_word_instructions_the_covered_set_names():
    """The WHOLE instruction, not only its text. Reading `.text` alone leaves
    the word count of all four unpinned, and a decoder that reported two words
    for a one-word instruction would desynchronize every walk after it while
    printing the right mnemonic."""
    assert decode([0x000000]) == Instruction(words=(0x000000,), text="nop")
    assert decode([0x000004]) == Instruction(words=(0x000004,), text="rti")
    assert decode([0x000005]) == Instruction(words=(0x000005,), text="illegal")
    assert decode([0x00000C]) == Instruction(words=(0x00000C,), text="rts")


def test_the_two_word_jumps_the_covered_set_names():
    assert decode([0x0AF080, 0x001234]) == Instruction(
        words=(0x0AF080, 0x001234), text="jmp $001234"
    )
    assert decode([0x0BF080, 0x001234]) == Instruction(
        words=(0x0BF080, 0x001234), text="jsr $001234"
    )


def test_a_near_miss_of_a_covered_jump_is_not_decoded_as_that_jump():
    """MEASURED. `0A F0 81` is `punlock` and `0B F0 81` is `plock`, and neither
    is covered here. A decoder that matched on the first two bytes alone would
    call both of them a jump and would be wrong twice."""
    assert decode([0x0AF081, 0x001234]).text == "undecoded $0AF081"
    assert decode([0x0BF081, 0x001234]).text == "undecoded $0BF081"
    assert decode([0x0AF000, 0x001234]).text == "undecoded $0AF000"


def test_a_near_miss_of_a_covered_one_word_instruction_is_not_decoded():
    """MEASURED: the oracle answers `dc` for 0x00000D, so `rts` is 0x00000C
    exactly and not a range. 0x000001 is a DIFFERENT case -- the oracle answers
    `pflushun`, which is a real instruction this covered set does not name --
    and `undecoded` is the right answer for both, for two different reasons."""
    assert decode([0x00000D]).text == "undecoded $00000D"
    assert decode([0x000001]).text == "undecoded $000001"


def test_a_word_outside_the_covered_set_says_so_and_never_invents_a_mnemonic():
    """`undecoded` means "this project has not decoded this word". It does NOT
    mean the word is data. 0xFFFFFF is a real instruction -- the oracle answers
    `macr` for it -- and this disassembler covers a stated subset, so saying
    `dc` would claim something false about the machine."""
    assert decode([0xFFFFFF]).text == "undecoded $FFFFFF"
    assert decode([0x123456]).text == "undecoded $123456"
    assert decode([0x4CA000]).text == "undecoded $4CA000"


def test_the_word_count_of_every_covered_instruction():
    """EVERY, and the name is the contract. An instruction this test leaves
    out carries no word count at all, and a stride error in it passes here.

    A wrong word count desynchronizes every instruction after it, which is the
    failure a stride error produces in a walk."""
    # The one-word instructions the covered set names.
    assert decode([0x000000]).words == (0x000000,)
    assert decode([0x000004]).words == (0x000004,)
    assert decode([0x000005]).words == (0x000005,)
    assert decode([0x00000C]).words == (0x00000C,)

    # The two-word instructions the covered set names.
    assert decode([0x0AF080, 0x001234]).words == (0x0AF080, 0x001234)
    assert decode([0x0BF080, 0x001234]).words == (0x0BF080, 0x001234)
    assert decode([0x08F4A6, 0x123456]).words == (0x08F4A6, 0x123456)
    assert decode([0x09F4A6, 0x123456]).words == (0x09F4A6, 0x123456)

    # A word outside the covered set consumes one word and never guesses at a
    # second, so a walk over undecoded words advances by one.
    assert decode([0xFFFFFF]).words == (0xFFFFFF,)


# ---------------------------------------------------------------------------
# Walking a buffer.
# ---------------------------------------------------------------------------


def test_disassemble_walks_a_buffer_and_advances_by_the_word_count():
    """The two-word `movep` must consume its immediate. If it did not, the
    immediate would be disassembled as an instruction and every word after it
    would be off by one."""
    assert disassemble([0x000000, 0x08F4A6, 0x123456, 0x00000C], base=0x100) == [
        Instruction(words=(0x000000,), text="nop", address=0x100),
        Instruction(
            words=(0x08F4A6, 0x123456),
            text="movep #$123456,X:$FFFFE6",
            address=0x101,
        ),
        Instruction(words=(0x00000C,), text="rts", address=0x103),
    ]


def test_disassemble_of_an_empty_buffer_is_an_empty_list():
    assert disassemble([]) == []


def test_a_trailing_two_word_instruction_with_no_room_is_refused():
    """A buffer that ends inside an instruction is a named failure. Returning a
    partial decode would let a caller record an operand that is not there."""
    with pytest.raises(Dsp56kDisassembleError) as caught:
        disassemble([0x000000, 0x08F4A6])

    assert str(caught.value) == (
        "DSP56K-TRUNCATED-INSTRUCTION: the word at index 1 needs 2 words, "
        "1 available"
    )


def test_a_word_wider_than_twenty_four_bits_is_refused():
    """The instruction word is 24 bits. A 32-bit value from a bad reader would
    otherwise decode as something, and silently."""
    with pytest.raises(Dsp56kDisassembleError) as caught:
        decode([0x1000000])

    assert str(caught.value) == (
        "DSP56K-WORD-TOO-WIDE: the word at index 0 is 0x1000000, and an "
        "instruction word is 24 bits"
    )


def test_a_negative_word_is_refused():
    with pytest.raises(Dsp56kDisassembleError) as caught:
        decode([-1])

    assert str(caught.value) == (
        "DSP56K-WORD-TOO-WIDE: the word at index 0 is -0x1, and an "
        "instruction word is 24 bits"
    )


def test_disassemble_checks_every_word_and_not_only_the_first():
    """A width check that ran once would pass a buffer whose fault is later,
    which is the buffer a real reader produces."""
    with pytest.raises(Dsp56kDisassembleError) as caught:
        disassemble([0x000000, 0x000000, 0x1000000])

    assert str(caught.value) == (
        "DSP56K-WORD-TOO-WIDE: the word at index 2 is 0x1000000, and an "
        "instruction word is 24 bits"
    )
