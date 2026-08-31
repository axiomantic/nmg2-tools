"""The `.pch2` parser. Task TOOL-10, design section 15.7, plan section 3.5.

HOW THIS FILE WAS WRITTEN, because the licence makes it matter.

`nmg2-tools` is MIT. A reference implementation of this format exists and is
copyleft: `msg/g2ools`, GPL-2.0-or-later, (c) 2006-2007 Matt Gerassimoff. No
line of `msg/g2ools` is copied, transliterated or paraphrased here. What this
file states about the container is a FACT about a data format -- which byte
sits at which offset, how wide a length field is, in which byte order it is
written, and which range a checksum covers. Facts are not copyrightable; the
reference code is a different expression of them and is not used. The operator
ruled on 2026-08-26 that this project takes the SPEC-ONLY CLEAN-ROOM route for
this format.

TWO SOURCES FED THIS FILE, AND THEY ARE NOT THE SAME KIND OF THING.

(a) THE CONTAINER SHAPE CAME FROM THIS PROJECT'S OWN DESIGN, sections 15.7 and
    15.3. That is an INTERNAL SPECIFICATION, not a third-party implementation.
    From it come the `[1-byte type][2-byte length][payload]` framing and the
    CRC-16/CCITT XMODEM parameters -- polynomial 0x1021, most significant bit
    first, initial value 0, no final exclusive-or, stored big-endian -- both
    restated under THE FORMAT below.

(b) THREE OF THE ELEVEN CODES IN `ACCEPTED_OBJECT_TYPES` CAME FROM OBSERVED
    BYTES, added 2026-08-26. They were read off the operator's own patch by
    walking the framing and reading each frame's type byte. No reference
    implementation, and no description of one, was consulted for them. They
    were then confirmed against the 73-file corpus at
    `nmg2-artifacts/corpus/pch2`: all 73 files walk to `filesize-2` exactly,
    all 73 CRCs verify, and the 1314 frames they hold carry exactly those
    eleven codes and no twelfth. The header boundary is MEASURED per file --
    two of the 73 carry a shorter text header than the rest, so a fixed offset
    would have walked 71 and read the two failures as bad data rather than as
    its own wrong assumption.

WHY THE RECORD CARRIES THE WEIGHT AND THE CODE CANNOT. A layout that merely
happens to match a reference somebody read is not independent, and a matching
layout is what BOTH a clean derivation and a contaminated one produce. The
result cannot separate them; only the account of how it was obtained can. Lint
18 reads this record's FORM and can never read its truth, so a reviewer is the
only thing between a false record and the repository.

WHAT IS NOT DERIVED HERE, AND MUST NOT BE FILLED IN BY GUESSING.

- THE ELEVEN TYPE CODES ARE UNNAMED AND THEIR MEANING IS NOT DERIVED. This
  parser FRAMES and CRC-CHECKS. Every payload stays an opaque byte string that
  nothing here interprets. Accepting eleven types is not decoding eleven types,
  and a reader who reads it as the second is reading something this file never
  claims.
- Names may not come from this project's current sessions. Deriving a name
  needs a reader who has seen NEITHER the reference NOR any summary of one, and
  who correlates against observable patch properties. A name recalled from a
  summary is indistinguishable from a derived one, and one plausible name would
  poison the whole record.
- A CONSTANT IS NOT PROVEN TO BE PADDING. Where corpus-derived structure is
  mentioned, that caveat travels with it: the corpus is one vendor's demo set,
  not a random sample, so a field every patch left at its default looks exactly
  like reserved space. Only a bit that VARIES is proven to be a field.
- Bit-level field layouts inside payloads. Payloads are bit-packed and not
  byte-aligned, and this file does not describe one.

THE FORMAT.

Design section 15.7 fixes the shape, and this parser implements exactly that
shape and nothing else:

    the `.pch2` format is a text header, a 2-byte binary header, then objects
    of [1-byte type][2-byte length][payload]. Fields are bit-packed and are
    not byte aligned.

Design section 15.3 fixes the CRC: CRC-16/CCITT, the XMODEM variant,
polynomial 0x1021, most significant bit first, initial value 0, no final
exclusive-or, stored big-endian. In a `.pch2` file it covers the version and
type bytes and every chunk, and excludes only the trailing CRC. The text
header is before the covered range.

WHERE THE ACCEPTED TYPE SET COMES FROM, AND WHY IT IS NOT IMPORTED.

`ACCEPTED_OBJECT_TYPES` is stated in this module and is not read from the
corpus generator. A parser that takes its accepted set from a generator accepts
exactly what that generator writes, and the generator writes exactly what the
specification names, so the two agree with each other for ANY set whatever and
no run over synthesized files can disagree with either. The set below is the
specification's union widened by type codes measured in real `.pch2` files.

The guarantee an import would have given -- that no type the generator writes
is refused here -- is asserted in the suite instead. An assertion can fail; an
import cannot.

The CRC routine is still imported. It is an algorithm design section 15.3
fixes rather than a decision about what to accept, and every real file is read
through it, so a wrong routine refuses real files loudly.

WHAT THE PARSER PROVES, AND WHAT IT DOES NOT.

This module parses framing, bit packing and the CRC. It proves that a file
holds well-formed objects and a valid CRC. It does NOT prove payload semantics:
design section 15.7 gives no payload layout for any object type, so a payload
that is well-framed but semantically wrong passes this parser. That is a known,
stated, accepted gap and a green T0 run over the synthesized corpus is not
coverage of the G2 Demo corpus for exactly that reason.

THE FILE-AGAINST-WIRE DIFFERENCES (design section 15.7).

1. The variation count is 9 in a file and 10 on the wire, and it affects
   0x4D and 0x65. A file carries 9; this parser reads the file, so it reads 9.
   Nothing here states anything about the tenth variation because nobody knows
   what it holds.
2. Two extra bytes, 0x2D 0x00, follow the 0x21 chunk in USB dumps. They are
   RAW bytes and not an object -- an object header is three bytes. This parser
   recognises the two-byte trailer immediately after a 0x21 object and records
   it on the result. Both the file form and the USB form are committed in the
   corpus, so both must parse.
3. Morph parameter names are omitted on write in both paths. The file carries
   no name, so this parser has nothing to read there and needs no branch for
   it. The omission is a fact about the file, not an extra field to skip.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from nmg2_tools.synth_pch2 import crc16_ccitt

# The object type codes this parser accepts, sorted. The provenance is mixed
# and the mixture is the point: some are the codes design section 15.7 and
# design section 18 name, and the rest were MEASURED in real `.pch2` files by
# walking the framing and reading each frame's type byte.
#
# NO AUTHORITY AVAILABLE TO THIS REPOSITORY STATES WHAT ANY OF THESE CODES
# MEAN. Accepting a code frames its payload and decodes nothing of it, so none
# is named here and a name for one must not be invented: an invented name reads
# as recovered knowledge and there is none behind it.
ACCEPTED_OBJECT_TYPES = (
    0x21,
    0x4A,
    0x4D,
    0x52,
    0x5A,
    0x5B,
    0x60,
    0x62,
    0x65,
    0x69,
    0x6F,
)

# The USB trailer design section 15.7 names: two raw bytes that follow the
# 0x21 chunk in USB dumps and are not an object. An object header is three
# bytes; this pair is two.
USB_TRAILER = b"\x2d\x00"

# The object type whose chunk the USB trailer follows.
TYPE_0X21 = 0x21


class Pch2Error(ValueError):
    """A `.pch2` file this parser refuses to read.

    The message starts with a NAME (`PCH2-BAD-CRC`, `PCH2-LENGTH-PAST-END`,
    `PCH2-TRUNCATED-OBJECT` or `PCH2-UNKNOWN-OBJECT-TYPE`) so that a caller --
    and the corpus manifest that names the expected refusal -- can match on it.
    """


class Pch2BadCrc(Pch2Error):
    """The stored CRC does not match the CRC computed over the covered range."""

    NAME = "PCH2-BAD-CRC"


class Pch2LengthPastEnd(Pch2Error):
    """An object declares a length that runs past the end of the file."""

    NAME = "PCH2-LENGTH-PAST-END"


class Pch2TruncatedObject(Pch2Error):
    """An object's payload stops early: fewer bytes present than declared."""

    NAME = "PCH2-TRUNCATED-OBJECT"


