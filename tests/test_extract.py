"""Resource extraction from the updaters.

WHAT RUNS WHERE. The two parsers themselves (``nmg2_tools.rsrc`` and
``nmg2_tools.pe``) are binary-format readers and are exercised here with
SYNTHETIC forks and PE files built in this file, so they run everywhere and
need no Clavia byte. The end-to-end claims -- that the macOS updater and the
Windows updater carry byte-identical firmware, and that the extracted images
and their decompressed sections hash to the four values ``artifacts.sha256``
lists -- DO touch real Clavia bytes, and are gated on their family roots via
two family fixtures -- ``installers_dir`` for the vendor updater images and
``artifacts_dir`` for the already-extracted ``.bin`` files. With no artifact
they skip with the gate's reason instead of failing or passing silently.

WHY THE NON-GATED HALF MATTERS: a test that passes when the code is broken is
worse than no test. The gated half cannot run in most environments, so the
parsers need their own, ungated proof here.
"""

import hashlib
import struct

import pytest

from nmg2_tools import pe, rsrc
from nmg2_tools.checksum import checksum
from nmg2_tools.container import load_sections, parse_header
from nmg2_tools.pe import PeError
from nmg2_tools.rsrc import RsrcError

# The SHA-256 digests, written out in full as
# `artifacts.sha256` writes them, so a digest that drifts cannot pass.
HASH_NMG2_OS = "b3a76b7db724d88e3f603e1f500cf873fd525d8015e35d4f985866a842751c3a"
HASH_BOOT_LOADER = "d1b8e30804edbccae853b647e06ac20ae902fd6da05ade7b5d2090ce17c24d88"
HASH_CODE = "2fa65ac9a1ca2d96c5060baedb1bd220efb4140e606738e8e2686a3b93c35788"
HASH_SRAM = "01f5d9f38f82a771028bf88a7d1a623944a576119f6b38e57af6d5d78f2d4357"


# ---------------------------------------------------------------------------
# Synthetic builders. Each parser is proven against a fork or PE it builds
# itself from stated field values, exactly as `tests/test_container.py` builds
# its containers.
# ---------------------------------------------------------------------------

def _u32(x):
    return struct.pack("<I", x & 0xFFFFFFFF)


def _u16(x):
    return struct.pack("<H", x & 0xFFFF)


class _PEBuilder:
    """Assemble the resource section of a PE, then wrap it in a minimal PE32."""

    def __init__(self):
        self.buf = bytearray()

    def here(self):
        return len(self.buf)

    def add_string(self, text):
        off = self.here()
        self.buf += _u16(len(text)) + text.encode("utf-16-le")
        return off

    def add_dir(self, entries):
        off = self.here()
        named = sum(1 for (nw, _tw) in entries if nw & 0x80000000)
        self.buf += _u32(0) + _u32(0) + _u16(0) + _u16(0) + _u16(named) + _u16(len(entries) - named)
        ent_off = len(self.buf)
        self.buf += b"\x00" * (8 * len(entries))
        for i, (nw, tw) in enumerate(entries):
            struct.pack_into("<II", self.buf, ent_off + i * 8, nw, tw)
        return off

    def add_data(self, rva, size):
        off = self.here()
        self.buf += _u32(rva) + _u32(size) + _u32(0) + _u32(0)
        return off

    def patch(self, off, fmt, *vals):
        struct.pack_into(fmt, self.buf, off, *vals)


PE32_MAGIC = 0x10B
PE32PLUS_MAGIC = 0x20B

# Where each optional-header form puts its data directories.
DATA_DIRECTORY_OFFSET = {PE32_MAGIC: 96, PE32PLUS_MAGIC: 112}


