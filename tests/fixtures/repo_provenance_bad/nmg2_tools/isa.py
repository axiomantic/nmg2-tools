"""An instruction decoder.

The reference disassembler is GPL-3.0. This module names it and then says
nothing at all about how the encodings below were obtained.
"""


def mnemonic(word):
    return "nop" if word == 0 else "undecoded"
