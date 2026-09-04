# SPDX-License-Identifier: GPL-2.0-or-later
"""A reader whose record is complete and whose HEADER is not.

WHAT THIS FILE IS, because the licence makes it matter.

This repository is MIT. No line of any other implementation is copied,
transliterated or paraphrased here.
"""


def read(data: bytes) -> int:
    return len(data)