def build_pe_file(os_image, loader, *, magic=PE32_MAGIC, virtual_size=None):
    """Build a synthetic PE whose resource tree carries type ``NMG2`` and type
    ``BOOT``, each under one id and one language.

    ``magic`` selects the PE32 or PE32+ optional header, which differ only in
    where the data directories start. ``virtual_size`` overrides the resource
    section's virtual size; a real section's raw size often exceeds it,
    because the raw data is padded to the file alignment."""
    rva_base = 0x1000
    raw_rsrc = 0x200
    b = _PEBuilder()
    root = b.add_dir([(0, 0), (0, 0)])
    root_entry = root + 16
    nmg2_name = b.add_string("NMG2")
    boot_name = b.add_string("BOOT")
    os_off = b.here()
    b.buf += os_image
    loader_off = b.here()
    b.buf += loader
    data_os = b.add_data(rva_base + os_off, len(os_image))
    data_loader = b.add_data(rva_base + loader_off, len(loader))
    lang_os = b.add_dir([(0, data_os)])
    lang_loader = b.add_dir([(0, data_loader)])
    name_os = b.add_dir([(1, lang_os | 0x80000000)])
    name_loader = b.add_dir([(1, lang_loader | 0x80000000)])
    b.patch(root_entry, "<II", nmg2_name | 0x80000000, name_os | 0x80000000)
    b.patch(root_entry + 8, "<II", boot_name | 0x80000000, name_loader | 0x80000000)
    rsrc_blob = bytes(b.buf)

    dos = bytearray(0x40)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x40)
    coff = struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, 0xE0, 0x010F)
    opt = bytearray(0xE0)
    struct.pack_into("<H", opt, 0, magic)
    struct.pack_into(
        "<II", opt, DATA_DIRECTORY_OFFSET[magic] + 2 * 8, rva_base, len(rsrc_blob)
    )
    section = bytearray(40)
    section[0:8] = b".rsrc\0\0\0"
    struct.pack_into(
        "<IIII",
        section,
        8,
        len(rsrc_blob) if virtual_size is None else virtual_size,
        rva_base,
        len(rsrc_blob),
        raw_rsrc,
    )
    pre = bytes(dos) + b"PE\0\0" + coff + bytes(opt) + bytes(section)
    out = bytearray(raw_rsrc + len(rsrc_blob))
    out[0 : len(pre)] = pre
    out[raw_rsrc : raw_rsrc + len(rsrc_blob)] = rsrc_blob
    return bytes(out)


def build_resource_fork(resources):
    """Build a synthetic Macintosh resource fork with the given ``(type, id,
    name, payload)`` tuples, in the layout ``nmg2_tools.rsrc`` documents."""
    by_type = {}
    for type_code, rid, name, payload in resources:
        by_type.setdefault(type_code, []).append((rid, name, payload))

    data_blob = bytearray()
    data_offsets = {}
    for type_code, items in by_type.items():
        for rid, _name, payload in items:
            data_offsets[(type_code, rid)] = len(data_blob)
            data_blob += struct.pack(">I", len(payload)) + payload

    type_list_size = 2 + 8 * len(by_type)
    ref_off = type_list_size
    ref_offsets = {}
    for type_code, items in by_type.items():
        ref_offsets[type_code] = ref_off
        ref_off += 12 * len(items)

    TYPE_LIST_REL = 28
    name_list_offset = TYPE_LIST_REL + ref_off
    namelist = bytearray()
    name_rel = {}
    for type_code, items in by_type.items():
        for rid, name, _payload in items:
            nb = name.encode("mac-roman") if name else b""
            name_rel[(type_code, rid)] = len(namelist)
            namelist += bytes([len(nb)]) + nb

    m = bytearray(name_list_offset + len(namelist))
    struct.pack_into(">HH", m, 24, TYPE_LIST_REL, name_list_offset)
    pos = TYPE_LIST_REL
    struct.pack_into(">H", m, pos, len(by_type) - 1)
    pos += 2
    for type_code, items in by_type.items():
        struct.pack_into(">4sHH", m, pos, type_code, len(items) - 1, ref_offsets[type_code])
        pos += 8
    for type_code, items in by_type.items():
        p = TYPE_LIST_REL + ref_offsets[type_code]
        for rid, name, _payload in items:
            n_off = name_rel[(type_code, rid)] if name else 0xFFFF
            d3 = data_offsets[(type_code, rid)].to_bytes(3, "big")
            struct.pack_into(">hHB3s4s", m, p, rid, n_off, 0, d3, b"\0\0\0\0")
            p += 12
    m[name_list_offset : name_list_offset + len(namelist)] = namelist

    DATA_OFF = 0x100
    map_off = DATA_OFF + len(data_blob)
    raw = bytearray(map_off + len(m))
    struct.pack_into(">IIII", raw, 0, DATA_OFF, map_off, len(data_blob), len(m))
    raw[DATA_OFF : DATA_OFF + len(data_blob)] = data_blob
    raw[map_off : map_off + len(m)] = m
    return bytes(raw)


