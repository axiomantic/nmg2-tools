# nmg2-tools

Python tools for the Nord Modular G2 emulator project.

This repository holds the analysis and build tools. It holds no emulator code,
and it uses no CMake.

## Status

Early. This repository holds the project layout and the test configuration. The
tools are not complete.

## What the tools do

| Tool | Function |
|---|---|
| Firmware extractor | Reads a firmware container and writes the parts it holds. |
| Flash image builder | Builds a flash image from its parts. |
| Signature scanner | Finds known code and data patterns in a binary. |
| DSP56300 disassembler | Disassembles DSP56300 machine code. |
| Patch tools | Read and write `.pch2` patch files. |

The firmware extractor is the test oracle for the C++ extractor in the emulator.
The two must give the same bytes. A test asserts this against a synthetic
container.

## Layout

The layout is fixed. Do not use a different one.

| Path | Content |
|---|---|
| `nmg2_tools/` | The package. All tool code lives here. |
| `tests/` | All tests. They live in the repository root, not in the package. |

`pyproject.toml` sets `testpaths = ["tests"]` and `pythonpath = ["."]`, so
`pytest` finds the tests and the tests import the package from the repository
root.

## Requirements

- Python 3.11 or later.
- pytest 7.0 or later.

## How to test

```
pytest
```

To run one file:

```
pytest tests/test_pch2.py
```

## Test data

This repository holds no data that Clavia wrote, and it never will.

The required tests read synthetic test data only. A contributor can run them
from a fork, and they need no configuration.

Some other tests read a private artifact tree. Those trees come in FAMILIES,
and each family has its own variable, because no one directory holds them all:

| Variable | Family |
|---|---|
| `NMG2_ARTIFACTS` | The firmware images, the recovered tables and the patch corpus. |
| `NMG2_DESCRIPTORS` | The module descriptor and editor panel tables. |
| `NMG2_INSTALLERS` | The vendor installer images the extractor reads. |

A family never falls back to another family's root. When a family's variable is
not set, or a file the test declares is not under that family's root, the test
skips and the reason names the variable and the path. It never fails for that
reason, and it never resolves a fixture out of a tree it did not name.

## Licence

MIT. See `LICENSE`.

The MIT licence puts a rule on every contribution: **this repository is
clean-room with respect to GPL and LGPL code.** Do not copy, port, translate or
transliterate code from a GPL or LGPL source into this repository. This applies
to the known GPL editors and tools in this problem space, among them
`msg/g2ools`, `BVerhue/nord_g2_editor` and `redpola/nomad2026`.

Facts stay usable. Protocol message formats, field offsets, bit layouts and
module type identifiers are facts, not expression, so a GPL tool is a
legitimate place to *check* a fact. Only copied expression is a problem.
