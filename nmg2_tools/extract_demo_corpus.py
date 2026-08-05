"""Walk a source tree and copy every ``.pch2`` file into an output corpus.

This tool takes an explicit ``--source`` directory and an explicit
``--dest`` directory. It has NO default source path, so it can never run
against a real installer image by accident.

For every file under ``--source`` whose name ends in ``.pch2``, it writes
the file UNCHANGED into ``<dest>/corpus/pch2/`` and records, in
``<dest>/corpus/pch2/MANIFEST.txt``, the file's path relative to the source
tree, its size in bytes and its SHA-256 digest. The manifest's first line
holds the total count of files it records.

This module is a walk-and-copy tool only. It never runs against, reads, or
writes a real Nord Modular G2 installer image inside this repository's own
test suite; the test suite drives it against a synthetic directory tree
that it builds itself.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


def find_pch2_files(source: Path) -> list[Path]:
    """Return every ``.pch2`` file under ``source``, sorted for determinism."""
    return sorted(p for p in source.rglob("*.pch2") if p.is_file())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract(source: Path, dest: Path) -> Path:
    """Copy every ``.pch2`` file under ``source`` into ``dest``.

    Returns the path to the manifest file it wrote.
    """
    pch2_files = find_pch2_files(source)

    corpus_dir = dest / "corpus"
    pch2_dir = corpus_dir / "pch2"
    pch2_dir.mkdir(parents=True, exist_ok=True)

    manifest_lines: list[str] = []
    for src_file in pch2_files:
        rel_path = src_file.relative_to(source)
        dest_file = pch2_dir / src_file.name
        shutil.copyfile(src_file, dest_file)
        size = src_file.stat().st_size
        sha = _sha256(src_file)
        manifest_lines.append(f"{rel_path.as_posix()}\t{size}\t{sha}")

    manifest_path = pch2_dir / "MANIFEST.txt"
    with manifest_path.open("w") as fh:
        fh.write(f"{len(pch2_files)}\n")
        for line in manifest_lines:
            fh.write(line + "\n")

    return manifest_path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, required=True, help="the installer tree to walk"
    )
    parser.add_argument(
        "--dest", type=Path, required=True, help="the output corpus directory"
    )
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print(f"EXTRACT-NO-SOURCE: {args.source} is not a directory", file=sys.stderr)
        return 1

    extract(args.source, args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
