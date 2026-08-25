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
5. PAYLOAD-REGISTER-MALFORMED: the register itself holds a
   ``public pch2-exception`` row that does not name the repository it is
   granted for. This is a failure of the REGISTER and not of any committed
   file, so it fails whatever the tree holds, and in either visibility.

The register file format
-------------------------
A simple tab-separated text file, one row per line::

    <path><TAB><visibility>[<TAB><repo>]

``path`` is a repository-relative path. A path ending in ``/`` names a
directory and covers every path beneath it. The optional third field is an
``owner/name`` repository slug that SCOPES the row to one repository; see
``public pch2-exception`` below. ``visibility`` is one of:

- ``public``               -- the path may be committed in a public
  repository, no size ceiling by itself (clause 3's path scope still
  applies).
- ``private``               -- the path is only for a private repository.
- ``public allow-listed``   -- the path may exceed the size ceiling.
- ``public pch2-exception`` -- the path is exempt from clause 1 ONLY. It is
  an operator-granted exception for a ``.pch2`` file whose provenance is
  unestablished. It grants NO size exemption: clause 3 still applies, so
  use ``public allow-listed`` for that and never assume one implies the
  other. It MUST carry the third ``repo`` field, because this register is
  ONE file shared by every repository: an unqualified row would except
  the path in all of them, and any repository could then silence
  clause 1 by choosing a directory name. The exception applies only when the
  caller passes a matching ``--repo``; an unidentified repository gets no
  exception, so the check fails CLOSED.

  That ``MUST`` is ENFORCED and not merely written here, at two levels. The
  parser REFUSES an exception row that names no repository (clause 5 above),
  so the malformed row cannot enter the register at all; and the grant test
  itself returns no exception for a row with no repository, so an entry
  built in code and never parsed cannot grant one either. The refusal is
  deliberate: a row that reads like a grant and silently grants nothing is
  the same unread rule in the other direction, and the operator who wrote it
  would never learn that the exception they believed they had is not there.

  One consequence of the tab-separated format: the space-separated fallback
  below carries two fields at most, so it can NEVER carry a repository. An
  exception row written with spaces is refused for that reason, however it
  reads.

Blank lines and lines starting with ``#`` are ignored.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SIZE_CEILING = 65_536

# The register SHIPS WITH THIS PACKAGE, so it is resolved against the module's
# own location and never against the process's working directory. A relative
# default here passes from the repository root and fails from every other
# directory -- green on a developer's machine, red in CI, in the shape of a
# defect in the code under test rather than in the path.
SHIPPED_REGISTER = Path(__file__).resolve().parent / "testdata" / "register.tsv"

PCH2_ALLOWED_DIR = "nmg2_tools/testdata/pch2_synth/"

# Clause 3 (the byte ceiling) applies only to a committed file under one of
# these path prefixes. Anything else is out of scope for the ceiling check.
CEILING_SCOPE_DIRS = ("fixtures/", "corpus/", "golden/", "captures/", "testdata/")

# The one accepted spelling of a clause 1 exception, and the substring that
# says a line MEANT to be one. A line that carries the mark but not the exact
# visibility is a malformed exception row, not an unrelated row.
PCH2_EXCEPTION_VISIBILITY = "public pch2-exception"
PCH2_EXCEPTION_MARK = "pch2-exception"


def _in_ceiling_scope(posix_path: str) -> bool:
    parts = posix_path.split("/")
    for i in range(len(parts) - 1):
        if parts[i] + "/" in CEILING_SCOPE_DIRS:
            return True
    return False


class RegisterError(ValueError):
    """A register line the parser refuses to accept."""