def build_container_image(sram_bytes, code_bytes):
    """A synthetic firmware container, both sections STORED (uncompressed), in
    the layout ``nmg2_tools.container`` documents."""
    count = 2
    header = bytearray(0x14)
    struct.pack_into(">HHI", header, 0, 0x00A2, 0x0100, 0)
    struct.pack_into(">I", header, 0x10, count)

    data_offset = 0x14 + count * 0x2C
    sections = [
        (b"SRAM", 0x20000800, sram_bytes),
        (b"CODE", 0x30000400, code_bytes),
    ]
    table = bytearray()
    cursor = data_offset
    for tag, load_address, payload in sections:
        table += struct.pack(
            ">4s7I", tag, cursor, len(payload), load_address, checksum(payload), 0, 0, 0
        ) + b"\x00" * 12
        cursor += len(payload)
    return bytes(header) + bytes(table) + sram_bytes + code_bytes


OS_SRAM = b"SRAM-DATA-1"
OS_CODE = b"CODE-DATA-2"
OS_IMAGE = build_container_image(OS_SRAM, OS_CODE)
LOADER = b"BOOT-LOADER"
FORK = build_resource_fork(
    [
        (b"NMG2", 128, "NMG2_128_OS", OS_IMAGE),
        (b"BOOT", 128, "BOOT_128_Loader", LOADER),
    ]
)
PEFILE = build_pe_file(OS_IMAGE, LOADER)


# ---------------------------------------------------------------------------
# Resource-fork parser, ungated.
# ---------------------------------------------------------------------------

def test_rsrc_parse_recovers_both_images():
    found = {r.type_code: r for r in rsrc.parse_fork(FORK)}
    assert set(found) == {"NMG2", "BOOT"}
    assert found["NMG2"].identifier == 128
    assert found["BOOT"].identifier == 128
    assert found["NMG2"].payload == OS_IMAGE
    assert found["BOOT"].payload == LOADER


def test_rsrc_firmware_returns_the_two_images():
    fw = rsrc.firmware(FORK)
    assert fw.os_image == OS_IMAGE
    assert fw.loader == LOADER


def test_rsrc_a_missing_image_is_a_named_error():
    only_os = build_resource_fork([(b"NMG2", 128, "NMG2_128_OS", OS_IMAGE)])
    with pytest.raises(RsrcError, match="BOOT"):
        rsrc.firmware(only_os)


def test_rsrc_refuses_a_truncated_fork():
    with pytest.raises(RsrcError):
        rsrc.parse_fork(b"\x00" * 8)


# ---------------------------------------------------------------------------
# PE parser, ungated.
# ---------------------------------------------------------------------------

def test_pe_parse_recovers_both_resources():
    resources = {r.type_name: r for r in pe.parse_pe(PEFILE)}
    assert set(resources) == {"NMG2", "BOOT"}
    assert resources["NMG2"].payload == OS_IMAGE
    assert resources["BOOT"].payload == LOADER


def test_pe_firmware_returns_the_two_images():
    fw = pe.firmware(PEFILE)
    assert fw.os_image == OS_IMAGE
    assert fw.loader == LOADER


def test_pe_refuses_a_non_mz_file():
    with pytest.raises(PeError):
        pe.parse_pe(b"this is not a PE file at all" * 4)


def test_pe_refuses_an_mz_that_is_not_pe():
    blob = bytearray(0x60)
    blob[0:2] = b"MZ"
    with pytest.raises(PeError):
        pe.parse_pe(bytes(blob))


def test_pe_names_the_offending_rva_when_it_maps_to_no_section():
    # The data-directory resource RVA sits at optional-header offset 96 + 2*8,
    # and the optional header starts after the DOS stub, the PE signature and
    # the COFF header.
    res_dir_rva_off = 0x40 + 4 + 20 + 96 + 2 * 8
    blob = bytearray(PEFILE)
    struct.pack_into("<I", blob, res_dir_rva_off, 0xDEADB000)
    with pytest.raises(PeError, match=r"PE-OFFSET-OUT-OF-RANGE: resource section RVA 0xDEADB000"):
        pe.parse_pe(bytes(blob))


