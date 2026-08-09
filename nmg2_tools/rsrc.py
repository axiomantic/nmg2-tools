"""Parse a Macintosh resource fork and extract the G2 firmware images.

Task TOOL-4. Design section 7.2 (accepted inputs) and 7.3 step 1 (find the
resources: type ``NMG2``, identifier 128, is the OS; type ``BOOT``, identifier
128, is the loader).

WHAT THIS FILE IS, because the licence makes it matter. ``nmg2-tools`` is MIT.
The resource-fork layout below is a FACT about a data format: which field sits
at which offset, how wide it is and in which byte order it is written. Facts
are not copyrightable. No line of any implementation is copied or paraphrased
here. The workspace reference ``tools/rsrcparse.py`` was read only as a
statement of the layout.

THE LAYOUT. A resource fork opens with a 16-byte header of four big-endian
longs:

    +0x00  u32  the offset of the resource data area, from the start of the
                 fork.
    +0x04  u32  the offset of the resource map, from the start of the fork.
    +0x08  u32  the length of the resource data area.
    +0x0C  u32  the length of the resource map.

The resource map holds three tables. First are 16 bytes that copy the header,
then 4 bytes of next-map handle, then 2 bytes of file reference, then 2 bytes
of attributes, then two offsets measured from the start of the map:

    +24    u16  the offset of the type list.
    +26    u16  the offset of the name list.

The type list opens with a big-endian u16 count stored as ``count - 1``, then
one 8-byte entry per type:

    entry +0x00  char[4]  the type code, e.g. ``NMG2`` or ``BOOT``. Mac OS
                          Roman.
    entry +0x04  u16      the number of resources of this type, as
                          ``count - 1``.
    entry +0x06  u16      the offset of this type's reference list, measured
                          from the start of the type list.

Each reference list holds one 12-byte entry per resource:

    +0x00  i16  the resource identifier (128 for both images).
    +0x02  u16  the offset of the resource name in the name list, or 0xFFFF
                when the resource carries no name.
    +0x04  u8   the resource attributes.
    +0x05  24-bit, big-endian. The offset of the resource data, measured from
              the start of the fork's data area.
    +0x08  4    reserved handle. Not read.

The data area holds the payload of every resource. At the data offset recorded
in the reference list the first big-endian u32 is the payload length and the
payload follows it.

Design section 7.1: the project ships no Clavia bytes. This module parses a
fork the user supplies; it never embeds one.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# The two images the updaters carry.
OS_TYPE = "NMG2"
LOADER_TYPE = "BOOT"
IMAGE_ID = 128

_RESOURCE_HEADER = struct.Struct(">IIII")
_MAP_HEADER = struct.Struct(">HH")
_TYPE_ENTRY = struct.Struct(">4sHH")
_REF_ENTRY = struct.Struct(">hHB3s")
_LENGTH = struct.Struct(">I")


class RsrcError(ValueError):
    """A resource fork that this parser refuses to read.

    The message starts with a name: ``RSRC-NO-HEADER``,
    ``RSRC-TRUNCATED-MAP``, ``RSRC-TRUNCATED-TYPE-LIST``,
    ``RSRC-TRUNCATED-REFERENCE-LIST``, ``RSRC-TRUNCATED-NAME-LIST`` or
    ``RSRC-TRUNCATED-DATA``.
    """


@dataclass(frozen=True)
class Resource:
    """One resource read from a fork."""

    type_code: str
    identifier: int
    name: str
    attributes: int
    payload: bytes


@dataclass(frozen=True)
class Firmware:
    """The two firmware images an updater carries.

    ``os_image`` is the raw container image that design section 7.3 steps 2
    and 3 parse (``nmg2_tools.container.parse_header`` /
    ``load_sections``); it hashes to the ``NMG2_128_OS.bin`` line of
    ``artifacts.sha256``. ``loader`` is the boot loader and hashes to the
    ``BOOT_128_Loader.bin`` line.
    """

    os_image: bytes
    loader: bytes


def parse_fork(data: bytes | bytearray | memoryview) -> tuple[Resource, ...]:
    """Parse every resource in a Macintosh resource fork.

    Raise :class:`RsrcError` when the fork is malformed. The returned tuple is
    in the order the fork's own tables list the types and resources, and is
    not sorted.
    """
    raw = bytes(data)

    if len(raw) < _RESOURCE_HEADER.size:
        raise RsrcError(f"RSRC-NO-HEADER: at least 16 bytes needed, {len(raw)} available")

    data_offset, map_offset, _data_length, map_length = _RESOURCE_HEADER.unpack_from(raw, 0)

    if map_offset + map_length > len(raw):
        raise RsrcError(
            f"RSRC-TRUNCATED-MAP: map needs {map_offset}+{map_length} bytes, "
            f"{len(raw)} available"
        )
    m = raw[map_offset : map_offset + map_length]

    if len(m) < 28:
        raise RsrcError(f"RSRC-TRUNCATED-MAP: map is only {len(m)} bytes")

    type_list_offset, name_list_offset = _MAP_HEADER.unpack_from(m, 24)

    if type_list_offset + 2 > len(m):
        raise RsrcError(f"RSRC-TRUNCATED-TYPE-LIST: type list at {type_list_offset} not in map")
    (type_count,) = struct.unpack_from(">H", m, type_list_offset)
    num_types = type_count + 1

    if type_list_offset + 2 + num_types * _TYPE_ENTRY.size > len(m):
        raise RsrcError(f"RSRC-TRUNCATED-TYPE-LIST: {num_types} type entries need more than the map holds")

    resources: list[Resource] = []
    for index in range(num_types):
        entry = type_list_offset + 2 + index * _TYPE_ENTRY.size
        type_bytes, num_refs_field, ref_list_field = _TYPE_ENTRY.unpack_from(m, entry)
        type_code = type_bytes.decode("mac-roman", "replace")
        num_refs = num_refs_field + 1
        ref_list_offset = type_list_offset + ref_list_field

        if ref_list_offset + num_refs * _REF_ENTRY.size > len(m):
            raise RsrcError(
                f"RSRC-TRUNCATED-REFERENCE-LIST: type {type_code} needs "
                f"{num_refs} references beyond the map"
            )

        for j in range(num_refs):
            ref = ref_list_offset + j * _REF_ENTRY.size
            identifier, name_offset, attributes, data_field = _REF_ENTRY.unpack_from(m, ref)
            data_in_area = int.from_bytes(data_field, "big")

            name = ""
            if name_offset != 0xFFFF:
                name_loc = name_list_offset + name_offset
                if name_loc >= len(m):
                    raise RsrcError(
                        f"RSRC-TRUNCATED-NAME-LIST: name at {name_loc} outside the map"
                    )
                name_len = m[name_loc]
                if name_loc + 1 + name_len > len(m):
                    raise RsrcError(
                        f"RSRC-TRUNCATED-NAME-LIST: name for type {type_code} id "
                        f"{identifier} runs past the map"
                    )
                name = m[name_loc + 1 : name_loc + 1 + name_len].decode("mac-roman", "replace")

            absolute = data_offset + data_in_area
            if absolute + _LENGTH.size > len(raw):
                raise RsrcError(
                    f"RSRC-TRUNCATED-DATA: {type_code} id {identifier} at 0x{absolute:x} "
                    f"needs a length word beyond the fork"
                )
            (payload_len,) = _LENGTH.unpack_from(raw, absolute)
            if absolute + _LENGTH.size + payload_len > len(raw):
                raise RsrcError(
                    f"RSRC-TRUNCATED-DATA: {type_code} id {identifier} claims "
                    f"{payload_len} bytes past the end of the fork"
                )
            payload = raw[absolute + _LENGTH.size : absolute + _LENGTH.size + payload_len]

            resources.append(
                Resource(
                    type_code=type_code,
                    identifier=identifier,
                    name=name,
                    attributes=attributes,
                    payload=payload,
                )
            )

    return tuple(resources)


def extract_images(
    data: bytes | bytearray | memoryview,
) -> tuple[bytes, bytes]:
    """Return the ``(os_image, loader)`` pair from a resource fork.

    Design section 7.3 step 1: type ``NMG2`` identifier 128 is the OS, type
    ``BOOT`` identifier 128 is the loader. Raise :class:`RsrcError` when
    either image is missing.
    """
    os_image = None
    loader = None
    for resource in parse_fork(data):
        if resource.type_code == OS_TYPE and resource.identifier == IMAGE_ID:
            os_image = resource.payload
        elif resource.type_code == LOADER_TYPE and resource.identifier == IMAGE_ID:
            loader = resource.payload

    if os_image is None:
        raise RsrcError(f"{OS_TYPE} identifier {IMAGE_ID} not found in the fork")
    if loader is None:
        raise RsrcError(f"{LOADER_TYPE} identifier {IMAGE_ID} not found in the fork")
    return os_image, loader


def firmware(data: bytes | bytearray | memoryview) -> Firmware:
    """Return the two images as a :class:`Firmware`."""
    os_image, loader = extract_images(data)
    return Firmware(os_image=os_image, loader=loader)