class RegisterEntry:
    __slots__ = ("path", "visibility", "repo")

    def __init__(
        self, path: str, visibility: str, repo: str | None = None
    ) -> None:
        self.path = path
        self.visibility = visibility
        self.repo = repo

    @property
    def is_dir_rule(self) -> bool:
        return self.path.endswith("/")

    @property
    def allow_listed(self) -> bool:
        return self.visibility == "public allow-listed"

    @property
    def pch2_excepted(self) -> bool:
        return self.visibility == PCH2_EXCEPTION_VISIBILITY

    def pch2_excepted_in(self, repo: str | None) -> bool:
        """Does this row except clause 1 for the repository being linted?

        A ``pch2-exception`` row applies ONLY in the repository it names, and
        it must name one. The register is one shared file, so a row that
        names no repository would except the path in all of them and let any of
        them silence this lint by choosing a directory name. Both an
        unqualified row (``self.repo`` is ``None``) and an unidentified
        caller (``repo`` is ``None``) therefore get no exception: this fails
        CLOSED on either side. ``load_register`` refuses the unqualified row
        outright; this test is the second lock, for an entry built in code.
        """
        if not self.pch2_excepted:
            return False
        if self.repo is None or repo is None:
            return False
        return repo == self.repo


def load_register(register_path: Path) -> list[RegisterEntry]:
    """Parse a register file into a list of :class:`RegisterEntry`.

    A ``public pch2-exception`` row is accepted in ONE form only: three
    tab-separated fields, the second exactly ``public pch2-exception`` and the
    third a non-empty ``owner/name`` slug. Anything else raises
    :class:`RegisterError` and names the line. The row is refused rather than
    quietly granting nothing, because a security-register row that reads like
    a grant and does nothing is the same silent hole in the other direction.
    Note that the space-separated fallback below produces two fields at most,
    so it can never carry the repository field: an exception row written with
    spaces is refused for that reason.
    """
    entries: list[RegisterEntry] = []
    for lineno, raw_line in enumerate(register_path.read_text().splitlines(), 1):
        line = raw_line.strip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            # Tolerate accidental runs of spaces instead of a literal tab.
            parts = line.split(None, 1)
        if PCH2_EXCEPTION_MARK in line and (
            len(parts) < 3
            or parts[1].strip() != PCH2_EXCEPTION_VISIBILITY
            or not parts[2].strip()
        ):
            raise RegisterError(
                f"{register_path}:{lineno}: a `{PCH2_EXCEPTION_VISIBILITY}` row "
                "must carry a third, tab-separated `owner/name` field naming "
                f"the one repository it is granted for: {line!r}"
            )
        path = parts[0].strip()
        visibility = parts[1].strip()
        repo = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        entries.append(RegisterEntry(path, visibility, repo))
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
    repo: str | None = None,
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
                entry is not None and entry.pch2_excepted_in(repo)
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
    repo_path: Path,
    register_path: Path,
    visibility: str = "public",
    repo: str | None = None,
) -> list[str]:
    entries = load_register(register_path)
    committed = _committed_files(repo_path)
    return lint_committed_files(repo_path, committed, entries, visibility, repo)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repo_path", type=Path, help="path to the repository root to check"
    )
    parser.add_argument(
        "--register",
        type=Path,
        default=SHIPPED_REGISTER,
        help=f"path to the register file (default: {SHIPPED_REGISTER})",
    )
    parser.add_argument(
        "--visibility",
        choices=["public", "private"],
        default="public",
        help="repository visibility (default: public)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help=(
            "the `owner/name` slug of the repository under test, as "
            "`github.repository` supplies it. A `public pch2-exception` "
            "register row that names a repository applies ONLY when this "
            "matches. Omitting it grants no scoped exception."
        ),
    )
    args = parser.parse_args(argv)

    try:
        failures = lint_repo_tree(
            args.repo_path, args.register, args.visibility, args.repo
        )
    except RegisterError as error:
        # A named finding and exit 1, the same shape as every other failure
        # this module reports. A traceback would say the same thing worse.
        print(f"PAYLOAD-REGISTER-MALFORMED: {error}", file=sys.stderr)
        return 1

    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