def test_pe_reads_a_pe32_plus_optional_header():
    """PE32+ puts its data directories 112 bytes into the optional header
    where PE32 puts them at 96. Reading a PE32+ image at the PE32 offset lands
    on the wrong directory entirely."""
    pe32_plus = build_pe_file(OS_IMAGE, LOADER, magic=PE32PLUS_MAGIC)
    resources = {r.type_name: r for r in pe.parse_pe(pe32_plus)}

    assert set(resources) == {"NMG2", "BOOT"}
    assert resources["NMG2"].payload == OS_IMAGE
    assert resources["BOOT"].payload == LOADER


def test_pe_maps_an_rva_that_lies_past_the_section_virtual_size():
    """A section's raw size may exceed its virtual size, and the resource data
    then sits past the virtual size but inside the raw data. Mapping an RVA
    against the virtual size alone loses every such resource."""
    padded = build_pe_file(OS_IMAGE, LOADER, virtual_size=1)
    resources = {r.type_name: r for r in pe.parse_pe(padded)}

    assert resources["NMG2"].payload == OS_IMAGE
    assert resources["BOOT"].payload == LOADER


# ---------------------------------------------------------------------------
# Every attacker-controlled offset reaches a NAMED refusal. `PeError` promises
# one, and an unguarded `unpack_from` breaks that promise with `struct.error`.
# ---------------------------------------------------------------------------


def _pe_with(**overrides):
    """The synthetic PE32 with one field overwritten in place."""
    blob = bytearray(PEFILE)
    dos_stub = 0x40
    optional = dos_stub + 4 + 20
    section = optional + 0xE0
    resource_base = 0x200
    field = {
        "section_count": (dos_stub + 4 + 2, "<H"),
        "section_virtual_address": (section + 12, "<I"),
        "root_named": (resource_base + 12, "<H"),
        "root_ids": (resource_base + 14, "<H"),
        "root_first_name": (resource_base + 16, "<I"),
        "root_first_target": (resource_base + 20, "<I"),
    }
    for name, value in overrides.items():
        offset, fmt = field[name]
        struct.pack_into(fmt, blob, offset, value)
    return bytes(blob)


def test_pe_names_a_dos_header_too_short_to_hold_e_lfanew():
    with pytest.raises(PeError, match="PE-TRUNCATED"):
        pe.parse_pe(b"MZ")


def test_pe_names_a_section_count_the_file_cannot_hold():
    with pytest.raises(PeError, match="PE-TRUNCATED"):
        pe.parse_pe(_pe_with(section_count=0xFFFF))


def test_pe_names_a_directory_entry_count_the_file_cannot_hold():
    with pytest.raises(PeError, match="PE-TRUNCATED"):
        pe.parse_pe(_pe_with(root_ids=4000))


def test_pe_names_a_data_entry_target_past_the_end_of_the_file():
    with pytest.raises(PeError, match="PE-TRUNCATED"):
        pe.parse_pe(_pe_with(root_first_target=0x7FFFFFF0))


def test_pe_names_a_directory_entry_name_past_the_end_of_the_file():
    with pytest.raises(PeError, match="PE-TRUNCATED"):
        pe.parse_pe(_pe_with(root_first_name=0x80000000 | 0x7FFFFFF0))


def test_pe_names_a_resource_directory_that_points_at_itself():
    """A self-pointing entry recurses until the interpreter's own stack limit
    raises a RecursionError, which no caller can match on."""
    with pytest.raises(PeError, match="PE-DIRECTORY-TOO-DEEP"):
        pe.parse_pe(_pe_with(root_first_target=0x80000000 | 0x00000000))


def test_pe_names_a_missing_image():
    # The root directory holds two entries; walking only the first resolves
    # NMG2 and leaves BOOT missing.
    with pytest.raises(PeError, match="PE-RESOURCE-NOT-FOUND"):
        pe.firmware(_pe_with(root_ids=1))


