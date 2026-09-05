"""A decoder for an external container format, with no provenance record.

It states the layout it decodes and says nothing about where the layout came
from.
"""


def decode(data: bytes) -> int:
    return len(data)
