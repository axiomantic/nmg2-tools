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

Some other tests read a private artifact tree. The environment variable
`NMG2_ARTIFACTS` gives the path to that tree. When the variable is not set,
those tests skip and give the reason. They never fail for that reason.

## Licence

The licence is not yet set. This repository carries no `LICENSE` file until the
operator selects one.