class Pch2UnknownObjectType(Pch2Error):
    """An object carries a type code this parser does not accept."""

    NAME = "PCH2-UNKNOWN-OBJECT-TYPE"



@dataclasses.dataclass(frozen=True)
class Pch2Object:
    """One object: a 1-byte type, a 2-byte length and that many payload bytes."""

    type: int
    payload: bytes

    @property
    def length(self) -> int:
        """The payload byte count, which is the object's 2-byte length field."""
        return len(self.payload)


@dataclasses.dataclass(frozen=True)
class Pch2File:
    """A parsed `.pch2` file: the two header bytes, the objects and the CRC."""

    version: int
    type: int
    objects: tuple[Pch2Object, ...]
    usb_trailer: bool
    stored_crc: int
    computed_crc: int

    @property
    def crc_valid(self) -> bool:
        """Whether the stored CRC equals the CRC computed over the covered range."""
        return self.stored_crc == self.computed_crc


def _named_message(error_cls: type[Pch2Error], detail: str) -> str:
    name = getattr(error_cls, "NAME", None)
    if name is None:
        # A structural refusal (no text header, file too small) that the
        # corpus manifest does not name. It still carries the detail so a
        # caller can tell why it happened.
        return detail
    return f"{name}: {detail}"


def _raise(error_cls: type[Pch2Error], detail: str) -> None:
    raise error_cls(_named_message(error_cls, detail))