# ---------------------------------------------------------------------------
# End to end, ungated: the mac and windows paths recover the same image, and
# the recovered container re-loads its two sections. This is the claim of
# `test_mac_and_windows_sources_are_identical`, driven with synthetic,
# non-Clavia bytes so the wiring is proven where the gated half cannot run.
# ---------------------------------------------------------------------------

def test_mac_and_windows_paths_give_byte_identical_firmware():
    fw_r = rsrc.firmware(FORK)
    fw_p = pe.firmware(PEFILE)
    assert fw_r.os_image == fw_p.os_image
    assert fw_r.loader == fw_p.loader


def test_recovered_image_reloads_its_sections():
    fw = rsrc.firmware(FORK)
    header = parse_header(fw.os_image)
    assert header.version == 0x00A2
    sections = dict((s.tag, data) for s, data in load_sections(fw.os_image))
    assert sections == {"SRAM": OS_SRAM, "CODE": OS_CODE}


# ---------------------------------------------------------------------------
# Gated: the real Clavia-derived artifacts, in TWO families.
#
# The vendor updater images and the already-extracted `.bin` files are
# different trees with different provenance, and no one directory holds both.
# Each body therefore requests the fixture of the family its inputs live under,
# and declares the paths it opens with `@pytest.mark.artifacts`. A body that
# WALKED the tree for a file matching a suffix could not be gated on that file
# at all: the gate would answer RUN and the walk would then raise where a skip
# WITH A REASON naming the path is required.
# ---------------------------------------------------------------------------

# The installer images, as paths relative to the installers root. One constant
# serves as the declaration AND as the path the body opens, so the gate and the
# read cannot name different files.
MAC_UPDATER_REL = "Nord Modular G2 Updater.rsrc"
WINDOWS_SETUP_REL = "Nord Modular G2 v1.62 Setup.exe"

# The extracted images, relative to the artifacts root.
OS_IMAGE_REL = "NMG2_128_OS.bin"
LOADER_IMAGE_REL = "BOOT_128_Loader.bin"


def _read(directory, relative_path):
    import os

    with open(os.path.join(directory, relative_path), "rb") as fh:
        return fh.read()


@pytest.mark.artifacts(MAC_UPDATER_REL, WINDOWS_SETUP_REL)
def test_mac_and_windows_sources_are_identical(installers_dir):
    mac = rsrc.firmware(_read(installers_dir, MAC_UPDATER_REL))
    win = pe.firmware(_read(installers_dir, WINDOWS_SETUP_REL))
    assert mac.os_image == win.os_image
    assert mac.loader == win.loader


@pytest.mark.artifacts(MAC_UPDATER_REL)
def test_extracted_images_have_the_design_sha256(installers_dir):
    mac = rsrc.firmware(_read(installers_dir, MAC_UPDATER_REL))
    assert hashlib.sha256(mac.os_image).hexdigest() == HASH_NMG2_OS
    assert hashlib.sha256(mac.loader).hexdigest() == HASH_BOOT_LOADER
    sections = dict((s.tag, data) for s, data in load_sections(mac.os_image))
    assert hashlib.sha256(sections["CODE"]).hexdigest() == HASH_CODE
    assert hashlib.sha256(sections["SRAM"]).hexdigest() == HASH_SRAM


@pytest.mark.artifacts(OS_IMAGE_REL, LOADER_IMAGE_REL)
def test_advanced_path_accepts_the_bin_files(artifacts_dir):
    """The advanced path: the operator supplies the two images directly. The
    two files are DECLARED rather than asserted to exist inside the body -- an
    existence assertion in a body is a gate in the wrong place, and it reports
    an absent artifact as a FAILURE where a skip is required."""
    os_image = _read(artifacts_dir, OS_IMAGE_REL)
    loader = _read(artifacts_dir, LOADER_IMAGE_REL)
    assert hashlib.sha256(os_image).hexdigest() == HASH_NMG2_OS
    assert hashlib.sha256(loader).hexdigest() == HASH_BOOT_LOADER
    sections = dict((s.tag, data) for s, data in load_sections(os_image))
    assert hashlib.sha256(sections["CODE"]).hexdigest() == HASH_CODE
    assert hashlib.sha256(sections["SRAM"]).hexdigest() == HASH_SRAM
