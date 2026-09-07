"""A DSP56300 disassembler over a stated subset.

THE COVERED SET IS SMALL ON PURPOSE.

A disassembler that guessed at an encoding nobody had verified would produce a
plausible-looking wrong decode silently, because a wrong mnemonic reads as well
as a right one. So this module decodes ONLY the instructions below, each of
which was verified against a reference disassembler, and it reports every other
word as `undecoded`:

    nop                  0x000000
    rti                  0x000004
    illegal              0x000005
    rts                  0x00000C
    jmp  $xxxxxx         0x0AF080 plus one address word
    jsr  $xxxxxx         0x0BF080 plus one address word
    movep #xxxxxx,X:pp   0x08F4 plus an operand byte, plus one immediate word
    movep #xxxxxx,Y:pp   0x09F4 plus an operand byte, plus one immediate word

`undecoded` MEANS "THIS PROJECT HAS NOT DECODED THIS WORD". It does not mean
the word is data. `0xFFFFFF` is a real instruction and decodes to `macr`.
Naming it `dc` would state something false about the machine.

`MOVEP`, MEASURED over all 256 operand values. The byte after `08 F4` is NOT
the field `1Spppppp` it is often described as:

    The peripheral address is the operand's low SIX bits added to $FFFFC0, so
    the window is the 64 words $FFFFC0 to $FFFFFF. Reading the WHOLE byte as
    the address gives $FFFFA6, $FFFFA5 and $FFFF9D, which is the common
    mistake.

    `S` is NOT in the operand byte. `08 F4 A6` and `08 F4 E6` both answer
    `x:$FFFFE6`. The memory space comes from the FIRST word: `08` is the X
    space and `09` is the Y space. Bits 7 and 6 do not reach the address.

    Bit 7 is not required. Operand bytes 0x40 to 0xFF decode and 0x00 to 0x3F
    are refused, so the rule is that at least one of the top two bits is set.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

# The instruction word is 24 bits.
WORD_MASK = 0xFFFFFF

# The peripheral window `MOVEP` reaches, and the mask that selects it.
PERIPHERAL_BASE = 0xFFFFC0
PERIPHERAL_MASK = 0x3F

# The operand byte must set at least one of its top two bits. MEASURED:
# 0x00 to 0x3F are refused, 0x40 to 0xFF decode.
PERIPHERAL_OPERAND_FLOOR = 0x40

# `MOVEP` immediate to peripheral. Bits 23..8 of the first word, one value for
# each memory space.
_MOVEP_X = 0x08F4
_MOVEP_Y = 0x09F4

# The two-word jumps, matched on the whole word.
_JMP = 0x0AF080
_JSR = 0x0BF080

# The one-word instructions, matched on the whole word.
_ONE_WORD = {
    0x000000: "nop",
    0x000004: "rti",
    0x000005: "illegal",
    0x00000C: "rts",
}


class Dsp56kDisassembleError(ValueError):
    """A word or a buffer this disassembler refuses to read.

    The message starts with a name: `DSP56K-WORD-TOO-WIDE` or
    `DSP56K-TRUNCATED-INSTRUCTION`.
    """


@dataclasses.dataclass(frozen=True)
class Instruction:
    """One decoded instruction.

    `words` holds every word the instruction consumed, so a caller can advance
    by `len(words)` and can print the bytes beside the text. `address` is the
    word address the instruction starts at, and it is 0 for a bare `decode`.
    """

    words: tuple[int, ...]
    text: str
    address: int = 0


def decode(words: Sequence[int], index: int = 0) -> Instruction:
    """Decode the instruction that starts at `words[index]`.

    Raise `Dsp56kDisassembleError` when a word is not 24 bits, or when the
    buffer ends inside a two-word instruction. A truncated instruction is a
    named failure and never a partial decode, because a partial decode would let
    a caller record an operand that is not there.
    """
    word = _word(words, index)

    text = _ONE_WORD.get(word)
    if text is not None:
        return Instruction(words=(word,), text=text, address=index)

    if word == _JMP:
        return _two_word(words, index, "jmp $%06X")

    if word == _JSR:
        return _two_word(words, index, "jsr $%06X")

    high = word >> 8
    operand = word & 0xFF
    if high in (_MOVEP_X, _MOVEP_Y) and operand >= PERIPHERAL_OPERAND_FLOOR:
        space = "X" if high == _MOVEP_X else "Y"
        address = PERIPHERAL_BASE + (operand & PERIPHERAL_MASK)
        return _two_word(words, index, f"movep #$%06X,{space}:${address:06X}")

    return Instruction(words=(word,), text=f"undecoded ${word:06X}", address=index)


def disassemble(words: Sequence[int], base: int = 0) -> list[Instruction]:
    """Decode a whole buffer, advancing by each instruction's own word count.

    `base` is the word address of `words[0]`. A two-word instruction consumes
    its second word, so a caller that walked one word at a time would
    disassemble an immediate as an instruction and every word after it would be
    off by one.
    """
    out = []
    index = 0
    while index < len(words):
        instruction = decode(words, index)
        out.append(
            dataclasses.replace(instruction, address=base + index)
        )
        index += len(instruction.words)
    return out


def _two_word(words: Sequence[int], index: int, template: str) -> Instruction:
    """Return a two-word instruction whose text takes the second word."""
    if index + 1 >= len(words):
        raise Dsp56kDisassembleError(
            f"DSP56K-TRUNCATED-INSTRUCTION: the word at index {index} needs "
            f"2 words, {len(words) - index} available"
        )
    first = _word(words, index)
    second = _word(words, index + 1)
    return Instruction(
        words=(first, second), text=template % second, address=index
    )


def _word(words: Sequence[int], index: int) -> int:
    """Return `words[index]`, refusing anything that is not a 24-bit word."""
    value = words[index]
    if not 0 <= value <= WORD_MASK:
        sign = "-" if value < 0 else ""
        raise Dsp56kDisassembleError(
            f"DSP56K-WORD-TOO-WIDE: the word at index {index} is "
            f"{sign}0x{abs(value):X}, and an instruction word is 24 bits"
        )
    return value