def parse(data: bytes) -> Pch2File:
    """Parse a whole `.pch2` file and return the objects and the CRC result.

    The shape this function implements is design section 15.7's, verbatim:

        a text header, a 2-byte binary header, then objects of
        [1-byte type][2-byte length][payload].

    The text header is everything up to and including the first NUL byte, as
    the synthesized corpus writes it. The two bytes after it are the binary
    header: the version byte then the type byte. The covered range -- the
    binary header plus every object -- is checked against the two trailing
    CRC bytes, big-endian, per design section 15.3.

    Raises :class:`Pch2Error` (a named subclass) on any malformed input: a
    bad CRC, a truncated object, a length that runs past the end of the file,
    or an unknown object type.
    """
    # 1. The text header. Everything up to and including the first NUL byte.
    nul = data.find(b"\x00")
    if nul < 0:
        _raise(
            Pch2Error,
            "no NUL byte terminates the text header",
        )
    text_end = nul + 1

    # 2. The two-byte binary header and the trailing two-byte CRC. The
    #    smallest well-formed file is text header + 2 binary header + 2 CRC.
    if len(data) - text_end < 4:
        _raise(Pch2Error, "file is smaller than header plus CRC")

    version = data[text_end]
    type_ = data[text_end + 1]
    stored_crc = int.from_bytes(data[-2:], "big")
    covered = data[text_end : len(data) - 2]
    computed = crc16_ccitt(covered)

    # 3. The CRC is checked BEFORE the objects are walked so that a file with
    #    both a bad CRC and a bad body reports the CRC fault, which is the one
    #    the corpus manifest expects for `bad_crc.pch2`.
    if computed != stored_crc:
        _raise(
            Pch2BadCrc,
            f"stored CRC {stored_crc:#06x} does not match the covered range's "
            f"CRC {computed:#06x}",
        )

    objects, usb_trailer = _walk_objects(covered[2:])

    return Pch2File(
        version=version,
        type=type_,
        objects=objects,
        usb_trailer=usb_trailer,
        stored_crc=stored_crc,
        computed_crc=computed,
    )


def _walk_objects(body: bytes) -> tuple[tuple[Pch2Object, ...], bool]:
    """Walk the object region (everything between the binary header and the
    CRC) and return the objects plus whether the USB trailer was present.

    Each object is [1-byte type][2-byte length][payload] with the length
    big-endian. The payload region is the part of `body` before the trailing
    CRC, so a declared length is satisfied strictly within `body`.

    The USB trailer (difference 2) is consumed when it immediately follows a
    0x21 object: the pair 0x2D 0x00 is two raw bytes, not an object, and the
    specification says they follow the 0x21 chunk. The trailer is part of the
    covered range and its bytes are already accounted for by the CRC.
    """
    objects: list[Pch2Object] = []
    cursor = 0
    usb_trailer = False
    body_len = len(body)

    while cursor < body_len:
        # The USB trailer immediately after a 0x21 object.
        if (
            objects
            and objects[-1].type == TYPE_0X21
            and body[cursor : cursor + 2] == USB_TRAILER
        ):
            usb_trailer = True
            cursor += 2
            continue

        type_byte = body[cursor]
        if type_byte not in ACCEPTED_OBJECT_TYPES:
            _raise(
                Pch2UnknownObjectType,
                f"0x{type_byte:02X} is not an object type this parser accepts "
                f"({', '.join(f'0x{t:02X}' for t in ACCEPTED_OBJECT_TYPES)})",
            )

        if cursor + 3 > body_len:
            # Not even the length field is fully present.
            _raise(Pch2TruncatedObject, "object header is incomplete")

        length = int.from_bytes(body[cursor + 1 : cursor + 3], "big")
        payload_start = cursor + 3
        payload_end = payload_start + length

        if payload_end > body_len:
            available = body_len - payload_start
            if available > 0:
                # Some payload bytes are present but fewer than declared: the
                # payload stops early. A truncated object.
                _raise(
                    Pch2TruncatedObject,
                    f"object 0x{type_byte:02X} declares {length} payload bytes "
                    f"but only {available} are present",
                )
            # No payload bytes at all: the declared length runs past the end
            # of the file.
            _raise(
                Pch2LengthPastEnd,
                f"object 0x{type_byte:02X} declares {length} payload bytes, "
                f"which runs past the end of the file",
            )

        objects.append(Pch2Object(type=type_byte, payload=body[payload_start:payload_end]))
        cursor = payload_end

    return tuple(objects), usb_trailer


def load(path: str | Path) -> Pch2File:
    """Read a `.pch2` file from disk and parse it."""
    return parse(Path(path).read_bytes())
