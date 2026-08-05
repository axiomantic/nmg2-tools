"""Check that committed payloads stay inside the agreed size and location rules.

This check reads COMMITTED FILES ONLY (the output of ``git ls-files``). It
does not read workflow text and it implements no upload check; a separate
step of the plan owns checking what a workflow actually uploads. This
module only checks what is already sitting in the repository's git index.

It takes a ``--visibility public|private`` argument (default ``public``),
the same meaning it has in ``credential_lint.py``, and enforces these
independent conditions, each with its own failure name:

1. PAYLOAD-PCH2-LOCATION: a ``*.pch2`` file anywhere in a public repository
   outside ``nmg2_tools/testdata/pch2_synth/`` fails, unless the register
   holds a ``public pch2-exception`` row covering the path, in which case
   this clause passes.
2. PAYLOAD-UNREGISTERED: any committed file under a ``fixtures/`` path with
   no register row fails, at any size, in either visibility. ``.gitkeep``
   files are exempt everywhere: they are directory markers, not fixtures,
   and a private repository uses one to make a registered but empty
   directory exist.
3. PAYLOAD-CEILING: a committed file above 65,536 bytes, under a
   ``fixtures/``, ``corpus/``, ``golden/``, ``captures/`` or ``testdata/``
   path, with no allow-listed register row, fails. This scope check applies
   in both visibilities.
4. PAYLOAD-PRIVATE-IN-PUBLIC: in a PUBLIC repository, a path whose register
   row is ``private`` is a failure. In a PRIVATE repository a ``private``
   row passes; the row exists precisely so a private repository, such as
   ``nmg2-artifacts``, may hold it.

The register file format
-------------------------
A simple tab-separated text file, one row per line::

    <path><TAB><visibility>

``path`` is a repository-relative path. A path ending in ``/`` names a
directory and covers every path beneath it. ``visibility`` is one of:

- ``public``               -- the path may be committed in a public
  repository, no size ceiling by itself (clause 3's path scope still
  applies).
- ``private``               -- the path is only for a private repository.
- ``public allow-listed``   -- the path may exceed the size ceiling.
- ``public pch2-exception`` -- the path is exempt from clause 1 ONLY. It is
  an operator-granted exception for a ``.pch2`` file whose provenance is
  unestablished. It grants NO size exemption: clause 3 still applies, so
  use ``public allow-listed`` for that and never assume one implies the
  other.

Blank lines and lines starting with ``#`` are ignored.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SIZE_CEILING = 65_536

PCH2_ALLOWED_DIR = "nmg2_tools/testdata/pch2_synth/"

# Clause 3 (the byte ceiling) applies only to a committed file under one of
# these path prefixes. Anything else is out of scope for the ceiling check.
CEILING_SCOPE_DIRS = ("fixtures/", "corpus/", "golden/", "captures/", "testdata/")


def _in_ceiling_scope(posix_path: str) -> bool:
    parts = posix_path.split("/")
    for i in range(len(parts) - 1):
        if parts[i] + "/" in CEILING_SCOPE_DIRS:
            return True
    return False


class RegisterEntry:
    __slots__ = ("path", "visibility")

    def __init__(self, path: str, visibility: str) -> None:
        self.path = path
        self.visibility = visibility

    @property
    def is_dir_rule(self) -> bool:
        return self.path.endswith("/")

    @property
    def allow_listed(self) -> bool:
        return self.visibility == "public allow-listed"

    @property
    def pch2_excepted(self) -> bool:
        return self.visibility == "public pch2-exception"


def load_register(register_path: Path) -> list[RegisterEntry]:
    """Parse a register file into a list of :class:`RegisterEntry`."""
    entries: list[RegisterEntry] = []
    for raw_line in register_path.read_text().splitlines():
        line = raw_line.strip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            # Tolerate accidental runs of spaces instead of a literal tab.
            parts = line.split(None, 1)
        path = parts[0].strip()
        visibility = parts[1].strip()
        entries.append(RegisterEntry(path, visibility))
    return entries


def _find_register_entry(
    rel_path: str, entries: list[RegisterEntry]
) -> RegisterEntry | None:
    best: RegisterEntry | None = None
    for entry in entries:
        if entry.is_dir_rule:
            if rel_path.startswith(entry.path):
                if best is None or len(entry.path) > len(best.path):
                    best = entry
        else:
            if rel_path == entry.path:
                return entry
    return best


def _committed_files(repo_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def lint_committed_files(
    repo_path: Path,
    committed_files: list[str],
    entries: list[RegisterEntry],
    visibility: str = "public",
) -> list[str]:
    """Return named failures for a given list of repository-relative paths."""
    failures: list[str] = []
    for rel_path in committed_files:
        posix_path = rel_path.replace("\\", "/")

        if posix_path.endswith(".gitkeep"):
            continue

        path_parts = posix_path.split("/")
        is_fixture = "fixtures" in path_parts[:-1]
        entry = _find_register_entry(posix_path, entries)

        if visibility == "public" and posix_path.endswith(".pch2"):
            if not posix_path.startswith(PCH2_ALLOWED_DIR) and not (
                entry is not None and entry.pch2_excepted
            ):
                failures.append(
                    f"PAYLOAD-PCH2-LOCATION: {posix_path}: .pch2 file outside "
                    f"{PCH2_ALLOWED_DIR}"
                )

        if is_fixture and entry is None:
            failures.append(
                f"PAYLOAD-UNREGISTERED: {posix_path}: committed fixture with "
                "no register row"
            )
            continue

        if entry is None:
            continue

        if (
            visibility == "public"
            and entry.visibility == "private"
        ):
            failures.append(
                f"PAYLOAD-PRIVATE-IN-PUBLIC: {posix_path}: register marks "
                "this path private, but it is committed in a public "
                "repository"
            )
            continue

        if not _in_ceiling_scope(posix_path):
            continue

        full_path = repo_path / rel_path
        try:
            size = full_path.stat().st_size
        except OSError:
            size = 0

        if size > SIZE_CEILING and not entry.allow_listed:
            failures.append(
                f"PAYLOAD-CEILING: {posix_path}: {size} bytes exceeds the "
                f"{SIZE_CEILING} byte ceiling and is not allow-listed"
            )

    return failures


def lint_repo_tree(
    repo_path: Path, register_path: Path, visibility: str = "public"
) -> list[str]:
    entries = load_register(register_path)
    committed = _committed_files(repo_path)
    return lint_committed_files(repo_path, committed, entries, visibility)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    parser.add_argument(
        "--register",
        type=Path,
        default=Path("nmg2_tools/testdata/register.tsv"),
        help="path to the register file (default: nmg2_tools/testdata/register.tsv)",
    )
    parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="repository visibility (default: public)",
    )
    args = parser.parse_args(argv)

    failures = lint_repo_tree(args.repo_path, args.register, args.visibility)
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
