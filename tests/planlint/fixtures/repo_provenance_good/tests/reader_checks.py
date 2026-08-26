"""Test code that handles bytes. It is not a shipped implementation, so the
record obligation does not reach it."""


def check(data: bytes) -> bool:
    return data == b"\x00"
