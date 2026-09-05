"""Read the G2 firmware images from a Windows PE resource section.

The ``Setup.exe`` updater stores its two firmware images under the same custom
type names the resource fork uses. The macOS and Windows updaters carry byte-identical
firmware, and :func:`firmware` extracts the same two images the
:mod:`nmg2_tools.rsrc` path does.

WHAT THIS FILE IS, because the licence makes it matter. ``nmg2-tools`` is MIT.
The PE layout below is a FACT about the Microsoft PE/COFF data format, which is
publicly specified. No line of any third-party implementation is copied or
paraphrased here.

THE LAYOUT. The subset of PE this module reads is the resource section.

* The image opens with an ``MZ`` DOS header. The long at ``+0x3C`` holds the
  file offset of the PE signature, ``PE\\0\\0``.
* The COFF header follows the signature: 2 bytes machine, 2 bytes section
  count, then 4 bytes time/date, 4 bytes pointer-to-symbol-table, 4 bytes
  symbol count, 2 bytes optional-header size, 2 bytes characteristics.
* The optional header follows. Its first 2 bytes are the magic: ``0x10B`` for
  PE32, ``0x20B`` for PE32+ (the G2 updaters are 32-bit, but the reader
  handles both). PE32's data directories start 96 bytes into the optional
  header; PE32+'s start 112 bytes in. Directory index 2 is the resource table,
  an 8-byte ``(RVA, size)`` pair.
* Section headers follow the optional header (40 bytes each). Each has an
  8-byte name, a 4-byte virtual size, a 4-byte virtual address, a 4-byte raw
  size and a 4-byte pointer-to-raw-data. An RVA maps to a file offset when it
  falls in a section's ``[virtual_address, virtual_address + max(virtual_size,
  raw_size))`` span.

THE RESOURCE TREE. The resource table is a three-level directory. Each
directory is:

    +0x00  u32  characteristics (ignored)
    +0x04  u32  time/date stamp (ignored)
    +0x08  u16  major version (ignored)
    +0x0A  u16  minor version (ignored)
    +0x0C  u16  number of named entries
    +0x0E  u16  number of ID entries

followed by ``named + id`` 8-byte entries. Each 8-byte entry is a
(name, target) pair:

* ``name`` -- an integer name/id when the top bit is clear, or, when the top
  bit is set, an offset from the start of the resource section to a
  length-prefixed UTF-16LE string.
* ``target`` -- an offset from the start of the resource section. When the top
  bit is set it points at a sub-directory; when clear, at a 16-byte data entry
  of ``(RVA, size, code page, reserved)``.

The three levels are type, then name/id, then language, then a data entry.
The G2 updater stores the OS under type ``NMG2`` and the loader under type
``BOOT``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from nmg2_tools.rsrc import Firmware, LOADER_TYPE, OS_TYPE

_PE_SIGNATURE = b"PE\0\0"
_COFF = struct.Struct("<HHIIIHH")
_DATA_DIR = struct.Struct("<II")
_SECTION = struct.Struct("<8sIIIIIIHHI")
_DIRECTORY_HEAD = struct.Struct("<IIHHHH")
_DIRECTORY_ENTRY = struct.Struct("<II")
_DATA_ENTRY = struct.Struct("<IIII")

RESOURCE_DIRECTORY_INDEX = 2
_OFFSET_FLAG = 0x80000000


class PeError(ValueError):
    """A PE file that this reader refuses to read.

    The message starts with a name: ``PE-NOT-MZ``, ``PE-NOT-PE``,
    ``PE-NO-OPTIONAL-HEADER``, ``PE-UNKNOWN-MAGIC``, ``PE-NO-RESOURCES`` or
    ``PE-OFFSET-OUT-OF-RANGE``.
    """


@dataclass(frozen=True)
class PeResource:
    """One resource read from a PE resource section.

    ``type_id``/``type_name`` name the top-level type, ``identifier`` the
    second-level name/id, and ``language`` the third level. Exactly one of the
    id/name pair at each level is set.
    """

    type_id: int | None
    type_name: str | None
    identifier: int | None
    language: int | None
    payload: bytes


def _rva_to_offset(rva: int, sections: list[tuple[int, int, int, int]]) -> int | None:
    """Map an RVA to a file offset, or ``None`` when no section holds it."""
    for virtual_address, virtual_size, raw_size, raw_pointer in sections:
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            return raw_pointer + (rva - virtual_address)
    return None


def _parse_data_entry(raw: bytes, target: int, sections: list) -> bytes:
    """Read the payload a leaf directory entry points at."""
    (data_rva, data_size, _codepage, _reserved) = _DATA_ENTRY.unpack_from(raw, target)
    file_off = _rva_to_offset(data_rva, sections)
    if file_off is None or file_off + data_size > len(raw):
        raise PeError(f"PE-OFFSET-OUT-OF-RANGE: resource data RVA 0x{data_rva:08X}")
    return raw[file_off : file_off + data_size]


def _decode_name(raw: bytes, base: int, name_raw: int):
    """Return ``(string_name, int_id)`` for a directory entry name word."""
    if name_raw & _OFFSET_FLAG:
        str_off = base + (name_raw & ~_OFFSET_FLAG)
        (length,) = struct.unpack_from("<H", raw, str_off)
        text = raw[str_off + 2 : str_off + 2 + length * 2].decode("utf-16-le", "replace")
        return text, None
    return None, name_raw


def _recurse(
    raw: bytes,
    base: int,
    offset: int,
    sections: list,
    depth: int,
    type_id: int | None,
    type_name: str | None,
    identifier: int | None,
    out: list[PeResource],
) -> None:
    head = _DIRECTORY_HEAD.unpack_from(raw, offset)
    named, ids = head[4], head[5]
    entry_off = offset + _DIRECTORY_HEAD.size
    total = named + ids

    for i in range(total):
        name_raw, target_raw = _DIRECTORY_ENTRY.unpack_from(raw, entry_off + i * _DIRECTORY_ENTRY.size)
        name_str, name_id = _decode_name(raw, base, name_raw)

        if target_raw & _OFFSET_FLAG:
            _recurse(
                raw,
                base,
                base + (target_raw & ~_OFFSET_FLAG),
                sections,
                depth + 1,
                type_id if depth > 0 else name_id,
                type_name if depth > 0 else name_str,
                name_id if depth == 1 else identifier,
                out,
            )
            continue

        payload = _parse_data_entry(raw, base + target_raw, sections)
        if depth == 2:
            out.append(
                PeResource(
                    type_id=type_id,
                    type_name=type_name,
                    identifier=identifier,
                    language=name_id if name_str is None else None,
                    payload=payload,
                )
            )
        elif depth == 1:
            out.append(
                PeResource(
                    type_id=type_id,
                    type_name=type_name,
                    identifier=name_id if name_str is None else None,
                    language=None,
                    payload=payload,
                )
            )
        else:
            out.append(
                PeResource(
                    type_id=name_id,
                    type_name=name_str,
                    identifier=None,
                    language=None,
                    payload=payload,
                )
            )


def parse_pe(data: bytes | bytearray | memoryview) -> tuple[PeResource, ...]:
    """Parse every resource in a PE file.

    Raise :class:`PeError` when the file is not a PE or has no resource
    section.
    """
    raw = bytes(data)

    if raw[:2] != b"MZ":
        raise PeError("PE-NOT-MZ")

    (e_lfanew,) = struct.unpack_from("<I", raw, 0x3C)
    if raw[e_lfanew : e_lfanew + 4] != _PE_SIGNATURE:
        raise PeError("PE-NOT-PE")

    coff = e_lfanew + 4
    _machine, section_count, _t, _sym_ptr, _sym_count, opt_size, _chars = _COFF.unpack_from(raw, coff)
    optional = coff + _COFF.size

    if opt_size < 2:
        raise PeError("PE-NO-OPTIONAL-HEADER")

    (magic,) = struct.unpack_from("<H", raw, optional)
    if magic == 0x10B:
        data_dir_off = optional + 96
    elif magic == 0x20B:
        data_dir_off = optional + 112
    else:
        raise PeError(f"PE-UNKNOWN-MAGIC: 0x{magic:04X}")

    res_entry = data_dir_off + RESOURCE_DIRECTORY_INDEX * _DATA_DIR.size
    if res_entry + _DATA_DIR.size > len(raw):
        raise PeError("PE-NO-RESOURCES")
    (res_rva, res_size) = _DATA_DIR.unpack_from(raw, res_entry)
    if res_rva == 0 or res_size == 0:
        raise PeError("PE-NO-RESOURCES")

    sections = []
    section_off = optional + opt_size
    for i in range(section_count):
        sec = _SECTION.unpack_from(raw, section_off + i * _SECTION.size)
        virtual_size, virtual_address, raw_size, raw_pointer = sec[1], sec[2], sec[3], sec[4]
        sections.append((virtual_address, virtual_size, raw_size, raw_pointer))

    base = _rva_to_offset(res_rva, sections)
    if base is None or base + res_size > len(raw):
        raise PeError("PE-OFFSET-OUT-OF-RANGE: resource section RVA 0x{res_rva:08X}")

    out: list[PeResource] = []
    _recurse(raw, base, base, sections, 0, None, None, None, out)
    return tuple(out)


def extract_images(data: bytes | bytearray | memoryview) -> tuple[bytes, bytes]:
    """Return the ``(os_image, loader)`` pair a PE file carries.

    The same rule applies to the PE page as to the resource fork: the OS sits
    under type ``NMG2`` and the loader under type ``BOOT``. Raise :class:`PeError` when either image is missing.
    """
    os_image = None
    loader = None
    for resource in parse_pe(data):
        if resource.type_name == OS_TYPE:
            os_image = resource.payload
        elif resource.type_name == LOADER_TYPE:
            loader = resource.payload

    if os_image is None:
        raise PeError(f"{OS_TYPE} resource not found in the PE file")
    if loader is None:
        raise PeError(f"{LOADER_TYPE} resource not found in the PE file")
    return os_image, loader


def firmware(data: bytes | bytearray | memoryview) -> Firmware:
    """Return the two images as a :class:`Firmware`."""
    os_image, loader = extract_images(data)
    return Firmware(os_image=os_image, loader=loader)
